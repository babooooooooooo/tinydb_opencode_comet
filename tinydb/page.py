"""Slotted Page structure for tinydb storage engine.

Page layout (4096 bytes):
  Header (32 bytes):
    - page_id:      uint32
    - page_type:    uint8 (DATA=1, CATALOG=2, INDEX=3)
    - slot_count:   uint16
    - free_space:   uint16
    - free_offset:  uint16
    - next_page_id: uint32
    - flags:        uint8
    - padding:      14 bytes (reserved)
  Slot Array (slot_count * 4 bytes each):
    - offset: uint16
    - length: uint16
  Free Space
  Row Data (grows upward from page bottom)
"""
import struct
from dataclasses import dataclass
from enum import Enum
from tinydb.constants import (
    PAGE_SIZE, PAGE_HEADER_SIZE, SLOT_SIZE, MAX_FREE_SPACE,
)
from tinydb.exceptions import PageOutOfRangeError

PAGE_HEADER_FORMAT = "<IBHHHIB16x"
assert struct.calcsize(PAGE_HEADER_FORMAT) == PAGE_HEADER_SIZE, \
    f"Header size mismatch: {struct.calcsize(PAGE_HEADER_FORMAT)} != {PAGE_HEADER_SIZE}"


class PageType(Enum):
    DATA = 1
    CATALOG = 2
    INDEX = 3


@dataclass(frozen=True)
class RowId:
    page_id: int
    slot_index: int


@dataclass
class Page:
    page_id: int
    page_type: PageType
    data: bytes
    dirty: bool = False


def create_empty_page(page_id: int, page_type: PageType) -> Page:
    data = bytearray(PAGE_SIZE)
    header = pack_page_header(
        page_id=page_id,
        page_type=page_type,
        slot_count=0,
        free_space=MAX_FREE_SPACE,
        free_offset=PAGE_SIZE,
        next_page_id=0,
        flags=0,
    )
    data[:PAGE_HEADER_SIZE] = header
    return Page(
        page_id=page_id,
        page_type=page_type,
        data=bytes(data),
        dirty=False,
    )


def pack_page_header(
    page_id: int,
    page_type: PageType,
    slot_count: int,
    free_space: int,
    free_offset: int,
    next_page_id: int,
    flags: int,
) -> bytes:
    return struct.pack(
        PAGE_HEADER_FORMAT,
        page_id,
        page_type.value,
        slot_count,
        free_space,
        free_offset,
        next_page_id,
        flags,
    )


def parse_page_header(data: bytes) -> dict:
    fields = struct.unpack_from(PAGE_HEADER_FORMAT, data, 0)
    return {
        "page_id": fields[0],
        "page_type": PageType(fields[1]),
        "slot_count": fields[2],
        "free_space": fields[3],
        "free_offset": fields[4],
        "next_page_id": fields[5],
        "flags": fields[6],
    }


def _write_slot(data: bytearray, slot_idx: int, offset: int, length: int) -> None:
    slot_offset = PAGE_HEADER_SIZE + slot_idx * SLOT_SIZE
    struct.pack_into("<HH", data, slot_offset, offset, length)


def _read_slot(data: bytes, slot_idx: int) -> tuple[int, int]:
    slot_offset = PAGE_HEADER_SIZE + slot_idx * SLOT_SIZE
    return struct.unpack_from("<HH", data, slot_offset)


def get_free_space(page: Page) -> int:
    header = parse_page_header(page.data)
    return header["free_space"]


def insert_row_into_page(page: Page, row_data: bytes) -> int:
    data = bytearray(page.data)
    header = parse_page_header(bytes(data))

    row_len = len(row_data)
    needed = row_len + SLOT_SIZE

    if needed > header["free_space"]:
        raise PageOutOfRangeError(
            f"Not enough space: need {needed}, have {header['free_space']}"
        )

    slot_idx = header["slot_count"]
    new_free_offset = header["free_offset"] - row_len

    data[new_free_offset:new_free_offset + row_len] = row_data
    _write_slot(data, slot_idx, new_free_offset, row_len)

    new_header = pack_page_header(
        page_id=header["page_id"],
        page_type=header["page_type"],
        slot_count=header["slot_count"] + 1,
        free_space=header["free_space"] - needed,
        free_offset=new_free_offset,
        next_page_id=header["next_page_id"],
        flags=header["flags"],
    )
    data[:PAGE_HEADER_SIZE] = new_header

    page.data = bytes(data)
    page.dirty = True
    return slot_idx


def get_row_from_page(page: Page, slot_idx: int) -> bytes | None:
    data = page.data
    header = parse_page_header(data)

    if slot_idx >= header["slot_count"]:
        return None

    offset, length = _read_slot(data, slot_idx)

    if length == 0:
        return None

    return data[offset:offset + length]


def delete_row_from_page(page: Page, slot_idx: int) -> None:
    data = bytearray(page.data)
    header = parse_page_header(bytes(data))

    if slot_idx >= header["slot_count"]:
        raise PageOutOfRangeError(f"Slot {slot_idx} out of range")

    _write_slot(data, slot_idx, 0, 0)

    new_header = pack_page_header(
        page_id=header["page_id"],
        page_type=header["page_type"],
        slot_count=header["slot_count"],
        free_space=header["free_space"],
        free_offset=header["free_offset"],
        next_page_id=header["next_page_id"],
        flags=header["flags"],
    )
    data[:PAGE_HEADER_SIZE] = new_header

    page.data = bytes(data)
    page.dirty = True


def get_slot_count(page: Page) -> int:
    """Get slot count from page header without creating a full dict."""
    return struct.unpack_from("<H", page.data, 5)[0]


def get_all_rows_from_page(page: Page) -> list[bytes]:
    result = []
    count = get_slot_count(page)
    for i in range(count):
        row = get_row_from_page(page, i)
        if row is not None:
            result.append(row)
    return result
