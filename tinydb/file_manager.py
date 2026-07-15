"""FileManager: handles file I/O, page allocation, and free list management.

.db file layout:
  Page 0: File Header
    - magic:          b"TINYDB\\0" (8 bytes)
    - version:        uint32
    - page_size:      uint32
    - page_count:     uint32
    - free_list_head: uint32
    - catalog_root:   uint32
    - checksum:       uint64 (CRC32 based)
    - padding:        to fill 4096 bytes
  Pages 1..N: data / catalog / index pages
"""
import struct
import zlib
from tinydb.constants import (
    MAGIC_BYTES, FORMAT_VERSION, PAGE_SIZE,
)
from tinydb.page import (
    PageType, parse_page_header, pack_page_header,
)
from tinydb.exceptions import StorageCorruptionError, PageOutOfRangeError


# File header format (after 8-byte magic):
# version(I) page_size(I) page_count(I) free_list_head(I) catalog_root(I) checksum(Q)
_HEADER_FMT = "<IIIIIIQ"
_HEADER_META_SIZE = struct.calcsize(_HEADER_FMT)
_CHECKSUM_SIZE = struct.calcsize("<Q")
# Number of bytes covered by the checksum (everything before it in the meta region)
_HEADER_DATA_SIZE = _HEADER_META_SIZE - _CHECKSUM_SIZE


class FileManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._file = None
        self.page_count = 0
        self.free_list_head = 0
        self.catalog_root = 0
        self.root_page_id = 0

    def open(self) -> None:
        """Open or create the database file."""
        if self._file is not None:
            return

        import os
        if os.path.exists(self.db_path):
            self._file = open(self.db_path, "r+b")
            self._read_header()
        else:
            self._file = open(self.db_path, "w+b")
            self._init_new_database()

    def close(self) -> None:
        """Flush all metadata and close file."""
        if self._file is None:
            return
        self._write_header()
        self._file.close()
        self._file = None

    def read_page(self, page_id: int) -> bytes:
        """Read raw page data by page_id. Returns PAGE_SIZE bytes."""
        if page_id >= self.page_count:
            raise PageOutOfRangeError(
                f"Page {page_id} out of range (page_count={self.page_count})"
            )
        offset = page_id * PAGE_SIZE
        self._file.seek(offset)
        data = self._file.read(PAGE_SIZE)
        if len(data) < PAGE_SIZE:
            data = data + b"\x00" * (PAGE_SIZE - len(data))
        return data

    def write_page(self, page_id: int, data: bytes) -> None:
        """Write page data to disk at the given page_id. Auto-grows if needed."""
        if page_id < 0:
            raise PageOutOfRangeError(
                f"Page {page_id} out of range (page_count={self.page_count})"
            )
        if len(data) != PAGE_SIZE:
            raise ValueError(f"Page data must be {PAGE_SIZE} bytes, got {len(data)}")

        if page_id >= self.page_count:
            self._grow_to(page_id + 1)

        offset = page_id * PAGE_SIZE
        self._file.seek(offset)
        self._file.write(data)
        self._file.flush()

    def alloc_page(self) -> int:
        """Allocate a new page. Returns the page_id."""
        # Try free list first
        if self.free_list_head != 0:
            page_id = self.free_list_head
            # Read next free page from the freed page's header
            raw = self.read_page(page_id)
            header = parse_page_header(raw)
            self.free_list_head = header["next_page_id"]
            self._write_header()
            return page_id

        # No free pages: extend file
        page_id = self.page_count
        self._grow_to(page_id + 1)
        return page_id

    def free_page(self, page_id: int) -> None:
        """Return a page to the free list."""
        if page_id == 0:
            raise PageOutOfRangeError("Cannot free page 0 (header)")

        raw = bytearray(self.read_page(page_id))

        # Check raw page_type byte; uninitialized pages have type=0
        page_type_byte = raw[4]
        if page_type_byte == 0:
            page_type = PageType.DATA
        else:
            header = parse_page_header(bytes(raw))
            page_type = header["page_type"]

        # Update header to point to current free list head
        new_header = pack_page_header(
            page_id=page_id,
            page_type=page_type,
            slot_count=0,
            free_space=0,
            free_offset=PAGE_SIZE,
            next_page_id=self.free_list_head,
            flags=0,
        )
        raw[:len(new_header)] = new_header

        self.write_page(page_id, bytes(raw))
        self.free_list_head = page_id
        self._write_header()

    def _grow_to(self, new_count: int) -> None:
        """Extend the file to hold at least new_count pages."""
        if new_count <= self.page_count:
            return
        # Seek to end and write zero pages to extend the file
        self._file.seek(self.page_count * PAGE_SIZE)
        for _ in range(new_count - self.page_count):
            self._file.write(b"\x00" * PAGE_SIZE)
        self._file.flush()
        self.page_count = new_count
        self._write_header()

    def _init_new_database(self) -> None:
        """Initialize a fresh database file."""
        self.page_count = 1
        self.free_list_head = 0
        self.catalog_root = 0
        self.root_page_id = 0
        self._write_header()

    def _read_header(self) -> None:
        """Read and verify file header."""
        self._file.seek(0)
        raw_header = self._file.read(PAGE_SIZE)

        # Check magic
        magic = raw_header[: len(MAGIC_BYTES)]
        if magic != MAGIC_BYTES:
            raise StorageCorruptionError(
                f"Invalid magic bytes: expected {MAGIC_BYTES!r}, got {magic!r}"
            )

        offset = 8
        version = struct.unpack_from("<I", raw_header, offset)[0]

        if version == 2:
            fields = struct.unpack_from(_HEADER_FMT, raw_header, offset)
            version, page_size, page_count, free_list_head, catalog_root, root_page_id, checksum = fields
            header_data = raw_header[offset:offset + _HEADER_DATA_SIZE]
        elif version == 1:
            _V1_FMT = "<IIIIIQ"
            fields = struct.unpack_from(_V1_FMT, raw_header, offset)
            version, page_size, page_count, free_list_head, catalog_root, checksum = fields
            root_page_id = catalog_root
            _v1_data_size = struct.calcsize(_V1_FMT) - _CHECKSUM_SIZE
            header_data = raw_header[offset:offset + _v1_data_size]
        else:
            raise StorageCorruptionError(f"Unsupported version: {version}")

        if page_size != PAGE_SIZE:
            raise StorageCorruptionError(
                f"Page size mismatch: {page_size} != {PAGE_SIZE}"
            )

        computed_checksum = zlib.crc32(header_data) & 0xFFFFFFFFFFFFFFFF
        if computed_checksum != checksum:
            raise StorageCorruptionError(
                f"Checksum mismatch: computed {computed_checksum:#x}, "
                f"stored {checksum:#x}"
            )

        self.page_count = page_count
        self.free_list_head = free_list_head
        self.catalog_root = catalog_root
        self.root_page_id = root_page_id

    def _write_header(self) -> None:
        """Write header page to disk."""
        raw = bytearray(PAGE_SIZE)
        raw[: len(MAGIC_BYTES)] = MAGIC_BYTES

        offset = 8
        # Write placeholder checksum (0), then compute CRC over the non-checksum bytes
        struct.pack_into(
            _HEADER_FMT,
            raw,
            offset,
            FORMAT_VERSION,
            PAGE_SIZE,
            self.page_count,
            self.free_list_head,
            self.catalog_root,
            self.root_page_id,
            0,  # placeholder checksum
        )

        # Compute checksum over data bytes (excluding checksum field)
        header_data = raw[offset:offset + _HEADER_DATA_SIZE]
        checksum = zlib.crc32(header_data) & 0xFFFFFFFFFFFFFFFF
        struct.pack_into("<Q", raw, offset + _HEADER_DATA_SIZE, checksum)

        self._file.seek(0)
        self._file.write(bytes(raw))
        self._file.flush()
