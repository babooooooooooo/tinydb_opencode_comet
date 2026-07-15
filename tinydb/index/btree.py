# tinydb/index/btree.py
"""B-tree index implementation. Nodes map directly to storage pages."""
import struct
from tinydb.types import DataType
from tinydb.page import (
    PageType, RowId, create_empty_page, parse_page_header, pack_page_header,
)
from tinydb.constants import PAGE_SIZE, PAGE_HEADER_SIZE, MAX_FREE_SPACE


def encode_key(value, data_type: DataType) -> bytes:
    """Encode a value to comparable bytes for B-tree ordering."""
    if data_type == DataType.INTEGER:
        raw = struct.pack(">q", value)
        if value < 0:
            return bytes(~b & 0xFF for b in raw)
        else:
            return bytes(b ^ 0x80 for b in raw)
    elif data_type == DataType.BOOLEAN:
        return struct.pack(">?", value)
    elif data_type == DataType.FLOAT:
        raw = struct.pack(">d", value)
        if value < 0:
            return bytes(~b & 0xFF for b in raw)
        else:
            return bytes(b ^ 0x80 for b in raw)
    elif data_type == DataType.TEXT:
        encoded = value.encode("utf-8")
        return struct.pack(">I", len(encoded)) + encoded
    else:
        raise ValueError(f"Unsupported key type: {data_type}")


def decode_key(data: bytes, data_type: DataType):
    """Decode bytes back to a Python value."""
    if data_type == DataType.INTEGER:
        if data[0] & 0x80:
            restored = bytes(b ^ 0x80 for b in data)
            return struct.unpack(">q", restored)[0]
        else:
            restored = bytes(~b & 0xFF for b in data)
            return struct.unpack(">q", restored)[0]
    elif data_type == DataType.BOOLEAN:
        return struct.unpack(">?", data)[0]
    elif data_type == DataType.FLOAT:
        raw = data
        if raw[0] & 0x80:
            restored = bytes(b ^ 0x80 for b in raw)
            return struct.unpack(">d", restored)[0]
        else:
            restored = bytes(~b & 0xFF for b in raw)
            return struct.unpack(">d", restored)[0]
    elif data_type == DataType.TEXT:
        length = struct.unpack(">I", data[:4])[0]
        return data[4:4 + length].decode("utf-8")
    else:
        raise ValueError(f"Unsupported key type: {data_type}")


def key_size(data_type: DataType) -> int:
    """Return fixed key size for fixed-width types, estimate for TEXT."""
    if data_type == DataType.INTEGER:
        return 8
    elif data_type == DataType.BOOLEAN:
        return 1
    elif data_type == DataType.FLOAT:
        return 8
    elif data_type == DataType.TEXT:
        return 32
    return 8


NODE_FLAG_LEAF = 0x01
NODE_FLAG_INTERNAL = 0x00

NODE_HEADER_SIZE = 4
NODE_DATA_OFFSET = PAGE_HEADER_SIZE + NODE_HEADER_SIZE


def compute_max_keys(ksz: int, is_leaf: bool) -> int:
    """Compute max keys per node based on key size."""
    if is_leaf:
        return (MAX_FREE_SPACE - NODE_HEADER_SIZE - 4) // (ksz + 8)
    else:
        return (MAX_FREE_SPACE - NODE_HEADER_SIZE - 4) // (ksz + 4)


class BTreeIndex:
    """B-tree index mapping keys to RowIds. Nodes are stored as pages."""

    def __init__(self, buffer_pool, key_type: DataType, root_page: int = 0):
        self._pool = buffer_pool
        self._fm = buffer_pool._fm
        self._key_type = key_type
        self._ksz = key_size(key_type)
        self._max_keys = compute_max_keys(self._ksz, is_leaf=True)

        if root_page == 0:
            self._root_page = self._fm.alloc_page()
            self._persist_node(self._root_page, NODE_FLAG_LEAF, 0, [], [], 0)
        else:
            self._root_page = root_page

    @property
    def root_page(self) -> int:
        return self._root_page

    def insert(self, key, row_ptr: RowId) -> None:
        """Insert a key-rowptr pair into the B-tree."""
        key_bytes = encode_key(key, self._key_type)
        root_data = self._read_node(self._root_page)

        if root_data["key_count"] >= self._max_keys:
            new_root = self._fm.alloc_page()

            left_page = self._root_page
            right_page = self._fm.alloc_page()

            mid = root_data["key_count"] // 2
            all_entries = root_data["entries"]

            if root_data["is_leaf"]:
                left_entries = all_entries[:mid]
                right_entries = all_entries[mid:]
                mid_key = right_entries[0][0]

                self._persist_node(left_page, NODE_FLAG_LEAF, len(left_entries),
                                   left_entries, [], 0)
                next_leaf = root_data.get("next_leaf", 0)
                self._persist_node(right_page, NODE_FLAG_LEAF, len(right_entries),
                                   right_entries, [], next_leaf)
                self._persist_node(new_root, NODE_FLAG_INTERNAL, 1,
                                   [(mid_key, None)],
                                   [left_page, right_page], 0)
            else:
                left_entries = all_entries[:mid]
                right_entries = all_entries[mid + 1:]
                mid_key = all_entries[mid][0]
                left_children = root_data["children"][:mid + 1]
                right_children = root_data["children"][mid + 1:]

                self._persist_node(left_page, NODE_FLAG_INTERNAL, len(left_entries),
                                   left_entries, left_children, 0)
                self._persist_node(right_page, NODE_FLAG_INTERNAL, len(right_entries),
                                   right_entries, right_children, 0)
                self._persist_node(new_root, NODE_FLAG_INTERNAL, 1,
                                   [(mid_key, None)],
                                   [left_page, right_page], 0)

            self._root_page = new_root
            self._insert_nonfull(new_root, key_bytes, row_ptr)
        else:
            self._insert_nonfull(self._root_page, key_bytes, row_ptr)

    def search(self, key) -> list[RowId]:
        """Search for all RowIds matching the given key."""
        key_bytes = encode_key(key, self._key_type)
        return self._search_node(self._root_page, key_bytes)

    def range_scan(self, start, end, start_inclusive=True, end_inclusive=True) -> list[RowId]:
        """Return all RowIds with keys in [start, end] range."""
        results = []
        start_bytes = encode_key(start, self._key_type) if start is not None else None
        end_bytes = encode_key(end, self._key_type) if end is not None else None

        leaf_page = self._find_leftmost_leaf() if start is None else self._find_leaf(start_bytes)

        while leaf_page != 0:
            node = self._read_node(leaf_page)
            for entry in node["entries"]:
                k = entry[0]
                if start_bytes is not None:
                    if start_inclusive and k < start_bytes:
                        continue
                    if not start_inclusive and k <= start_bytes:
                        continue
                if end_bytes is not None:
                    if end_inclusive and k > end_bytes:
                        return results
                    if not end_inclusive and k >= end_bytes:
                        return results
                results.append(entry[1])
            leaf_page = node.get("next_leaf", 0)

        return results

    def delete(self, key, row_ptr: RowId) -> None:
        """Lazy delete: remove (key, row_ptr) from leaf."""
        key_bytes = encode_key(key, self._key_type)
        self._delete_from_node(self._root_page, key_bytes, row_ptr)

    def _insert_nonfull(self, page_id, key_bytes, row_ptr):
        """Insert into a node that is not full."""
        node = self._read_node(page_id)

        if node["is_leaf"]:
            entries = node["entries"]
            insert_pos = 0
            for i, (k, _) in enumerate(entries):
                if key_bytes < k:
                    break
                insert_pos = i + 1
            entries.insert(insert_pos, (key_bytes, row_ptr))
            self._persist_node(page_id, NODE_FLAG_LEAF, len(entries),
                               entries, [], node.get("next_leaf", 0))
        else:
            children = node["children"]
            entries = node["entries"]
            child_idx = 0
            for i, (k, _) in enumerate(entries):
                if key_bytes < k:
                    break
                child_idx = i + 1

            child_page = children[child_idx]
            child_node = self._read_node(child_page)

            if child_node["key_count"] >= self._max_keys:
                self._split_child(page_id, child_idx)
                node = self._read_node(page_id)
                entries = node["entries"]
                if child_idx < len(entries) and key_bytes > entries[child_idx][0]:
                    child_idx += 1
                child_page = node["children"][child_idx]
            self._insert_nonfull(child_page, key_bytes, row_ptr)

    def _split_child(self, parent_page, child_idx):
        """Split a full child of parent at index child_idx."""
        parent = self._read_node(parent_page)
        child_page = parent["children"][child_idx]
        child = self._read_node(child_page)

        mid = child["key_count"] // 2
        right_page = self._fm.alloc_page()

        if child["is_leaf"]:
            left_entries = child["entries"][:mid]
            right_entries = child["entries"][mid:]
            mid_key = right_entries[0][0]

            next_leaf = child.get("next_leaf", 0)
            self._persist_node(child_page, NODE_FLAG_LEAF, len(left_entries),
                               left_entries, [], 0)
            self._persist_node(right_page, NODE_FLAG_LEAF, len(right_entries),
                               right_entries, [], next_leaf)
        else:
            left_entries = child["entries"][:mid]
            right_entries = child["entries"][mid + 1:]
            mid_key = child["entries"][mid][0]
            left_children = child["children"][:mid + 1]
            right_children = child["children"][mid + 1:]

            self._persist_node(child_page, NODE_FLAG_INTERNAL, len(left_entries),
                               left_entries, left_children, 0)
            self._persist_node(right_page, NODE_FLAG_INTERNAL, len(right_entries),
                               right_entries, right_children, 0)

        parent["entries"].insert(child_idx, (mid_key, None))
        parent["children"].insert(child_idx + 1, right_page)
        self._persist_node(parent_page, NODE_FLAG_INTERNAL, len(parent["entries"]),
                           parent["entries"], parent["children"], 0)

    def _search_node(self, page_id, key_bytes) -> list[RowId]:
        """Recursively search for key in subtree rooted at page_id."""
        node = self._read_node(page_id)

        if node["is_leaf"]:
            return [ptr for k, ptr in node["entries"] if k == key_bytes]

        entries = node["entries"]
        children = node["children"]
        child_idx = 0
        for i, (k, _) in enumerate(entries):
            if key_bytes < k:
                break
            child_idx = i + 1

        if child_idx < len(children):
            return self._search_node(children[child_idx], key_bytes)
        return []

    def _delete_from_node(self, page_id, key_bytes, row_ptr):
        """Lazy delete from leaf."""
        node = self._read_node(page_id)

        if node["is_leaf"]:
            entries = [(k, ptr) for k, ptr in node["entries"]
                       if not (k == key_bytes and ptr == row_ptr)]
            self._persist_node(page_id, NODE_FLAG_LEAF, len(entries),
                               entries, [], node.get("next_leaf", 0))
        else:
            entries = node["entries"]
            children = node["children"]
            child_idx = 0
            for i, (k, _) in enumerate(entries):
                if key_bytes < k:
                    break
                child_idx = i + 1
            if child_idx < len(children):
                self._delete_from_node(children[child_idx], key_bytes, row_ptr)

    def _find_leftmost_leaf(self) -> int:
        """Traverse to leftmost leaf."""
        page_id = self._root_page
        while True:
            node = self._read_node(page_id)
            if node["is_leaf"]:
                return page_id
            if node["children"]:
                page_id = node["children"][0]
            else:
                return page_id

    def _find_leaf(self, key_bytes) -> int:
        """Find the leaf page where key should be."""
        page_id = self._root_page
        while True:
            node = self._read_node(page_id)
            if node["is_leaf"]:
                return page_id
            entries = node["entries"]
            children = node["children"]
            child_idx = 0
            for i, (k, _) in enumerate(entries):
                if key_bytes < k:
                    break
                child_idx = i + 1
            if child_idx < len(children):
                page_id = children[child_idx]
            else:
                return page_id

    def _read_node(self, page_id) -> dict:
        """Read and parse a B-tree node from a page."""
        data = self._pool.get_page(page_id)
        flags = data[PAGE_HEADER_SIZE]
        key_count = struct.unpack_from("<H", data, PAGE_HEADER_SIZE + 1)[0]
        is_leaf = (flags & NODE_FLAG_LEAF) != 0

        offset = NODE_DATA_OFFSET
        entries = []
        children = []

        if is_leaf:
            for _ in range(key_count):
                klen = struct.unpack_from("<H", data, offset)[0]
                offset += 2
                key_bytes = data[offset:offset + klen]
                offset += klen
                pid, slot = struct.unpack_from("<II", data, offset)
                offset += 8
                entries.append((key_bytes, RowId(page_id=pid, slot_index=slot)))
            next_leaf = struct.unpack_from("<I", data, offset)[0]
            return {
                "is_leaf": True,
                "key_count": key_count,
                "entries": entries,
                "next_leaf": next_leaf,
            }
        else:
            for _ in range(key_count):
                klen = struct.unpack_from("<H", data, offset)[0]
                offset += 2
                key_bytes = data[offset:offset + klen]
                offset += klen
                entries.append((key_bytes, None))
            for _ in range(key_count + 1):
                child_page = struct.unpack_from("<I", data, offset)[0]
                offset += 4
                children.append(child_page)
            return {
                "is_leaf": False,
                "key_count": key_count,
                "entries": entries,
                "children": children,
            }

    def _persist_node(self, page_id, node_flags, key_count, entries, children, next_leaf):
        """Serialize and write a B-tree node to a page."""
        data = bytearray(PAGE_SIZE)
        header = pack_page_header(
            page_id=page_id,
            page_type=PageType.INDEX,
            slot_count=0,
            free_space=0,
            free_offset=PAGE_SIZE,
            next_page_id=0,
            flags=0,
        )
        data[:PAGE_HEADER_SIZE] = header

        data[PAGE_HEADER_SIZE] = node_flags
        struct.pack_into("<H", data, PAGE_HEADER_SIZE + 1, key_count)
        data[PAGE_HEADER_SIZE + 3] = 0

        offset = NODE_DATA_OFFSET

        if node_flags & NODE_FLAG_LEAF:
            for key_bytes, row_ptr in entries:
                struct.pack_into("<H", data, offset, len(key_bytes))
                offset += 2
                data[offset:offset + len(key_bytes)] = key_bytes
                offset += len(key_bytes)
                struct.pack_into("<II", data, offset,
                                 row_ptr.page_id, row_ptr.slot_index)
                offset += 8
            struct.pack_into("<I", data, offset, next_leaf)
        else:
            for key_bytes, _ in entries:
                struct.pack_into("<H", data, offset, len(key_bytes))
                offset += 2
                data[offset:offset + len(key_bytes)] = key_bytes
                offset += len(key_bytes)
            for child_page in children:
                struct.pack_into("<I", data, offset, child_page)
                offset += 4

        self._fm.write_page(page_id, bytes(data))
        if page_id in self._pool._cache:
            self._pool.set_page_data(page_id, bytes(data))
