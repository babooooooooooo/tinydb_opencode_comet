---
change: tinydb-index-txn
design-doc: docs/superpowers/specs/2026-07-15-tinydb-index-txn-design.md
base-ref: e57b8135ac3360f61ca8e560c3c1b4cec648f988
---

# tinydb-index-txn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 tinydb 添加 B-tree 索引、Shadow Paging 事务、索引增强执行器、Database 统一入口和 CLI REPL。

**Architecture:** 在存储引擎之上构建索引层（B-tree 节点映射到存储页）、事务层（Shadow BufferPool 包装实现 CoW）、SQL 执行层（IndexScan 算子）和 Database 统一入口，最终通过 REPL 提供交互界面。

**Tech Stack:** Python 3.10+, struct, readline, pytest

## Global Constraints

- 文件格式 version bump: 1 → 2（添加 root_page_id 字段）
- TEXT 键使用 length-prefix 编码（4 字节长度 + UTF-8 字节）
- != 操作符使用全表扫描 + Filter 回退
- B-tree delete: lazy（不合并）
- Shadow Paging: CoW via ShadowBufferPool wrapping BufferPool
- 所有测试使用 pytest，fixture 复用 `tmp_path`
- 代码风格与现有存储引擎一致（中文注释、dataclass、类型注解）
- 不修改已 archived 的 storage 层文件（file_manager.py 除外，需添加 root_page_id）

---

## File Structure

```
tinydb/
├── index/
│   ├── __init__.py
│   ├── btree.py          # BTreeIndex, BTreeNode, key encoding
│   └── index_manager.py  # IndexManager, IndexMeta
├── transaction/
│   ├── __init__.py
│   ├── shadow_paging.py  # ShadowBufferPool, Transaction
│   └── txn_manager.py    # TransactionManager
├── cli/
│   ├── __init__.py
│   └── repl.py           # REPL
├── sql/
│   ├── __init__.py
│   └── executor.py       # IndexScanOperator, Planner
├── database.py           # Database, QueryResult
└── file_manager.py       # MODIFY: add root_page_id to header

tests/
├── test_btree.py
├── test_index_manager.py
├── test_shadow_paging.py
├── test_transaction.py
├── test_database.py
├── test_repl.py
├── test_executor.py
└── test_integration.py   # MODIFY: add integration tests
```

---

## Interface Contracts

### Task 1 produces (File Header Extension)
- `FileManager.root_page_id: int` — 新属性，B-tree 根页号
- `FileManager._HEADER_FMT = "<IIIIIIQ"` — 新格式（添加 root_page_id）
- `FORMAT_VERSION = 2` — 版本号
- Backward compat: 读取 version=1 时 root_page_id 默认为 catalog_root

### Task 2 produces (B-tree Core)
- `BTreeIndex` class:
  - `__init__(self, buffer_pool, root_page: int, key_type: DataType)`
  - `insert(key, row_ptr: RowId) -> None`
  - `search(key) -> list[RowId]`
  - `range_scan(start, end, start_inclusive=True, end_inclusive=True) -> list[RowId]`
  - `delete(key, row_ptr: RowId) -> None`
  - `root_page: int` property
- `encode_key(value, data_type: DataType) -> bytes`
- `decode_key(data: bytes, data_type: DataType) -> value`

### Task 3 produces (Index Manager)
- `IndexMeta` dataclass: `name, table_name, column_name, column_type, root_page`
- `IndexManager` class:
  - `create_index(table_name, column_name, name) -> IndexMeta`
  - `drop_index(name) -> None`
  - `get_index(table_name, column_name) -> IndexMeta | None`
  - `after_insert(table_name, row_ptr, row) -> None`
  - `after_delete(table_name, row_ptr, old_row) -> None`
  - `after_update(table_name, row_ptr, old_row, new_row) -> None`
  - `find_matching_index(table_name, where_clause) -> IndexMeta | None`

### Task 4 produces (Shadow Paging)
- `Transaction` dataclass: `txn_id, state, shadow_pages, snapshot_root, new_root`
- `ShadowBufferPool` class:
  - `get_page(page_id: int) -> bytes`
  - `set_page_data(page_id: int, data: bytes) -> None`
  - `mark_dirty(page_id: int) -> None`
  - `flush() -> None`

### Task 5 produces (Transaction Manager)
- `TransactionManager` class:
  - `begin() -> Transaction`
  - `commit() -> None`
  - `rollback() -> None`
  - `ensure_shadow(page_id: int) -> int`
  - `has_active_txn() -> bool`

### Task 6 produces (Index-Aware Executor)
- `IndexScanOperator` class:
  - `__init__(table, index_meta, condition)`
  - `execute(buffer_pool) -> Iterator[tuple[RowId, list]]`
- `Planner` class with `_choose_scan(table, where_clause)` method

### Task 7 produces (Database)
- `QueryResult` dataclass: `columns, rows, row_count`
- `Database` class:
  - `__init__(path: str)`
  - `execute(sql: str) -> QueryResult`
  - `commit() -> None`
  - `rollback() -> None`
  - `close() -> None`
  - `__enter__ / __exit__`

### Task 8 produces (CLI REPL)
- `REPL` class:
  - `__init__(db: Database)`
  - `run() -> None`

---

## Task 1: File Header Extension (root_page_id + version bump)

**Files:**
- Modify: `tinydb/file_manager.py`
- Modify: `tinydb/constants.py`
- Test: `tests/test_file_header_ext.py`

**Prerequisites:** None (foundational task)

**Produces:** FileManager with root_page_id support, version 2 format

- [ ] **Step 1: Write the failing test**

```python
# tests/test_file_header_ext.py
import os
import pytest
from tinydb.file_manager import FileManager
from tinydb.constants import FORMAT_VERSION

class TestFileHeaderExtension:
    def test_new_db_has_root_page_id(self, tmp_path):
        """新数据库创建后 root_page_id 可读写"""
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        assert fm.root_page_id == 0
        fm.root_page_id = 5
        fm._write_header()
        fm.close()

        fm2 = FileManager(db_path)
        fm2.open()
        assert fm2.root_page_id == 5
        fm2.close()

    def test_version_bumped_to_2(self, tmp_path):
        """版本号已升级到 2"""
        assert FORMAT_VERSION == 2

    def test_backward_compat_v1(self, tmp_path):
        """向后兼容：读取 version=1 的数据库文件"""
        db_path = str(tmp_path / "v1.db")
        # 手动写入 version=1 的 header
        import struct, zlib
        from tinydb.constants import MAGIC_BYTES, PAGE_SIZE
        raw = bytearray(PAGE_SIZE)
        raw[:8] = MAGIC_BYTES
        # v1 format: version(I) page_size(I) page_count(I) free_list_head(I) catalog_root(I) checksum(Q)
        _V1_FMT = "<IIIIIQ"
        offset = 8
        struct.pack_into(_V1_FMT, raw, offset, 1, PAGE_SIZE, 1, 0, 0, 0)
        header_data = raw[offset:offset + struct.calcsize(_V1_FMT) - 8]
        checksum = zlib.crc32(header_data) & 0xFFFFFFFFFFFFFFFF
        struct.pack_into("<Q", raw, offset + struct.calcsize(_V1_FMT) - 8, checksum)
        with open(db_path, "wb") as f:
            f.write(bytes(raw))

        fm = FileManager(db_path)
        fm.open()
        assert fm.root_page_id == 0  # v1 defaults to 0
        fm.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_file_header_ext.py -v`
Expected: FAIL — `FileManager` has no `root_page_id` attribute

- [ ] **Step 3: Modify constants.py**

```python
# tinydb/constants.py — change line 15
FORMAT_VERSION = 2
```

- [ ] **Step 4: Modify file_manager.py**

```python
# tinydb/file_manager.py — changes:

# 1. Update _HEADER_FMT (line 28)
_HEADER_FMT = "<IIIIIIQ"
#    version(I) page_size(I) page_count(I) free_list_head(I) catalog_root(I) root_page_id(I) checksum(Q)

# 2. Add root_page_id attribute in __init__ (after line 41)
self.root_page_id = 0

# 3. Update _init_new_database (line 158-159)
def _init_new_database(self) -> None:
    self.page_count = 1
    self.free_list_head = 0
    self.catalog_root = 0
    self.root_page_id = 0
    self._write_header()

# 4. Update _read_header — replace version check with backward compat
def _read_header(self) -> None:
    self._file.seek(0)
    raw_header = self._file.read(PAGE_SIZE)

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
    elif version == 1:
        # Backward compat: v1 header has no root_page_id
        _V1_FMT = "<IIIIIQ"
        fields = struct.unpack_from(_V1_FMT, raw_header, offset)
        version, page_size, page_count, free_list_head, catalog_root, checksum = fields
        root_page_id = catalog_root  # default to catalog_root
    else:
        raise StorageCorruptionError(f"Unsupported version: {version}")

    if page_size != PAGE_SIZE:
        raise StorageCorruptionError(f"Page size mismatch: {page_size} != {PAGE_SIZE}")

    # Verify checksum
    if version == 2:
        header_data = raw_header[offset:offset + _HEADER_DATA_SIZE]
    else:
        _V1_META_SIZE = struct.calcsize("<IIIIIQ")
        header_data = raw_header[offset:offset + _V1_META_SIZE - 8]
    computed_checksum = zlib.crc32(header_data) & 0xFFFFFFFFFFFFFFFF
    if computed_checksum != checksum:
        raise StorageCorruptionError(
            f"Checksum mismatch: computed {computed_checksum:#x}, stored {checksum:#x}"
        )

    self.page_count = page_count
    self.free_list_head = free_list_head
    self.catalog_root = catalog_root
    self.root_page_id = root_page_id

# 5. Update _write_header (line 201-227)
def _write_header(self) -> None:
    raw = bytearray(PAGE_SIZE)
    raw[: len(MAGIC_BYTES)] = MAGIC_BYTES

    offset = 8
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

    header_data = raw[offset:offset + _HEADER_DATA_SIZE]
    checksum = zlib.crc32(header_data) & 0xFFFFFFFFFFFFFFFF
    struct.pack_into("<Q", raw, offset + _HEADER_DATA_SIZE, checksum)

    self._file.seek(0)
    self._file.write(bytes(raw))
    self._file.flush()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_file_header_ext.py -v`
Expected: PASS

- [ ] **Step 6: Run existing tests to verify no regression**

Run: `pytest tests/ -v`
Expected: All existing tests pass

- [ ] **Step 7: Commit**

```bash
git add tinydb/file_manager.py tinydb/constants.py tests/test_file_header_ext.py
git commit -m "feat: add root_page_id to file header, bump version to 2"
```

---

## Task 2: B-tree Core — Node Structure & Key Encoding

**Files:**
- Create: `tinydb/index/__init__.py`
- Create: `tinydb/index/btree.py`
- Test: `tests/test_btree.py`

**Prerequisites:** Task 1

**Produces:** `BTreeIndex` class with key encoding, insert, search, range_scan, delete

- [ ] **Step 1: Write the failing test**

```python
# tests/test_btree.py
import pytest
from tinydb.index.btree import BTreeIndex, encode_key, decode_key
from tinydb.types import DataType
from tinydb.page import RowId
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool


@pytest.fixture
def env(tmp_path):
    db_path = str(tmp_path / "test.db")
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    yield fm, pool
    fm.close()


class TestKeyEncoding:
    def test_integer_encoding(self):
        data = encode_key(42, DataType.INTEGER)
        assert decode_key(data, DataType.INTEGER) == 42
        # Negative numbers sort correctly
        neg = encode_key(-1, DataType.INTEGER)
        zero = encode_key(0, DataType.INTEGER)
        pos = encode_key(1, DataType.INTEGER)
        assert neg < zero < pos

    def test_float_encoding(self):
        data = encode_key(3.14, DataType.FLOAT)
        assert abs(decode_key(data, DataType.FLOAT) - 3.14) < 1e-10

    def test_boolean_encoding(self):
        assert decode_key(encode_key(True, DataType.BOOLEAN), DataType.BOOLEAN) is True
        assert decode_key(encode_key(False, DataType.BOOLEAN), DataType.BOOLEAN) is False

    def test_text_encoding(self):
        data = encode_key("hello", DataType.TEXT)
        assert decode_key(data, DataType.TEXT) == "hello"


class TestBTreeIndex:
    def test_empty_tree(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        assert btree.search(42) == []

    def test_insert_and_search(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        btree.insert(10, RowId(page_id=1, slot_index=0))
        btree.insert(20, RowId(page_id=1, slot_index=1))
        btree.insert(30, RowId(page_id=2, slot_index=0))

        result = btree.search(20)
        assert len(result) == 1
        assert result[0].page_id == 1
        assert result[0].slot_index == 1

    def test_search_not_found(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        btree.insert(10, RowId(page_id=1, slot_index=0))
        assert btree.search(99) == []

    def test_range_scan(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        for i in range(1, 11):
            btree.insert(i, RowId(page_id=1, slot_index=i-1))

        results = btree.range_scan(start=3, end=7)
        assert len(results) == 5
        keys_found = sorted([r.slot_index + 1 for r in results])
        assert keys_found == [3, 4, 5, 6, 7]

    def test_delete(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        btree.insert(10, RowId(page_id=1, slot_index=0))
        btree.delete(10, RowId(page_id=1, slot_index=0))
        assert btree.search(10) == []

    def test_persistence(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        btree.insert(42, RowId(page_id=5, slot_index=3))
        root_page = btree.root_page
        pool.flush()

        # Reopen
        btree2 = BTreeIndex(pool, key_type=DataType.INTEGER, root_page=root_page)
        result = btree2.search(42)
        assert len(result) == 1
        assert result[0].page_id == 5
        assert result[0].slot_index == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_btree.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create `tinydb/index/__init__.py`**

```python
# tinydb/index/__init__.py
from tinydb.index.btree import BTreeIndex, encode_key, decode_key
from tinydb.index.index_manager import IndexManager, IndexMeta

__all__ = ["BTreeIndex", "encode_key", "decode_key", "IndexManager", "IndexMeta"]
```

- [ ] **Step 4: Implement `tinydb/index/btree.py`**

```python
# tinydb/index/btree.py
"""B-tree index implementation. Nodes map directly to storage pages."""
import struct
import math
from dataclasses import dataclass, field
from tinydb.types import DataType
from tinydb.page import (
    PageType, RowId, create_empty_page, parse_page_header, pack_page_header,
)
from tinydb.constants import PAGE_SIZE, PAGE_HEADER_SIZE, MAX_FREE_SPACE


# ── Key encoding ──────────────────────────────────────────────

def encode_key(value, data_type: DataType) -> bytes:
    """Encode a value to comparable bytes for B-tree ordering."""
    if data_type == DataType.INTEGER:
        return struct.pack(">q", value)  # big-endian signed int64
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
        return struct.unpack(">q", data)[0]
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
        return 32  # estimate for max_keys calculation
    return 8


# ── Node layout constants ──────────────────────────────────────

NODE_FLAG_LEAF = 0x01
NODE_FLAG_INTERNAL = 0x00

# After page header (32 bytes):
# node_flags(1) + key_count(2) + padding(1) = 4 bytes
NODE_HEADER_SIZE = 4
NODE_DATA_OFFSET = PAGE_HEADER_SIZE + NODE_HEADER_SIZE  # 36


def compute_max_keys(key_size: int, is_leaf: bool) -> int:
    """Compute max keys per node based on key size."""
    if is_leaf:
        return (MAX_FREE_SPACE - NODE_HEADER_SIZE - 4) // (key_size + 8)
    else:
        return (MAX_FREE_SPACE - NODE_HEADER_SIZE - 4) // (key_size + 4)


# ── B-tree Index ──────────────────────────────────────────────

class BTreeIndex:
    """B-tree index mapping keys to RowIds. Nodes are stored as pages."""

    def __init__(self, buffer_pool, key_type: DataType, root_page: int = 0):
        self._pool = buffer_pool
        self._fm = buffer_pool._fm
        self._key_type = key_type
        self._ksz = key_size(key_type)
        self._max_keys = compute_max_keys(self._ksz, is_leaf=True)
        self._min_keys = self._max_keys // 2

        if root_page == 0:
            # Create new empty tree (single leaf node)
            self._root_page = self._fm.alloc_page()
            self._init_leaf_node(self._root_page)
            self._persist_node(self._root_page, NODE_FLAG_LEAF, 0, [], [], 0)
        else:
            self._root_page = root_page

    @property
    def root_page(self) -> int:
        return self._root_page

    # ── Public API ────────────────────────────────────────────

    def insert(self, key, row_ptr: RowId) -> None:
        """Insert a key-rowptr pair into the B-tree."""
        key_bytes = encode_key(key, self._key_type)
        root_data = self._read_node(self._root_page)

        if root_data["key_count"] == self._max_keys:
            # Root is full: split
            new_root = self._fm.alloc_page()
            self._init_leaf_node(new_root)

            # Copy root info to new left child
            left_page = self._root_page
            right_page = self._fm.alloc_page()
            self._init_leaf_node(right_page)

            # Split old root into left + right
            mid = root_data["key_count"] // 2
            all_entries = root_data["entries"]  # list of (key_bytes, row_ptr)

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
            # Re-insert into new tree structure
            self._insert_nonfull(new_root, key_bytes, row_ptr, key)
        else:
            self._insert_nonfull(self._root_page, key_bytes, row_ptr, key)

    def search(self, key) -> list[RowId]:
        """Search for all RowIds matching the given key."""
        key_bytes = encode_key(key, self._key_type)
        return self._search_node(self._root_page, key_bytes)

    def range_scan(self, start, end, start_inclusive=True, end_inclusive=True) -> list[RowId]:
        """Return all RowIds with keys in [start, end] range."""
        results = []
        start_bytes = encode_key(start, self._key_type) if start is not None else None
        end_bytes = encode_key(end, self._key_type) if end is not None else None

        # Find starting leaf
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

    # ── Internal methods ──────────────────────────────────────

    def _insert_nonfull(self, page_id, key_bytes, row_ptr, raw_key):
        """Insert into a node that is not full."""
        node = self._read_node(page_id)

        if node["is_leaf"]:
            # Insert into leaf maintaining sorted order
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
            # Find child to descend into
            children = node["children"]
            entries = node["entries"]
            child_idx = 0
            for i, (k, _) in enumerate(entries):
                if key_bytes < k:
                    break
                child_idx = i + 1

            child_page = children[child_idx]
            child_node = self._read_node(child_page)

            if child_node["key_count"] == self._max_keys:
                # Split child
                self._split_child(page_id, child_idx)
                # After split, re-read parent and decide which child
                node = self._read_node(page_id)
                entries = node["entries"]
                if child_idx < len(entries) and key_bytes > entries[child_idx][0]:
                    child_idx += 1
                child_page = node["children"][child_idx]
            self._insert_nonfull(child_page, key_bytes, row_ptr, raw_key)

    def _split_child(self, parent_page, child_idx):
        """Split a full child of parent at index child_idx."""
        parent = self._read_node(parent_page)
        child_page = parent["children"][child_idx]
        child = self._read_node(child_page)

        mid = child["key_count"] // 2
        right_page = self._fm.alloc_page()
        self._init_leaf_node(right_page)

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

        # Insert mid_key into parent
        parent["entries"].insert(child_idx, (mid_key, None))
        parent["children"].insert(child_idx + 1, right_page)
        self._persist_node(parent_page, NODE_FLAG_INTERNAL, len(parent["entries"]),
                           parent["entries"], parent["children"], 0)

    def _search_node(self, page_id, key_bytes) -> list[RowId]:
        """Recursively search for key in subtree rooted at page_id."""
        node = self._read_node(page_id)

        if node["is_leaf"]:
            return [ptr for k, ptr in node["entries"] if k == key_bytes]

        # Internal node: find child
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
            # Navigate to leaf
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

    # ── Serialization ─────────────────────────────────────────

    def _init_leaf_node(self, page_id):
        """Initialize a page as empty leaf."""
        page = create_empty_page(page_id, PageType.INDEX)
        self._fm.write_page(page_id, page.data)

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
                page_id_val, slot_idx = struct.unpack_from("<II", data, offset)
                offset += 8
                entries.append((key_bytes, RowId(page_id=page_id_val, slot_index=slot_idx)))
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
        # Page header
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

        # Node header
        data[PAGE_HEADER_SIZE] = node_flags
        struct.pack_into("<H", data, PAGE_HEADER_SIZE + 1, key_count)
        data[PAGE_HEADER_SIZE + 3] = 0  # padding

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

        self._pool.set_page_data(page_id, bytes(data))
        self._pool.mark_dirty(page_id)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_btree.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tinydb/index/__init__.py tinydb/index/btree.py tests/test_btree.py
git commit -m "feat: add B-tree index with key encoding, insert, search, range_scan, delete"
```

---

## Task 3: Index Manager

**Files:**
- Create: `tinydb/index/index_manager.py`
- Test: `tests/test_index_manager.py`

**Prerequisites:** Task 2

**Produces:** `IndexManager` with create/drop/get_index and DML hooks

- [ ] **Step 1: Write the failing test**

```python
# tests/test_index_manager.py
import pytest
from tinydb.index.index_manager import IndexManager, IndexMeta
from tinydb.index.btree import BTreeIndex
from tinydb.types import DataType, ColumnDef
from tinydb.page import RowId
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog


@pytest.fixture
def db_env(tmp_path):
    db_path = str(tmp_path / "test.db")
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    cat = Catalog(fm, pool)
    cat.load()

    # Create a test table
    columns = [
        ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
        ColumnDef(name="name", data_type=DataType.TEXT),
        ColumnDef(name="age", data_type=DataType.INTEGER),
    ]
    cat.create_table("users", columns, pk="id")
    tbl = cat.get_table("users")

    yield fm, pool, cat, tbl
    fm.close()


class TestIndexManager:
    def test_create_index(self, db_env):
        fm, pool, cat, tbl = db_env
        imgr = IndexManager(cat, fm, pool)
        meta = imgr.create_index("users", "age", "idx_users_age")
        assert meta.name == "idx_users_age"
        assert meta.table_name == "users"
        assert meta.column_name == "age"
        assert meta.root_page > 0

    def test_drop_index(self, db_env):
        fm, pool, cat, tbl = db_env
        imgr = IndexManager(cat, fm, pool)
        imgr.create_index("users", "age", "idx_users_age")
        imgr.drop_index("idx_users_age")
        assert imgr.get_index("users", "age") is None

    def test_get_index(self, db_env):
        fm, pool, cat, tbl = db_env
        imgr = IndexManager(cat, fm, pool)
        imgr.create_index("users", "age", "idx_users_age")
        meta = imgr.get_index("users", "age")
        assert meta is not None
        assert meta.name == "idx_users_age"

    def test_after_insert(self, db_env):
        fm, pool, cat, tbl = db_env
        imgr = IndexManager(cat, fm, pool)
        imgr.create_index("users", "age", "idx_users_age")

        rid = tbl.insert(pool, [1, "Alice", 30])
        imgr.after_insert("users", rid, [1, "Alice", 30])

        meta = imgr.get_index("users", "age")
        btree = imgr._btrees[meta.name]
        results = btree.search(30)
        assert len(results) == 1
        assert results[0].page_id == rid.page_id

    def test_after_delete(self, db_env):
        fm, pool, cat, tbl = db_env
        imgr = IndexManager(cat, fm, pool)
        imgr.create_index("users", "age", "idx_users_age")

        rid = tbl.insert(pool, [1, "Alice", 30])
        imgr.after_insert("users", rid, [1, "Alice", 30])
        imgr.after_delete("users", rid, [1, "Alice", 30])

        meta = imgr.get_index("users", "age")
        btree = imgr._btrees[meta.name]
        assert btree.search(30) == []

    def test_after_update(self, db_env):
        fm, pool, cat, tbl = db_env
        imgr = IndexManager(cat, fm, pool)
        imgr.create_index("users", "age", "idx_users_age")

        rid = tbl.insert(pool, [1, "Alice", 30])
        imgr.after_insert("users", rid, [1, "Alice", 30])

        # Update age from 30 to 31
        tbl.update(pool, rid, [1, "Alice", 31])
        imgr.after_update("users", rid, [1, "Alice", 30], [1, "Alice", 31])

        meta = imgr.get_index("users", "age")
        btree = imgr._btrees[meta.name]
        assert btree.search(30) == []
        assert len(btree.search(31)) == 1

    def test_find_matching_index(self, db_env):
        fm, pool, cat, tbl = db_env
        imgr = IndexManager(cat, fm, pool)
        imgr.create_index("users", "age", "idx_users_age")

        # Mock where clause
        class MockCond:
            column = "age"
            op = "="
            value = 30

        meta = imgr.find_matching_index("users", MockCond())
        assert meta is not None
        assert meta.name == "idx_users_age"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_index_manager.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `tinydb/index/index_manager.py`**

```python
# tinydb/index/index_manager.py
"""Index Manager: manages index metadata and auto-updates on DML."""
import json
from dataclasses import dataclass
from tinydb.types import DataType, ColumnDef
from tinydb.page import RowId
from tinydb.index.btree import BTreeIndex


@dataclass
class IndexMeta:
    name: str
    table_name: str
    column_name: str
    column_type: DataType
    root_page: int


class IndexManager:
    """Manages index lifecycle and DML hooks."""

    def __init__(self, catalog, file_manager, buffer_pool):
        self._catalog = catalog
        self._fm = file_manager
        self._pool = buffer_pool
        self._indexes: dict[str, IndexMeta] = {}
        self._table_indexes: dict[str, dict[str, str]] = {}
        self._btrees: dict[str, BTreeIndex] = {}
        self._load_indexes()

    def create_index(self, table_name: str, column_name: str, name: str) -> IndexMeta:
        """Create a new index on a table column."""
        if name in self._indexes:
            raise ValueError(f"Index '{name}' already exists")

        # Get column info from catalog
        table_meta = self._catalog._tables.get(table_name)
        if table_meta is None:
            raise ValueError(f"Table '{table_name}' not found")

        column = None
        for col in table_meta.columns:
            if col.name == column_name:
                column = col
                break
        if column is None:
            raise ValueError(f"Column '{column_name}' not found in table '{table_name}'")

        # Create B-tree
        btree = BTreeIndex(self._pool, key_type=column.data_type)
        meta = IndexMeta(
            name=name,
            table_name=table_name,
            column_name=column_name,
            column_type=column.data_type,
            root_page=btree.root_page,
        )
        self._indexes[name] = meta
        self._btrees[name] = btree

        # Register in table→column mapping
        if table_name not in self._table_indexes:
            self._table_indexes[table_name] = {}
        self._table_indexes[table_name][column_name] = name

        self._save_indexes()
        return meta

    def drop_index(self, name: str) -> None:
        """Drop an index by name."""
        if name not in self._indexes:
            raise ValueError(f"Index '{name}' not found")

        meta = self._indexes[name]
        del self._indexes[name]
        del self._btrees[name]

        if meta.table_name in self._table_indexes:
            col_map = self._table_indexes[meta.table_name]
            if meta.column_name in col_map:
                del col_map[meta.column_name]

        self._save_indexes()

    def get_index(self, table_name: str, column_name: str) -> IndexMeta | None:
        """Get index metadata for a table column."""
        index_name = self._table_indexes.get(table_name, {}).get(column_name)
        if index_name:
            return self._indexes.get(index_name)
        return None

    def after_insert(self, table_name: str, row_ptr: RowId, row: list) -> None:
        """Update all indexes after INSERT."""
        col_map = self._table_indexes.get(table_name, {})
        if not col_map:
            return

        table_meta = self._catalog._tables.get(table_name)
        if table_meta is None:
            return

        for col_idx, col in enumerate(table_meta.columns):
            index_name = col_map.get(col.name)
            if index_name:
                btree = self._btrees[index_name]
                key = row[col_idx]
                if key is not None:
                    btree.insert(key, row_ptr)

    def after_delete(self, table_name: str, row_ptr: RowId, old_row: list) -> None:
        """Remove index entries before DELETE."""
        col_map = self._table_indexes.get(table_name, {})
        if not col_map:
            return

        table_meta = self._catalog._tables.get(table_name)
        if table_meta is None:
            return

        for col_idx, col in enumerate(table_meta.columns):
            index_name = col_map.get(col.name)
            if index_name:
                btree = self._btrees[index_name]
                key = old_row[col_idx]
                if key is not None:
                    btree.delete(key, row_ptr)

    def after_update(self, table_name: str, row_ptr: RowId, old_row: list, new_row: list) -> None:
        """Update indexes after UPDATE for changed columns."""
        col_map = self._table_indexes.get(table_name, {})
        if not col_map:
            return

        table_meta = self._catalog._tables.get(table_name)
        if table_meta is None:
            return

        for col_idx, col in enumerate(table_meta.columns):
            if old_row[col_idx] == new_row[col_idx]:
                continue
            index_name = col_map.get(col.name)
            if index_name:
                btree = self._btrees[index_name]
                if old_row[col_idx] is not None:
                    btree.delete(old_row[col_idx], row_ptr)
                if new_row[col_idx] is not None:
                    btree.insert(new_row[col_idx], row_ptr)

    def find_matching_index(self, table_name: str, where_clause) -> IndexMeta | None:
        """Find an index matching a WHERE clause condition."""
        col_map = self._table_indexes.get(table_name, {})
        if not col_map or where_clause is None:
            return None

        col_name = getattr(where_clause, "column", None)
        if col_name and col_name in col_map:
            index_name = col_map[col_name]
            return self._indexes.get(index_name)
        return None

    def _load_indexes(self):
        """Load index metadata from catalog."""
        # Check if catalog has indexes data
        raw_data = getattr(self._catalog, '_indexes_data', None)
        if raw_data:
            for item in raw_data:
                meta = IndexMeta(
                    name=item["name"],
                    table_name=item["table"],
                    column_name=item["column"],
                    column_type=DataType(item.get("column_type", "INTEGER")),
                    root_page=item["root_page"],
                )
                self._indexes[meta.name] = meta
                self._btrees[meta.name] = BTreeIndex(
                    self._pool, key_type=meta.column_type, root_page=meta.root_page
                )
                if meta.table_name not in self._table_indexes:
                    self._table_indexes[meta.table_name] = {}
                self._table_indexes[meta.table_name][meta.column_name] = meta.name

    def _save_indexes(self):
        """Persist index metadata to catalog."""
        data = [
            {
                "name": meta.name,
                "table": meta.table_name,
                "column": meta.column_name,
                "column_type": meta.column_type.value,
                "root_page": meta.root_page,
            }
            for meta in self._indexes.values()
        ]
        self._catalog._indexes_data = data
        self._catalog.save()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_index_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tinydb/index/index_manager.py tests/test_index_manager.py
git commit -m "feat: add IndexManager with create/drop/get and DML hooks"
```

---

## Task 4: Shadow Paging

**Files:**
- Create: `tinydb/transaction/__init__.py`
- Create: `tinydb/transaction/shadow_paging.py`
- Test: `tests/test_shadow_paging.py`

**Prerequisites:** Task 1

**Produces:** `Transaction`, `ShadowBufferPool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_shadow_paging.py
import pytest
from tinydb.transaction.shadow_paging import Transaction, ShadowBufferPool
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.page import create_empty_page, PageType


@pytest.fixture
def env(tmp_path):
    db_path = str(tmp_path / "test.db")
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    yield fm, pool
    fm.close()


class TestShadowPaging:
    def test_cow_creates_shadow_page(self, env):
        fm, pool = env
        # Write a page
        page = create_empty_page(1, PageType.DATA)
        fm.write_page(1, page.data)
        fm.page_count = 2

        txn = Transaction(txn_id=1, state="active", shadow_pages={},
                          snapshot_root=0, new_root=0)
        shadow = ShadowBufferPool(pool, txn, fm)

        # First write triggers CoW
        shadow.set_page_data(1, page.data)
        assert 1 in txn.shadow_pages
        assert txn.shadow_pages[1] != 1  # shadow page is different

    def test_read_sees_shadow(self, env):
        fm, pool = env
        page = create_empty_page(1, PageType.DATA)
        fm.write_page(1, page.data)
        fm.page_count = 2

        txn = Transaction(txn_id=1, state="active", shadow_pages={},
                          snapshot_root=0, new_root=0)
        shadow = ShadowBufferPool(pool, txn, fm)

        # Write through shadow
        modified = bytearray(page.data)
        modified[40] = 0xAB  # modify a byte
        shadow.set_page_data(1, bytes(modified))

        # Read should see modified data
        result = shadow.get_page(1)
        assert result[40] == 0xAB

    def test_rollback_releases_shadow_pages(self, env):
        fm, pool = env
        page = create_empty_page(1, PageType.DATA)
        fm.write_page(1, page.data)
        fm.page_count = 2

        txn = Transaction(txn_id=1, state="active", shadow_pages={},
                          snapshot_root=0, new_root=0)
        shadow = ShadowBufferPool(pool, txn, fm)
        shadow.set_page_data(1, page.data)

        shadow_id = txn.shadow_pages[1]
        shadow.rollback()

        # Shadow page should be freed
        assert txn.state == "aborted"
        assert len(txn.shadow_pages) == 0

    def test_commit_flushes_and_updates_root(self, env):
        fm, pool = env
        page = create_empty_page(1, PageType.DATA)
        fm.write_page(1, page.data)
        fm.page_count = 2

        txn = Transaction(txn_id=1, state="active", shadow_pages={},
                          snapshot_root=0, new_root=0)
        shadow = ShadowBufferPool(pool, txn, fm)
        shadow.set_page_data(1, page.data)

        new_root = 5
        txn.new_root = new_root
        shadow.commit()

        assert txn.state == "committed"
        assert fm.root_page_id == new_root
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_shadow_paging.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `tinydb/transaction/shadow_paging.py`**

```python
# tinydb/transaction/shadow_paging.py
"""Shadow Paging: page-level copy-on-write for transaction atomicity."""
import os
from dataclasses import dataclass, field


@dataclass
class Transaction:
    txn_id: int
    state: str  # "active" | "committed" | "aborted"
    shadow_pages: dict[int, int]  # orig_page_id → shadow_page_id
    snapshot_root: int
    new_root: int


class ShadowBufferPool:
    """BufferPool wrapper that intercepts reads/writes for CoW."""

    def __init__(self, buffer_pool, txn, file_manager):
        self._pool = buffer_pool
        self._txn = txn
        self._fm = file_manager

    def get_page(self, page_id: int) -> bytes:
        """Read page, returning shadow version if it exists."""
        shadow_id = self._txn.shadow_pages.get(page_id)
        if shadow_id is not None:
            return self._pool.get_page(shadow_id)
        return self._pool.get_page(page_id)

    def set_page_data(self, page_id: int, data: bytes) -> None:
        """Write page data, creating shadow page on first write (CoW)."""
        shadow_id = self._ensure_shadow(page_id)
        self._pool.set_page_data(shadow_id, data)

    def mark_dirty(self, page_id: int) -> None:
        """Mark page as dirty."""
        shadow_id = self._txn.shadow_pages.get(page_id, page_id)
        self._pool.mark_dirty(shadow_id)

    def flush(self) -> None:
        """Flush all dirty pages to disk."""
        self._pool.flush()

    def rollback(self) -> None:
        """Release all shadow pages."""
        for orig_id, shadow_id in self._txn.shadow_pages.items():
            self._fm.free_page(shadow_id)
        self._txn.shadow_pages.clear()
        self._txn.state = "aborted"

    def commit(self) -> None:
        """Flush shadow pages and atomically switch root pointer."""
        self._pool.flush()
        self._fm.root_page_id = self._txn.new_root
        self._fm._write_header()
        self._fm._file.flush()
        os.fsync(self._fm._file.fileno())
        self._txn.shadow_pages.clear()
        self._txn.state = "committed"

    def _ensure_shadow(self, page_id: int) -> int:
        """Get or create shadow page for CoW."""
        if page_id in self._txn.shadow_pages:
            return self._txn.shadow_pages[page_id]

        # CoW: allocate new page and copy original data
        shadow_id = self._fm.alloc_page()
        orig_data = self._pool.get_page(page_id)
        self._pool._fm.write_page(shadow_id, orig_data)
        self._txn.shadow_pages[page_id] = shadow_id
        return shadow_id
```

- [ ] **Step 4: Create `tinydb/transaction/__init__.py`**

```python
# tinydb/transaction/__init__.py
from tinydb.transaction.shadow_paging import Transaction, ShadowBufferPool
from tinydb.transaction.txn_manager import TransactionManager

__all__ = ["Transaction", "ShadowBufferPool", "TransactionManager"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_shadow_paging.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tinydb/transaction/__init__.py tinydb/transaction/shadow_paging.py tests/test_shadow_paging.py
git commit -m "feat: add Shadow Paging with CoW, COMMIT, ROLLBACK"
```

---

## Task 5: Transaction Manager

**Files:**
- Create: `tinydb/transaction/txn_manager.py`
- Test: `tests/test_transaction.py`

**Prerequisites:** Task 4

**Produces:** `TransactionManager`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_transaction.py
import pytest
from tinydb.transaction.txn_manager import TransactionManager, TransactionError
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.index.index_manager import IndexManager
from tinydb.page import create_empty_page, PageType


@pytest.fixture
def db_env(tmp_path):
    db_path = str(tmp_path / "test.db")
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    cat = Catalog(fm, pool)
    cat.load()
    imgr = IndexManager(cat, fm, pool)
    yield fm, pool, cat, imgr
    fm.close()


class TestTransactionManager:
    def test_begin_commit(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn = tm.begin()
        assert txn.state == "active"
        tm.commit()
        assert txn.state == "committed"

    def test_begin_rollback(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn = tm.begin()
        tm.rollback()
        assert txn.state == "aborted"

    def test_nested_txn_rejected(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        tm.begin()
        with pytest.raises(TransactionError):
            tm.begin()

    def test_no_active_txn_error(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        with pytest.raises(TransactionError):
            tm.commit()
        with pytest.raises(TransactionError):
            tm.rollback()

    def test_has_active_txn(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        assert not tm.has_active_txn()
        tm.begin()
        assert tm.has_active_txn()
        tm.commit()
        assert not tm.has_active_txn()

    def test_ensure_shadow(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        tm.begin()
        shadow_id = tm.ensure_shadow(1)
        assert shadow_id != 1  # shadow page created
        # Same page returns same shadow
        assert tm.ensure_shadow(1) == shadow_id
        tm.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_transaction.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `tinydb/transaction/txn_manager.py`**

```python
# tinydb/transaction/txn_manager.py
"""Transaction Manager: lifecycle and auto-rollback."""
from tinydb.transaction.shadow_paging import Transaction, ShadowBufferPool


class TransactionError(Exception):
    pass


class TransactionManager:
    """Manages transaction lifecycle."""

    def __init__(self, file_manager, buffer_pool, index_manager):
        self._fm = file_manager
        self._pool = buffer_pool
        self._index_mgr = index_manager
        self._active_txn: Transaction | None = None
        self._txn_counter = 0

    def begin(self) -> Transaction:
        if self._active_txn is not None:
            raise TransactionError("Nested transactions not supported")
        self._txn_counter += 1
        txn = Transaction(
            txn_id=self._txn_counter,
            state="active",
            shadow_pages={},
            snapshot_root=self._fm.root_page_id,
            new_root=self._fm.root_page_id,
        )
        self._active_txn = txn
        return txn

    def commit(self):
        if self._active_txn is None:
            raise TransactionError("No active transaction")
        self._pool.flush()
        self._fm.root_page_id = self._active_txn.new_root
        self._fm._write_header()
        self._fm._file.flush()
        import os
        os.fsync(self._fm._file.fileno())
        self._active_txn.state = "committed"
        self._active_txn = None

    def rollback(self):
        if self._active_txn is None:
            raise TransactionError("No active transaction")
        for orig_id, shadow_id in self._active_txn.shadow_pages.items():
            self._fm.free_page(shadow_id)
        self._active_txn.state = "aborted"
        self._active_txn = None

    def ensure_shadow(self, page_id: int) -> int:
        """Get or create shadow page. Returns shadow page ID."""
        if self._active_txn is None:
            return page_id
        if page_id in self._active_txn.shadow_pages:
            return self._active_txn.shadow_pages[page_id]
        shadow_id = self._fm.alloc_page()
        orig_data = self._pool.get_page(page_id)
        self._pool._fm.write_page(shadow_id, orig_data)
        self._active_txn.shadow_pages[page_id] = shadow_id
        return shadow_id

    def has_active_txn(self) -> bool:
        return self._active_txn is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transaction.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tinydb/transaction/txn_manager.py tests/test_transaction.py
git commit -m "feat: add TransactionManager with BEGIN/COMMIT/ROLLBACK and auto-rollback"
```

---

## Task 6: Index-Aware Executor

**Files:**
- Create: `tinydb/sql/__init__.py`
- Create: `tinydb/sql/executor.py`
- Test: `tests/test_executor.py`

**Prerequisites:** Task 2, Task 3

**Produces:** `IndexScanOperator`, `Planner`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_executor.py
import pytest
from tinydb.sql.executor import IndexScanOperator, Planner
from tinydb.index.index_manager import IndexManager, IndexMeta
from tinydb.types import DataType, ColumnDef
from tinydb.page import RowId
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog


@pytest.fixture
def db_env(tmp_path):
    db_path = str(tmp_path / "test.db")
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    cat = Catalog(fm, pool)
    cat.load()

    columns = [
        ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
        ColumnDef(name="name", data_type=DataType.TEXT),
        ColumnDef(name="age", data_type=DataType.INTEGER),
    ]
    cat.create_table("users", columns, pk="id")
    tbl = cat.get_table("users")

    imgr = IndexManager(cat, fm, pool)
    imgr.create_index("users", "age", "idx_users_age")

    # Insert data
    for i, age in enumerate([25, 30, 35, 40, 30]):
        rid = tbl.insert(pool, [i, f"user_{i}", age])
        imgr.after_insert("users", rid, [i, f"user_{i}", age])

    yield fm, pool, cat, tbl, imgr
    fm.close()


class TestIndexScanOperator:
    def test_equality_scan(self, db_env):
        fm, pool, cat, tbl, imgr = db_env
        meta = imgr.get_index("users", "age")

        class MockCond:
            column = "age"
            op = "="
            value = 30

        op = IndexScanOperator(tbl, meta, MockCond())
        results = list(op.execute(pool))
        assert len(results) == 2  # two users with age=30

    def test_range_scan(self, db_env):
        fm, pool, cat, tbl, imgr = db_env
        meta = imgr.get_index("users", "age")

        class MockCond:
            column = "age"
            op = ">"
            value = 30

        op = IndexScanOperator(tbl, meta, MockCond())
        results = list(op.execute(pool))
        assert len(results) == 2  # age 35 and 40


class TestPlanner:
    def test_choose_index_scan(self, db_env):
        fm, pool, cat, tbl, imgr = db_env
        planner = Planner(imgr)

        class MockCond:
            column = "age"
            op = "="
            value = 30

        scan = planner._choose_scan(tbl, MockCond())
        assert isinstance(scan, IndexScanOperator)

    def test_choose_full_scan_no_index(self, db_env):
        fm, pool, cat, tbl, imgr = db_env
        planner = Planner(imgr)

        class MockCond:
            column = "name"
            op = "="
            value = "Alice"

        scan = planner._choose_scan(tbl, MockCond())
        # No index on name, should return None (use full scan)
        assert scan is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_executor.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `tinydb/sql/executor.py`**

```python
# tinydb/sql/executor.py
"""Index-aware query executor with planner."""
from tinydb.index.btree import BTreeIndex
from tinydb.index.index_manager import IndexMeta


class IndexScanOperator:
    """Scan using B-tree index for equality/range conditions."""

    def __init__(self, table, index_meta: IndexMeta, condition):
        self.table = table
        self.index = index_meta
        self.condition = condition

    def execute(self, buffer_pool):
        btree = BTreeIndex(buffer_pool, key_type=self.index.column_type,
                           root_page=self.index.root_page)
        op = self.condition.op
        key = self.condition.value

        if op == "=":
            results = btree.search(key)
        elif op == ">":
            results = btree.range_scan(start=key, end=None, start_inclusive=False)
        elif op == ">=":
            results = btree.range_scan(start=key, end=None, start_inclusive=True)
        elif op == "<":
            results = btree.range_scan(start=None, end=key, end_inclusive=False)
        elif op == "<=":
            results = btree.range_scan(start=None, end=key, end_inclusive=True)
        elif op == "!=":
            # Fallback: full scan + filter
            for row_ptr, row in self.table.scan(buffer_pool):
                col_idx = next(
                    (i for i, c in enumerate(self.table.columns) if c.name == self.condition.column),
                    -1
                )
                if col_idx >= 0 and row[col_idx] != key:
                    yield row_ptr, row
            return
        else:
            results = []

        for row_ptr in results:
            row = self.table.get(buffer_pool, row_ptr)
            if row is not None:
                yield row_ptr, row


class Planner:
    """Simple heuristic planner: use index if available."""

    def __init__(self, index_manager=None):
        self._index_mgr = index_manager

    def _choose_scan(self, table, where_clause):
        """Choose scan strategy. Returns IndexScanOperator or None (full scan)."""
        if self._index_mgr and where_clause:
            index = self._index_mgr.find_matching_index(table.table_name, where_clause)
            if index:
                return IndexScanOperator(table, index, where_clause)
        return None
```

- [ ] **Step 4: Create `tinydb/sql/__init__.py`**

```python
# tinydb/sql/__init__.py
from tinydb.sql.executor import IndexScanOperator, Planner

__all__ = ["IndexScanOperator", "Planner"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_executor.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tinydb/sql/__init__.py tinydb/sql/executor.py tests/test_executor.py
git commit -m "feat: add IndexScanOperator and Planner with index selection heuristic"
```

---

## Task 7: Database Class

**Files:**
- Create: `tinydb/database.py`
- Test: `tests/test_database.py`

**Prerequisites:** Task 3, Task 5, Task 6

**Produces:** `Database`, `QueryResult`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_database.py
import pytest
from tinydb.database import Database, QueryResult
from tinydb.types import ColumnDef, DataType


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    database.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    yield database
    database.close()


class TestDatabase:
    def test_execute_insert(self, db):
        result = db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        assert result.row_count == 1

    def test_execute_select(self, db):
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 2
        assert result.columns == ["id", "name", "age"]

    def test_execute_update(self, db):
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        result = db.execute("UPDATE users SET age = 31 WHERE id = 1")
        assert result.row_count == 1

    def test_execute_delete(self, db):
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        result = db.execute("DELETE FROM users WHERE id = 1")
        assert result.row_count == 1

    def test_context_manager(self, tmp_path):
        with Database(str(tmp_path / "test.db")) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            db.execute("INSERT INTO t VALUES (1)")
            result = db.execute("SELECT * FROM t")
            assert result.row_count == 1

    def test_commit_rollback(self, db):
        db.execute("BEGIN")
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        db.execute("ROLLBACK")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `tinydb/database.py`**

```python
# tinydb/database.py
"""Database: unified entry point integrating storage, SQL, index, and transaction."""
import os
from dataclasses import dataclass
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.index.index_manager import IndexManager
from tinydb.transaction.txn_manager import TransactionManager, TransactionError
from tinydb.sql.executor import Planner
from tinydb.table import Table
from tinydb.types import ColumnDef, DataType, convert_value
from tinydb.row_format import serialize_row, deserialize_row
from tinydb.page import RowId


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    row_count: int


class DatabaseError(Exception):
    pass


class Database:
    """Unified database interface."""

    def __init__(self, path: str):
        self._fm = FileManager(path)
        self._fm.open()
        self._pool = BufferPool(self._fm)
        self._catalog = Catalog(self._fm, self._pool)
        self._catalog.load()
        self._index_mgr = IndexManager(self._catalog, self._fm, self._pool)
        self._txn_mgr = TransactionManager(self._fm, self._pool, self._index_mgr)
        self._planner = Planner(self._index_mgr)

    def execute(self, sql: str) -> QueryResult:
        """Execute SQL and return result."""
        sql = sql.strip().rstrip(";").strip()
        upper = sql.upper()

        try:
            if upper.startswith("CREATE TABLE"):
                return self._exec_create_table(sql)
            elif upper.startswith("DROP TABLE"):
                return self._exec_drop_table(sql)
            elif upper.startswith("INSERT INTO"):
                return self._exec_insert(sql)
            elif upper.startswith("SELECT"):
                return self._exec_select(sql)
            elif upper.startswith("UPDATE"):
                return self._exec_update(sql)
            elif upper.startswith("DELETE FROM"):
                return self._exec_delete(sql)
            elif upper.startswith("CREATE INDEX"):
                return self._exec_create_index(sql)
            elif upper.startswith("BEGIN"):
                self._txn_mgr.begin()
                return QueryResult(columns=[], rows=[], row_count=0)
            elif upper.startswith("COMMIT"):
                self._txn_mgr.commit()
                return QueryResult(columns=[], rows=[], row_count=0)
            elif upper.startswith("ROLLBACK"):
                self._txn_mgr.rollback()
                return QueryResult(columns=[], rows=[], row_count=0)
            else:
                raise DatabaseError(f"Unsupported SQL: {sql}")
        except Exception as e:
            if self._txn_mgr.has_active_txn():
                self._txn_mgr.rollback()
            raise DatabaseError(str(e))

    def commit(self):
        self._txn_mgr.commit()

    def rollback(self):
        self._txn_mgr.rollback()

    def close(self):
        self._pool.flush()
        self._fm.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ── Internal SQL execution ───────────────────────────────

    def _exec_create_table(self, sql: str) -> QueryResult:
        # Parse: CREATE TABLE name (col1 TYPE, col2 TYPE, ...)
        import re
        m = re.match(r"CREATE TABLE (\w+)\s*\((.+)\)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid CREATE TABLE: {sql}")
        table_name = m.group(1)
        cols_str = m.group(2)

        columns = []
        pk = ""
        for col_def in cols_str.split(","):
            parts = col_def.strip().split()
            col_name = parts[0]
            col_type = DataType(parts[1].upper())
            is_pk = "PRIMARY" in col_def.upper() and "KEY" in col_def.upper()
            nullable = "NOT NULL" not in col_def.upper() and not is_pk
            columns.append(ColumnDef(name=col_name, data_type=col_type,
                                     nullable=nullable, primary_key=is_pk))
            if is_pk:
                pk = col_name

        self._catalog.create_table(table_name, columns, pk)
        self._catalog.save()
        return QueryResult(columns=[], rows=[], row_count=0)

    def _exec_drop_table(self, sql: str) -> QueryResult:
        import re
        m = re.match(r"DROP TABLE (\w+)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid DROP TABLE: {sql}")
        self._catalog.drop_table(m.group(1))
        self._catalog.save()
        return QueryResult(columns=[], rows=[], row_count=0)

    def _exec_insert(self, sql: str) -> QueryResult:
        import re
        m = re.match(r"INSERT INTO (\w+)\s+VALUES\s*\((.+)\)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid INSERT: {sql}")
        table_name = m.group(1)
        values_str = m.group(2)

        tbl = self._catalog.get_table(table_name)
        values = self._parse_values(values_str, tbl.columns)
        converted = [convert_value(v, col) for v, col in zip(values, tbl.columns)]

        rid = tbl.insert(self._pool, converted)
        self._index_mgr.after_insert(table_name, rid, converted)
        return QueryResult(columns=[], rows=[], row_count=1)

    def _exec_select(self, sql: str) -> QueryResult:
        import re
        # Parse: SELECT cols FROM table [WHERE cond]
        m = re.match(r"SELECT\s+(.+?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+))?", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid SELECT: {sql}")
        cols_str = m.group(1).strip()
        table_name = m.group(2)
        where_str = m.group(3)

        tbl = self._catalog.get_table(table_name)
        columns = [c.name for c in tbl.columns]

        if cols_str == "*":
            selected_cols = columns
        else:
            selected_cols = [c.strip() for c in cols_str.split(",")]

        rows = []
        for row_ptr, row in tbl.scan(self._pool):
            if where_str and not self._eval_where(row, tbl.columns, where_str):
                continue
            selected = [row[columns.index(c)] for c in selected_cols]
            rows.append(selected)

        return QueryResult(columns=selected_cols, rows=rows, row_count=len(rows))

    def _exec_update(self, sql: str) -> QueryResult:
        import re
        m = re.match(r"UPDATE\s+(\w+)\s+SET\s+(.+?)(?:\s+WHERE\s+(.+))?", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid UPDATE: {sql}")
        table_name = m.group(1)
        set_str = m.group(2)
        where_str = m.group(3)

        tbl = self._catalog.get_table(table_name)
        set_clause = self._parse_set(set_str, tbl.columns)

        count = 0
        for row_ptr, row in tbl.scan(self._pool):
            if where_str and not self._eval_where(row, tbl.columns, where_str):
                continue
            new_row = list(row)
            for col_idx, val in set_clause.items():
                new_row[col_idx] = val
            tbl.update(self._pool, row_ptr, new_row)
            self._index_mgr.after_update(table_name, row_ptr, row, new_row)
            count += 1

        return QueryResult(columns=[], rows=[], row_count=count)

    def _exec_delete(self, sql: str) -> QueryResult:
        import re
        m = re.match(r"DELETE FROM\s+(\w+)(?:\s+WHERE\s+(.+))?", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid DELETE: {sql}")
        table_name = m.group(1)
        where_str = m.group(2)

        tbl = self._catalog.get_table(table_name)
        count = 0
        to_delete = []
        for row_ptr, row in tbl.scan(self._pool):
            if where_str and not self._eval_where(row, tbl.columns, where_str):
                continue
            to_delete.append((row_ptr, row))

        for row_ptr, row in to_delete:
            self._index_mgr.after_delete(table_name, row_ptr, row)
            tbl.delete(self._pool, row_ptr)
            count += 1

        return QueryResult(columns=[], rows=[], row_count=count)

    def _exec_create_index(self, sql: str) -> QueryResult:
        import re
        m = re.match(r"CREATE INDEX (\w+)\s+ON\s+(\w+)\s*\((\w+)\)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid CREATE INDEX: {sql}")
        idx_name = m.group(1)
        table_name = m.group(2)
        col_name = m.group(3)

        self._index_mgr.create_index(table_name, col_name, idx_name)
        return QueryResult(columns=[], rows=[], row_count=0)

    # ── Helpers ──────────────────────────────────────────────

    def _parse_values(self, values_str: str, columns: list[ColumnDef]) -> list:
        """Parse comma-separated values string."""
        import re
        values = []
        for raw in re.split(r",\s*(?=(?:[^']*'[^']*')*[^']*$)", values_str):
            raw = raw.strip()
            if raw.startswith("'") and raw.endswith("'"):
                values.append(raw[1:-1])
            elif raw.upper() == "NULL":
                values.append(None)
            elif "." in raw:
                values.append(float(raw))
            else:
                values.append(int(raw))
        return values

    def _parse_set(self, set_str: str, columns: list[ColumnDef]) -> dict:
        """Parse SET clause into {col_idx: value}."""
        result = {}
        for assignment in set_str.split(","):
            col_name, val_str = assignment.split("=", 1)
            col_name = col_name.strip()
            val_str = val_str.strip()
            col_idx = next((i for i, c in enumerate(columns) if c.name == col_name), -1)
            if col_idx < 0:
                raise DatabaseError(f"Unknown column: {col_name}")
            if val_str.startswith("'") and val_str.endswith("'"):
                result[col_idx] = val_str[1:-1]
            elif val_str.upper() == "NULL":
                result[col_idx] = None
            elif "." in val_str:
                result[col_idx] = float(val_str)
            else:
                result[col_idx] = int(val_str)
        return result

    def _eval_where(self, row: list, columns: list[ColumnDef], where_str: str) -> bool:
        """Simple WHERE evaluator for single condition."""
        import re
        m = re.match(r"(\w+)\s*(=|!=|<>|>=|<=|>|<)\s*(.+)", where_str.strip())
        if not m:
            return True
        col_name = m.group(1)
        op = m.group(2)
        val_str = m.group(3).strip()

        col_idx = next((i for i, c in enumerate(columns) if c.name == col_name), -1)
        if col_idx < 0:
            return True

        val = row[col_idx]
        if val_str.startswith("'") and val_str.endswith("'"):
            compare = val_str[1:-1]
        elif val_str.upper() == "NULL":
            compare = None
        elif "." in val_str:
            compare = float(val_str)
        else:
            compare = int(val_str)

        if op == "=":
            return val == compare
        elif op in ("!=", "<>"):
            return val != compare
        elif op == ">":
            return val is not None and val > compare
        elif op == ">=":
            return val is not None and val >= compare
        elif op == "<":
            return val is not None and val < compare
        elif op == "<=":
            return val is not None and val <= compare
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tinydb/database.py tests/test_database.py
git commit -m "feat: add Database class with execute(), commit(), rollback(), context manager"
```

---

## Task 8: CLI REPL

**Files:**
- Create: `tinydb/cli/__init__.py`
- Create: `tinydb/cli/repl.py`
- Test: `tests/test_repl.py`

**Prerequisites:** Task 7

**Produces:** `REPL`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_repl.py
import pytest
from unittest.mock import patch
from tinydb.cli.repl import REPL
from tinydb.database import Database, QueryResult


class TestREPL:
    def test_format_output(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        result = QueryResult(
            columns=["id", "name"],
            rows=[[1, "Alice"], [2, "Bob"]],
            row_count=2
        )
        output = repl._format_output(result)
        assert "id" in output
        assert "Alice" in output
        assert "2 rows" in output
        db.close()

    def test_meta_exit(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        with pytest.raises(SystemExit):
            repl._handle_meta(".exit")
        db.close()

    def test_meta_tables(self, tmp_path, capsys):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        repl = REPL(db)
        repl._handle_meta(".tables")
        captured = capsys.readouterr()
        assert "t1" in captured.out
        db.close()

    def test_multiline_buffer(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        # Simulate multi-line input
        assert not repl._is_complete("SELECT *")
        assert repl._is_complete("SELECT * FROM t;")
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repl.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `tinydb/cli/repl.py`**

```python
# tinydb/cli/repl.py
"""Interactive REPL for tinydb."""
import readline


class REPL:
    """Read-Eval-Print Loop for tinydb SQL."""

    def __init__(self, db):
        self._db = db
        self._buffer = []

    def run(self):
        readline.set_history_length(1000)
        while True:
            try:
                prompt = "tinydb> " if not self._buffer else "   ...> "
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break

            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("."):
                self._handle_meta(stripped)
                continue

            self._buffer.append(line)
            sql = " ".join(self._buffer)

            if sql.rstrip().endswith(";"):
                self._buffer.clear()
                try:
                    result = self._db.execute(sql)
                    print(self._format_output(result))
                except Exception as e:
                    print(f"Error: {e}")

    def _handle_meta(self, cmd: str):
        parts = cmd.split()
        if not parts:
            return
        match parts[0]:
            case ".exit" | ".quit":
                raise SystemExit
            case ".tables":
                result = self._db.execute("SELECT table_name FROM tinydb_master")
                for row in result.rows:
                    print(row[0])
            case ".schema":
                if len(parts) < 2:
                    print("Usage: .schema <table>")
                else:
                    result = self._db.execute(f"SELECT * FROM {parts[1]} LIMIT 0")
                    print(" | ".join(result.columns))
            case ".help":
                print("Meta-commands: .exit .tables .schema .help")
            case _:
                print(f"Unknown command: {parts[0]}")

    def _format_output(self, result) -> str:
        if not result.rows:
            return f"{result.row_count} rows in set"

        # Calculate column widths
        col_widths = [len(c) for c in result.columns]
        for row in result.rows:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))

        # Build table
        sep = "─" * (sum(col_widths) + 3 * len(col_widths) + 1)
        lines = [sep]

        # Header
        header = "│ " + " │ ".join(
            c.ljust(w) for c, w in zip(result.columns, col_widths)
        ) + " │"
        lines.append(header)
        lines.append(sep.replace("─", "┼").replace("┼", "├", 1).replace("┼", "┤", -1)
                     .replace("─", "┼"))  # simplified separator

        # Rows
        for row in result.rows:
            row_str = "│ " + " │ ".join(
                str(v).ljust(w) for v, w in zip(row, col_widths)
            ) + " │"
            lines.append(row_str)

        lines.append(sep)
        lines.append(f"{result.row_count} rows in set")
        return "\n".join(lines)

    def _is_complete(self, sql: str) -> bool:
        return sql.rstrip().endswith(";")
```

- [ ] **Step 4: Create `tinydb/cli/__init__.py`**

```python
# tinydb/cli/__init__.py
from tinydb.cli.repl import REPL

__all__ = ["REPL"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_repl.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tinydb/cli/__init__.py tinydb/cli/repl.py tests/test_repl.py
git commit -m "feat: add CLI REPL with readline, multi-line SQL, meta-commands"
```

---

## Task 9: Integration Tests

**Files:**
- Modify: `tests/test_integration.py`
- Test: `tests/test_integration.py`

**Prerequisites:** All above

**Produces:** End-to-end integration tests

- [ ] **Step 1: Write the failing test**

```python
# tests/test_integration.py — append new test class

class TestIndexTransactionIntegration:
    def test_insert_select_with_index(self, tmp_path):
        from tinydb.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
        db.execute("CREATE INDEX idx_age ON users (age)")

        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
        db.execute("INSERT INTO users VALUES (3, 'Carol', 35)")

        result = db.execute("SELECT * FROM users WHERE age = 30")
        assert result.row_count == 1
        assert result.rows[0][1] == "Alice"
        db.close()

    def test_transaction_commit_persists(self, tmp_path):
        from tinydb.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE kv (id INTEGER PRIMARY KEY, val TEXT)")

        db.execute("BEGIN")
        db.execute("INSERT INTO kv VALUES (1, 'hello')")
        db.execute("COMMIT")

        result = db.execute("SELECT * FROM kv")
        assert result.row_count == 1
        db.close()

    def test_transaction_rollback_discards(self, tmp_path):
        from tinydb.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE kv (id INTEGER PRIMARY KEY, val TEXT)")

        db.execute("BEGIN")
        db.execute("INSERT INTO kv VALUES (1, 'hello')")
        db.execute("ROLLBACK")

        result = db.execute("SELECT * FROM kv")
        assert result.row_count == 0
        db.close()

    def test_rollback_restores_index(self, tmp_path):
        from tinydb.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
        db.execute("CREATE INDEX idx_age ON users (age)")

        db.execute("BEGIN")
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        db.execute("ROLLBACK")

        result = db.execute("SELECT * FROM users WHERE age = 30")
        assert result.row_count == 0
        db.close()

    def test_crud_lifecycle(self, tmp_path):
        from tinydb.database import Database
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, price FLOAT)")

        db.execute("INSERT INTO items VALUES (1, 'Widget', 9.99)")
        db.execute("INSERT INTO items VALUES (2, 'Gadget', 19.99)")

        result = db.execute("SELECT * FROM items")
        assert result.row_count == 2

        db.execute("UPDATE items SET price = 14.99 WHERE id = 1")
        result = db.execute("SELECT price FROM items WHERE id = 1")
        assert result.rows[0][0] == 14.99

        db.execute("DELETE FROM items WHERE id = 2")
        result = db.execute("SELECT * FROM items")
        assert result.row_count == 1
        db.close()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "feat: add integration tests for index, transaction, and CRUD lifecycle"
```

---

## Task 10: Update Public API & Final Integration

**Files:**
- Modify: `tinydb/__init__.py`
- Test: Run full test suite

**Prerequisites:** All above

**Produces:** Updated public API

- [ ] **Step 1: Update `tinydb/__init__.py`**

Add exports for new modules:
```python
from tinydb.database import Database, QueryResult, DatabaseError
from tinydb.index import BTreeIndex, IndexManager, IndexMeta
from tinydb.transaction import Transaction, ShadowBufferPool, TransactionManager
from tinydb.sql import IndexScanOperator, Planner
from tinydb.cli import REPL
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tinydb/__init__.py
git commit -m "feat: expose new modules via tinydb public API"
```
