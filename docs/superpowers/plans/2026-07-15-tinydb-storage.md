---
change: tinydb-storage
design-doc: docs/superpowers/specs/2026-07-15-tinydb-storage-design.md
base-ref: null
archived-with: 2026-07-15-tinydb-storage
---

# tinydb-storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 tinydb 存储引擎的七个模块（TypeSystem / RowFormat / Page / FileManager / BufferPool / Catalog / Table），提供完整的页式存储、LRU 缓冲池、系统目录和表级 CRUD API。

**Architecture:** 自底向上的模块依赖链：TypeSystem → RowFormat → Page → FileManager → BufferPool → Catalog → Table。每个模块通过清晰接口解耦，上层仅依赖下层接口。BufferPool 采用 OrderedDict + 双向链表双视角 LRU 设计（教学展示用）。文件格式采用经典 Slotted Page + 空闲链表分配器。

**Tech Stack:** Python 3.10+, pytest, 零外部依赖

## Global Constraints

- Python 3.10+ 标准库，零外部依赖
- 页大小固定 4096 bytes
- 文件 magic bytes: `b"TINYDB\0"`
- 文件格式版本: 1
- BufferPool 默认容量: 100 pages
- 教学优先: 代码清晰可读，关键概念有注释
- 所有错误通过异常体系处理（StorageError 继承树）
- 不支持并发访问
- NULL 位图: 每列 1 bit，`ceil(n/8)` bytes
- 行编码: INTEGER=int64(8B), FLOAT=double(8B), BOOLEAN=1B, TEXT=4B length + UTF-8

---

## File Structure

```
tinydb/
├── __init__.py
├── types.py          # DataType, ColumnDef, Value, 类型检查/转换
├── row_format.py     # NULL 位图, serialize_row, deserialize_row
├── page.py           # Page, PageType, RowId, Slotted Page 操作
├── file_manager.py   # FileManager, FileHeader, 空闲链表分配器
├── buffer_pool.py    # BufferPool, LRU Node, pin/unpin
├── catalog.py        # Catalog, TableMeta, tinydb_master
├── table.py          # Table, insert/scan/get/delete/update
└── exceptions.py     # StorageError 继承树

tests/
├── conftest.py       # 共享 fixtures (tmp_path, sample columns)
├── test_types.py
├── test_row_format.py
├── test_page.py
├── test_file_manager.py
├── test_buffer_pool.py
├── test_catalog.py
├── test_table.py
└── test_integration.py
```

---

## Task 1: Project Skeleton & Constants

**Files:**
- Create: `tinydb/__init__.py`
- Create: `tinydb/exceptions.py`
- Create: `tinydb/constants.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `pyproject.toml`

**Interfaces:**
- Consumes: nothing
- Produces: `StorageError` 异常类, 模块常量 (`PAGE_SIZE`, `PAGE_HEADER_SIZE` 等)

- [x] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "tinydb"
version = "0.1.0"
description = "A tiny embedded relational database for learning"
requires-python = ">=3.10"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"
```

- [x] **Step 2: Create package init files**

```python
# tinydb/__init__.py
"""tinydb: a tiny embedded relational database for learning."""
```

```python
# tests/__init__.py
```

- [x] **Step 3: Create exceptions.py**

```python
# tinydb/exceptions.py


class StorageError(Exception):
    """Base exception for all storage engine errors."""
    pass


class StorageCorruptionError(StorageError):
    """File integrity check failed."""
    pass


class StorageFullError(StorageError):
    """No space left in database file."""
    pass


class PageOutOfRangeError(StorageError):
    """Referenced page is beyond file bounds."""
    pass


class TableExistsError(StorageError):
    """Attempted to create a table that already exists."""
    pass


class TableNotFoundError(StorageError):
    """Referenced table does not exist."""
    pass


class SchemaMismatchError(StorageError):
    """Value does not match column definition."""
    pass
```

- [x] **Step 4: Create constants.py**

```python
# tinydb/constants.py

# Page constants
PAGE_SIZE = 4096
PAGE_HEADER_SIZE = 32
SLOT_SIZE = 4
MAX_FREE_SPACE = PAGE_SIZE - PAGE_HEADER_SIZE

# File format
MAGIC = b"TINYDB\0"
VERSION = 1

# Buffer pool
DEFAULT_BUFFER_POOL_CAPACITY = 100

# Page types
PAGE_TYPE_DATA = 1
PAGE_TYPE_CATALOG = 2
PAGE_TYPE_INDEX = 3

# Catalog table name
CATALOG_TABLE_NAME = "tinydb_master"
```

- [x] **Step 5: Create conftest.py with shared fixtures**

```python
# tests/conftest.py
"""Shared pytest fixtures for tinydb storage engine tests."""
import pytest


@pytest.fixture
def all_types_columns():
    """A column set covering all four data types."""
    from tinydb.types import ColumnDef, DataType
    return [
        ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
        ColumnDef(name="name", data_type=DataType.TEXT, nullable=True),
        ColumnDef(name="score", data_type=DataType.FLOAT, nullable=True),
        ColumnDef(name="active", data_type=DataType.BOOLEAN, nullable=False),
    ]


@pytest.fixture
def sample_row(all_types_columns):
    """A sample row matching all_types_columns."""
    return [1, "Alice", 95.5, True]


@pytest.fixture
def null_row(all_types_columns):
    """A row with a NULL value."""
    return [2, None, None, False]
```

- [x] **Step 6: Verify project structure**

Run: `python -c "import tinydb; from tinydb.exceptions import StorageError; print('OK')"`
Expected: `OK`

- [x] **Step 7: Commit**

```bash
git add pyproject.toml tinydb/__init__.py tinydb/exceptions.py tinydb/constants.py tests/__init__.py tests/conftest.py
git commit -m "feat(storage): add project skeleton, exceptions, and constants"
```

---

## Task 2: TypeSystem — DataType Enum & ColumnDef

**Files:**
- Create: `tinydb/types.py`
- Create: `tests/test_types.py`

**Interfaces:**
- Consumes: `constants.py`
- Produces: `DataType`, `ColumnDef`, `Value`, `validate_value()`, `convert_value()`

- [x] **Step 1: Write the failing test**

```python
# tests/test_types.py
"""Tests for tinydb.types module."""
import pytest
from tinydb.types import DataType, ColumnDef, Value, validate_value, convert_value
from tinydb.exceptions import SchemaMismatchError


class TestDataType:
    def test_enum_values(self):
        assert DataType.INTEGER.value == "INTEGER"
        assert DataType.FLOAT.value == "FLOAT"
        assert DataType.TEXT.value == "TEXT"
        assert DataType.BOOLEAN.value == "BOOLEAN"


class TestColumnDef:
    def test_basic_creation(self):
        col = ColumnDef(name="id", data_type=DataType.INTEGER)
        assert col.name == "id"
        assert col.data_type == DataType.INTEGER
        assert col.nullable is True
        assert col.primary_key is False
        assert col.unique is False

    def test_not_null_column(self):
        col = ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False)
        assert col.nullable is False

    def test_primary_key_column(self):
        col = ColumnDef(name="id", data_type=DataType.INTEGER, primary_key=True)
        assert col.primary_key is True


class TestValidateValue:
    def test_integer_accepts_int(self):
        col = ColumnDef(name="x", data_type=DataType.INTEGER)
        validate_value(42, col)  # should not raise

    def test_integer_rejects_float(self):
        col = ColumnDef(name="x", data_type=DataType.INTEGER)
        with pytest.raises(SchemaMismatchError):
            validate_value(3.14, col)

    def test_float_accepts_int(self):
        col = ColumnDef(name="x", data_type=DataType.FLOAT)
        validate_value(42, col)  # implicit conversion

    def test_float_accepts_float(self):
        col = ColumnDef(name="x", data_type=DataType.FLOAT)
        validate_value(3.14, col)

    def test_text_accepts_str(self):
        col = ColumnDef(name="x", data_type=DataType.TEXT)
        validate_value("hello", col)

    def test_text_rejects_int(self):
        col = ColumnDef(name="x", data_type=DataType.TEXT)
        with pytest.raises(SchemaMismatchError):
            validate_value(42, col)

    def test_boolean_accepts_bool(self):
        col = ColumnDef(name="x", data_type=DataType.BOOLEAN)
        validate_value(True, col)

    def test_nullable_accepts_none(self):
        col = ColumnDef(name="x", data_type=DataType.INTEGER, nullable=True)
        validate_value(None, col)

    def test_not_nullable_rejects_none(self):
        col = ColumnDef(name="x", data_type=DataType.INTEGER, nullable=False)
        with pytest.raises(SchemaMismatchError):
            validate_value(None, col)


class TestConvertValue:
    def test_int_to_float(self):
        col = ColumnDef(name="x", data_type=DataType.FLOAT)
        result = convert_value(42, col)
        assert result == 42.0
        assert isinstance(result, float)

    def test_int_to_int(self):
        col = ColumnDef(name="x", data_type=DataType.INTEGER)
        result = convert_value(42, col)
        assert result == 42
        assert isinstance(result, int)

    def test_str_to_text(self):
        col = ColumnDef(name="x", data_type=DataType.TEXT)
        result = convert_value("hello", col)
        assert result == "hello"


class TestValue:
    def test_wrap_int(self):
        v = Value(42, DataType.INTEGER)
        assert v.data == 42
        assert v.data_type == DataType.INTEGER
        assert v.is_null is False

    def test_wrap_none(self):
        v = Value(None, DataType.INTEGER)
        assert v.is_null is True

    def test_value_equality(self):
        v1 = Value(42, DataType.INTEGER)
        v2 = Value(42, DataType.INTEGER)
        assert v1 == v2
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tinydb.types'`

- [x] **Step 3: Write minimal implementation**

```python
# tinydb/types.py
"""Type system: DataType enum, ColumnDef, Value wrapper, validation and conversion."""
from dataclasses import dataclass
from enum import Enum
from tinydb.exceptions import SchemaMismatchError


class DataType(Enum):
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"


@dataclass
class ColumnDef:
    name: str
    data_type: DataType
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False


@dataclass
class Value:
    data: object
    data_type: DataType

    @property
    def is_null(self) -> bool:
        return self.data is None


def validate_value(value: object, column: ColumnDef) -> None:
    """Validate value against column definition. Raises SchemaMismatchError on mismatch."""
    if value is None:
        if not column.nullable:
            raise SchemaMismatchError(
                f"Column '{column.name}' is NOT NULL but received NULL"
            )
        return

    col_type = column.data_type

    if col_type == DataType.INTEGER:
        if isinstance(value, float):
            raise SchemaMismatchError(
                f"Column '{column.name}' is INTEGER but received float: {value}. "
                "Implicit float-to-int conversion is not allowed."
            )
        if not isinstance(value, int):
            raise SchemaMismatchError(
                f"Column '{column.name}' is INTEGER but received {type(value).__name__}"
            )

    elif col_type == DataType.FLOAT:
        if not isinstance(value, (int, float)):
            raise SchemaMismatchError(
                f"Column '{column.name}' is FLOAT but received {type(value).__name__}"
            )

    elif col_type == DataType.TEXT:
        if not isinstance(value, str):
            raise SchemaMismatchError(
                f"Column '{column.name}' is TEXT but received {type(value).__name__}"
            )

    elif col_type == DataType.BOOLEAN:
        if not isinstance(value, bool):
            raise SchemaMismatchError(
                f"Column '{column.name}' is BOOLEAN but received {type(value).__name__}"
            )


def convert_value(value: object, column: ColumnDef) -> object:
    """Convert value to the target column type after validation."""
    validate_value(value, column)

    if value is None:
        return None

    if column.data_type == DataType.FLOAT and isinstance(value, int):
        return float(value)

    return value
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_types.py -v`
Expected: PASS (19 tests)

- [x] **Step 5: Commit**

```bash
git add tinydb/types.py tests/test_types.py
git commit -m "feat(types): add DataType, ColumnDef, Value with type validation"
```

---

## Task 3: RowFormat — NULL Bitmap & Serialization

**Files:**
- Create: `tinydb/row_format.py`
- Create: `tests/test_row_format.py`

**Interfaces:**
- Consumes: `tinydb.types` (DataType, ColumnDef)
- Produces: `serialize_row()`, `deserialize_row()`, `null_bitmap()`, `encode_null_flags()`, `decode_null_flags()`

- [x] **Step 1: Write the failing test**

```python
# tests/test_row_format.py
"""Tests for tinydb.row_format module."""
import pytest
from tinydb.types import ColumnDef, DataType
from tinydb.row_format import serialize_row, deserialize_row, encode_null_flags, decode_null_flags


class TestNullBitmap:
    def test_8_columns_1_byte(self):
        nulls = [False] * 8
        bitmap = encode_null_flags(nulls)
        assert len(bitmap) == 1

    def test_12_columns_2_bytes(self):
        nulls = [False] * 12
        bitmap = encode_null_flags(nulls)
        assert len(bitmap) == 2

    def test_1_column_1_byte(self):
        nulls = [True]
        bitmap = encode_null_flags(nulls)
        assert len(bitmap) == 1
        assert bitmap[0] == 0b00000001

    def test_decode_roundtrip(self):
        nulls = [True, False, True, False, False, False, False, False]
        bitmap = encode_null_flags(nulls)
        decoded = decode_null_flags(bitmap, 8)
        assert decoded == nulls


class TestSerializeRow:
    @pytest.fixture
    def columns(self):
        return [
            ColumnDef(name="id", data_type=DataType.INTEGER),
            ColumnDef(name="name", data_type=DataType.TEXT),
            ColumnDef(name="score", data_type=DataType.FLOAT),
            ColumnDef(name="active", data_type=DataType.BOOLEAN),
        ]

    def test_serialize_full_row(self, columns):
        row = [1, "Alice", 95.5, True]
        data = serialize_row(row, columns)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_serialize_with_null(self, columns):
        row = [2, None, None, False]
        data = serialize_row(row, columns)
        assert isinstance(data, bytes)

    def test_serialize_chinese_text(self, columns):
        row = [3, "张三", 88.0, True]
        data = serialize_row(row, columns)
        result = deserialize_row(data, columns)
        assert result[1] == "张三"


class TestDeserializeRow:
    @pytest.fixture
    def columns(self):
        return [
            ColumnDef(name="id", data_type=DataType.INTEGER),
            ColumnDef(name="name", data_type=DataType.TEXT),
            ColumnDef(name="score", data_type=DataType.FLOAT),
            ColumnDef(name="active", data_type=DataType.BOOLEAN),
        ]

    def test_roundtrip(self, columns):
        row = [1, "Alice", 95.5, True]
        data = serialize_row(row, columns)
        result = deserialize_row(data, columns)
        assert result == row

    def test_roundtrip_with_nulls(self, columns):
        row = [2, None, None, False]
        data = serialize_row(row, columns)
        result = deserialize_row(data, columns)
        assert result[0] == 2
        assert result[1] is None
        assert result[2] is None
        assert result[3] is False

    def test_roundtrip_chinese_text(self, columns):
        row = [3, "数据库", 100.0, True]
        data = serialize_row(row, columns)
        result = deserialize_row(data, columns)
        assert result == row
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_row_format.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

```python
# tinydb/row_format.py
"""Row serialization format: NULL bitmap + typed column encoding.

Row wire format:
  Header:
    - null_bitmap: ceil(n/8) bytes
    - num_columns: uint16
  Body (in column order):
    - INTEGER: 8 bytes (int64, little-endian)
    - FLOAT:   8 bytes (double, little-endian)
    - BOOLEAN: 1 byte (0 or 1)
    - TEXT:    4 bytes length (uint32) + UTF-8 bytes
"""
import struct
import math
from tinydb.types import DataType, ColumnDef


# Type markers for on-disk representation
_TYPE_MARKERS = {
    DataType.INTEGER: 1,
    DataType.FLOAT: 2,
    DataType.TEXT: 3,
    DataType.BOOLEAN: 4,
}

_HEADER_FMT = "<H"  # num_columns: uint16
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)

_INT_FMT = "<q"     # int64
_FLOAT_FMT = "<d"   # double
_BOOL_FMT = "<?"
_TEXT_LEN_FMT = "<I"  # uint32 for text length


def encode_null_flags(null_flags: list[bool]) -> bytes:
    """Encode a list of NULL flags into a bitmap (1 bit per column)."""
    n = len(null_flags)
    num_bytes = math.ceil(n / 8)
    bitmap = bytearray(num_bytes)

    for i, is_null in enumerate(null_flags):
        if is_null:
            byte_idx = i // 8
            bit_idx = i % 8
            bitmap[byte_idx] |= (1 << bit_idx)

    return bytes(bitmap)


def decode_null_flags(bitmap: bytes, num_columns: int) -> list[bool]:
    """Decode a bitmap into a list of NULL flags."""
    flags = []
    for i in range(num_columns):
        byte_idx = i // 8
        bit_idx = i % 8
        is_null = bool(bitmap[byte_idx] & (1 << bit_idx))
        flags.append(is_null)
    return flags


def serialize_row(values: list, columns: list[ColumnDef]) -> bytes:
    """Serialize a row (list of values) into bytes."""
    n = len(columns)
    null_flags = [v is None for v in values]

    # Header
    result = bytearray()
    result.extend(encode_null_flags(null_flags))
    result.extend(struct.pack(_HEADER_FMT, n))

    # Body: serialize each non-NULL column
    for i, (val, col) in enumerate(zip(values, columns)):
        if val is None:
            continue  # NULL values are only recorded in bitmap

        if col.data_type == DataType.INTEGER:
            result.extend(struct.pack(_INT_FMT, val))
        elif col.data_type == DataType.FLOAT:
            fval = float(val) if isinstance(val, int) else val
            result.extend(struct.pack(_FLOAT_FMT, fval))
        elif col.data_type == DataType.TEXT:
            encoded = val.encode("utf-8")
            result.extend(struct.pack(_TEXT_LEN_FMT, len(encoded)))
            result.extend(encoded)
        elif col.data_type == DataType.BOOLEAN:
            result.extend(struct.pack(_BOOL_FMT, val))

    return bytes(result)


def deserialize_row(data: bytes, columns: list[ColumnDef]) -> list:
    """Deserialize bytes back into a row (list of values)."""
    if not data:
        return []

    # Read bitmap
    n = len(columns)
    num_bitmap_bytes = math.ceil(n / 8)
    bitmap = data[:num_bitmap_bytes]
    null_flags = decode_null_flags(bitmap, n)

    # Read num_columns header
    offset = num_bitmap_bytes
    num_columns = struct.unpack_from(_HEADER_FMT, data, offset)[0]
    offset += _HEADER_SIZE

    # Read values
    result = []
    for i in range(num_columns):
        if null_flags[i]:
            result.append(None)
            continue

        col = columns[i]
        if col.data_type == DataType.INTEGER:
            val = struct.unpack_from(_INT_FMT, data, offset)[0]
            offset += struct.calcsize(_INT_FMT)
        elif col.data_type == DataType.FLOAT:
            val = struct.unpack_from(_FLOAT_FMT, data, offset)[0]
            offset += struct.calcsize(_FLOAT_FMT)
        elif col.data_type == DataType.TEXT:
            text_len = struct.unpack_from(_TEXT_LEN_FMT, data, offset)[0]
            offset += struct.calcsize(_TEXT_LEN_FMT)
            val = data[offset:offset + text_len].decode("utf-8")
            offset += text_len
        elif col.data_type == DataType.BOOLEAN:
            val = struct.unpack_from(_BOOL_FMT, data, offset)[0]
            offset += struct.calcsize(_BOOL_FMT)
        else:
            val = None

        result.append(val)

    return result
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_row_format.py -v`
Expected: PASS (8 tests)

- [x] **Step 5: Commit**

```bash
git add tinydb/row_format.py tests/test_row_format.py
git commit -m "feat(row-format): implement NULL bitmap and row serialization"
```

---

## Task 4: Page — Slotted Page Structure

**Files:**
- Create: `tinydb/page.py`
- Create: `tests/test_page.py`

**Interfaces:**
- Consumes: `tinydb.constants`, `tinydb.row_format`
- Produces: `Page`, `PageType`, `RowId`, `create_empty_page()`, `parse_page_header()`, `pack_page_header()`

- [x] **Step 1: Write the failing test**

```python
# tests/test_page.py
"""Tests for tinydb.page module."""
import pytest
from tinydb.page import (
    Page, PageType, RowId, PAGE_HEADER_FORMAT,
    create_empty_page, parse_page_header, pack_page_header,
    insert_row_into_page, get_row_from_page, delete_row_from_page,
    get_all_rows_from_page, get_free_space,
)
from tinydb.constants import PAGE_SIZE, PAGE_HEADER_SIZE, SLOT_SIZE, MAX_FREE_SPACE


class TestPageType:
    def test_page_type_values(self):
        assert PageType.DATA.value == 1
        assert PageType.CATALOG.value == 2
        assert PageType.INDEX.value == 3


class TestRowId:
    def test_row_id_creation(self):
        rid = RowId(page_id=5, slot_index=3)
        assert rid.page_id == 5
        assert rid.slot_index == 3

    def test_row_id_immutable(self):
        rid = RowId(page_id=5, slot_index=3)
        with pytest.raises(AttributeError):
            rid.page_id = 10


class TestPageHeader:
    def test_pack_unpack_roundtrip(self):
        header = {
            "page_id": 42,
            "page_type": PageType.DATA,
            "slot_count": 3,
            "free_space": 3000,
            "free_offset": 3500,
            "next_page_id": 0,
            "flags": 0,
        }
        data = pack_page_header(**header)
        assert len(data) == PAGE_HEADER_SIZE
        parsed = parse_page_header(data)
        assert parsed["page_id"] == 42
        assert parsed["page_type"] == PageType.DATA
        assert parsed["slot_count"] == 3
        assert parsed["free_space"] == 3000
        assert parsed["free_offset"] == 3500

    def test_header_size_is_32(self):
        assert PAGE_HEADER_SIZE == 32


class TestPageCreation:
    def test_create_empty_data_page(self):
        page = create_empty_page(page_id=1, page_type=PageType.DATA)
        assert isinstance(page, Page)
        assert page.page_id == 1
        assert page.page_type == PageType.DATA
        assert page.slot_count == 0
        assert page.dirty is False
        assert len(page.data) == PAGE_SIZE


class TestPageOperations:
    @pytest.fixture
    def page(self):
        return create_empty_page(page_id=1, page_type=PageType.DATA)

    def test_insert_row(self, page):
        row_data = b"hello world row data"
        slot_idx = insert_row_into_page(page, row_data)
        assert slot_idx == 0
        assert page.slot_count == 1
        assert page.dirty is True

    def test_insert_and_get_row(self, page):
        row_data = b"test data"
        slot_idx = insert_row_into_page(page, row_data)
        retrieved = get_row_from_page(page, slot_idx)
        assert retrieved == row_data

    def test_insert_multiple_rows(self, page):
        rows = [b"row1", b"row2", b"row3"]
        for i, row in enumerate(rows):
            slot_idx = insert_row_into_page(page, row)
            assert slot_idx == i
        assert page.slot_count == 3
        all_rows = get_all_rows_from_page(page)
        assert all_rows == rows

    def test_delete_row(self, page):
        slot_idx = insert_row_into_page(page, b"to be deleted")
        delete_row_from_page(page, slot_idx)
        retrieved = get_row_from_page(page, slot_idx)
        assert retrieved is None

    def test_free_space_decreases_after_insert(self, page):
        initial_free = get_free_space(page)
        insert_row_into_page(page, b"some data that takes space")
        assert get_free_space(page) < initial_free

    def test_get_free_space_initial(self, page):
        # Empty page: free space = MAX_FREE_SPACE
        assert get_free_space(page) == MAX_FREE_SPACE
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_page.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

```python
# tinydb/page.py
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
from dataclasses import dataclass, field
from enum import Enum
from tinydb.constants import (
    PAGE_SIZE, PAGE_HEADER_SIZE, SLOT_SIZE, MAX_FREE_SPACE,
)
from tinydb.exceptions import PageOutOfRangeError

# Page header: page_id(I) page_type(B) slot_count(H) free_space(H) free_offset(H) next_page_id(I) flags(B) padding(13s)
PAGE_HEADER_FORMAT = "<IBHHHIB13s"
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

    @property
    def slot_count(self) -> int:
        header = parse_page_header(self.data)
        return header["slot_count"]


def create_empty_page(page_id: int, page_type: PageType) -> Page:
    """Create a new empty page with initialized header."""
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
    """Pack page header fields into 32 bytes."""
    return struct.pack(
        PAGE_HEADER_FORMAT,
        page_id,
        page_type.value,
        slot_count,
        free_space,
        free_offset,
        next_page_id,
        flags,
        b"\x00" * 13,
    )


def parse_page_header(data: bytes) -> dict:
    """Unpack 32 bytes into a dict of header fields."""
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
    """Write a slot entry in the slot array."""
    slot_offset = PAGE_HEADER_SIZE + slot_idx * SLOT_SIZE
    struct.pack_into("<HH", data, slot_offset, offset, length)


def _read_slot(data: bytes, slot_idx: int) -> tuple[int, int]:
    """Read (offset, length) for a given slot index."""
    slot_offset = PAGE_HEADER_SIZE + slot_idx * SLOT_SIZE
    return struct.unpack_from("<HH", data, slot_offset)


def get_free_space(page: Page) -> int:
    """Get remaining free space in the page."""
    header = parse_page_header(page.data)
    return header["free_space"]


def insert_row_into_page(page: Page, row_data: bytes) -> int:
    """Insert row_data into the page. Returns the slot index."""
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

    # Write row data at new_free_offset
    data[new_free_offset:new_free_offset + row_len] = row_data

    # Write slot entry
    _write_slot(data, slot_idx, new_free_offset, row_len)

    # Update header
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
    """Retrieve row data by slot index. Returns None if slot is empty/deleted."""
    data = page.data
    header = parse_page_header(data)

    if slot_idx >= header["slot_count"]:
        return None

    offset, length = _read_slot(data, slot_idx)

    # Deleted rows have length=0 and offset=0
    if length == 0:
        return None

    return data[offset:offset + length]


def delete_row_from_page(page: Page, slot_idx: int) -> None:
    """Mark a row as deleted by zeroing its slot length."""
    data = bytearray(page.data)
    header = parse_page_header(bytes(data))

    if slot_idx >= header["slot_count"]:
        raise PageOutOfRangeError(f"Slot {slot_idx} out of range")

    # Zero out the slot
    _write_slot(data, slot_idx, 0, 0)

    # Note: we don't reclaim space for deleted rows (simplified for teaching)
    new_free_space = header["free_space"]  # unchanged

    new_header = pack_page_header(
        page_id=header["page_id"],
        page_type=header["page_type"],
        slot_count=header["slot_count"],
        free_space=new_free_space,
        free_offset=header["free_offset"],
        next_page_id=header["next_page_id"],
        flags=header["flags"],
    )
    data[:PAGE_HEADER_SIZE] = new_header

    page.data = bytes(data)
    page.dirty = True


def get_all_rows_from_page(page: Page) -> list[bytes]:
    """Get all valid (non-deleted) rows from the page."""
    result = []
    for i in range(page.slot_count):
        row = get_row_from_page(page, i)
        if row is not None:
            result.append(row)
    return result
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_page.py -v`
Expected: PASS (14 tests)

- [x] **Step 5: Commit**

```bash
git add tinydb/page.py tests/test_page.py
git commit -m "feat(page): implement Slotted Page with header, slots, and row ops"
```

---

## Task 5: FileManager — File Header & Page I/O

**Files:**
- Create: `tinydb/file_manager.py`
- Create: `tests/test_file_manager.py`

**Interfaces:**
- Consumes: `tinydb.constants`, `tinydb.page`
- Produces: `FileManager`, `open_database()`, `close_database()`, `read_page()`, `write_page()`, `alloc_page()`, `free_page()`

- [x] **Step 1: Write the failing test**

```python
# tests/test_file_manager.py
"""Tests for tinydb.file_manager module."""
import os
import pytest
from tinydb.file_manager import FileManager
from tinydb.page import create_empty_page, PageType, parse_page_header
from tinydb.exceptions import StorageCorruptionError, PageOutOfRangeError
from tinydb.constants import MAGIC, PAGE_SIZE


class TestFileManagerOpen:
    def test_create_new_database(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        assert os.path.exists(db_path)
        assert fm.page_count == 1
        fm.close()

    def test_open_existing_database(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        fm.close()

        fm2 = FileManager(db_path)
        fm2.open()
        assert fm2.page_count == 1
        fm2.close()

    def test_invalid_magic_rejected(self, tmp_path):
        db_path = str(tmp_path / "corrupt.db")
        with open(db_path, "wb") as f:
            f.write(b"NODB\0" + b"\x00" * 100)
        fm = FileManager(db_path)
        with pytest.raises(StorageCorruptionError):
            fm.open()


class TestFileManagerPageIO:
    @pytest.fixture
    def fm(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        yield fm
        fm.close()

    def test_read_page_zero(self, fm):
        page = fm.read_page(0)
        assert isinstance(page, bytes)
        assert len(page) == PAGE_SIZE

    def test_alloc_page(self, fm):
        page_id = fm.alloc_page()
        assert page_id == 1  # page 0 is header, first alloc is page 1
        assert fm.page_count == 2

    def test_alloc_multiple_pages(self, fm):
        ids = [fm.alloc_page() for _ in range(5)]
        assert ids == [1, 2, 3, 4, 5]
        assert fm.page_count == 6

    def test_write_and_read_page(self, fm):
        page = create_empty_page(1, PageType.DATA)
        fm.write_page(1, page.page_id, page.page_type, page.data)
        data = fm.read_page(1)
        assert len(data) == PAGE_SIZE

    def test_read_out_of_range_page(self, fm):
        with pytest.raises(PageOutOfRangeError):
            fm.read_page(9999)

    def test_free_page(self, fm):
        page_id = fm.alloc_page()
        fm.free_page(page_id)
        # free page should be re-usable
        new_id = fm.alloc_page()
        assert new_id == page_id

    def test_close_flushes_metadata(self, fm):
        fm.alloc_page()
        initial_count = fm.page_count
        fm.close()

        fm2 = FileManager(fm.db_path)
        fm2.open()
        assert fm2.page_count == initial_count
        fm2.close()
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_file_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

```python
# tinydb/file_manager.py
"""FileManager: handles file I/O, page allocation, and free list management.

.db file layout:
  Page 0: File Header
    - magic:          b"TINYDB\0" (8 bytes)
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
    MAGIC, VERSION, PAGE_SIZE, PAGE_TYPE_DATA,
)
from tinydb.page import (
    Page, PageType, create_empty_page, parse_page_header, pack_page_header,
)
from tinydb.exceptions import StorageCorruptionError, PageOutOfRangeError, StorageFullError


# File header format (excluding magic):
# version(I) page_size(I) page_count(I) free_list_head(I) catalog_root(I) checksum(Q)
_HEADER_FMT = "<IIIIIQ"
_HEADER_META_SIZE = struct.calcsize(_HEADER_FMT)
_HEADER_TOTAL_SIZE = PAGE_SIZE  # header occupies full first page


class FileManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._file = None
        self.page_count = 0
        self.free_list_head = 0
        self.catalog_root = 0

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

    def write_page(self, page_id: int, page_type: PageType, data: bytes) -> None:
        """Write page data to disk at the given page_id."""
        if page_id >= self.page_count:
            raise PageOutOfRangeError(
                f"Page {page_id} out of range (page_count={self.page_count})"
            )
        if len(data) != PAGE_SIZE:
            raise ValueError(f"Page data must be {PAGE_SIZE} bytes, got {len(data)}")

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
            next_free = parse_page_header(raw)["next_page_id"]
            self.free_list_head = next_free
            self._write_header()
            return page_id

        # No free pages: extend file
        page_id = self.page_count
        self.page_count += 1
        self._write_header()
        # Write empty page data
        self._file.seek(page_id * PAGE_SIZE)
        self._file.write(b"\x00" * PAGE_SIZE)
        self._file.flush()
        return page_id

    def free_page(self, page_id: int) -> None:
        """Return a page to the free list."""
        if page_id == 0:
            raise PageOutOfRangeError("Cannot free page 0 (header)")

        raw = bytearray(self.read_page(page_id))
        header = parse_page_header(bytes(raw))

        # Update header to point to current free list head
        new_header = pack_page_header(
            page_id=header["page_id"],
            page_type=PageType(header["page_type"]) if isinstance(header["page_type"], int) else header["page_type"],
            slot_count=0,
            free_space=0,
            free_offset=PAGE_SIZE,
            next_page_id=self.free_list_head,
            flags=0,
        )
        raw[:len(new_header)] = new_header

        self.write_page(page_id, PageType.DATA, bytes(raw))
        self.free_list_head = page_id
        self._write_header()

    def _init_new_database(self) -> None:
        """Initialize a fresh database file."""
        # Write header page
        self.page_count = 1
        self.free_list_head = 0
        self.catalog_root = 0
        self._write_header()

    def _read_header(self) -> None:
        """Read and verify file header."""
        self._file.seek(0)
        raw_header = self._file.read(PAGE_SIZE)

        # Check magic
        magic = raw_header[: len(MAGIC)]
        if magic != MAGIC:
            raise StorageCorruptionError(
                f"Invalid magic bytes: expected {MAGIC!r}, got {magic!r}"
            )

        # Parse header fields
        offset = 8  # after magic
        fields = struct.unpack_from(_HEADER_FMT, raw_header, offset)
        version, page_size, page_count, free_list_head, catalog_root, checksum = fields

        if version != VERSION:
            raise StorageCorruptionError(
                f"Unsupported version: {version}, expected {VERSION}"
            )

        if page_size != PAGE_SIZE:
            raise StorageCorruptionError(
                f"Page size mismatch: {page_size} != {PAGE_SIZE}"
            )

        # Verify checksum (over the header data before checksum field)
        header_data = raw_header[offset:offset + _HEADER_META_SIZE]
        computed_checksum = zlib.crc32(header_data) & 0xFFFFFFFFFFFFFFFF
        if computed_checksum != checksum:
            raise StorageCorruptionError(
                f"Checksum mismatch: computed {computed_checksum:#x}, "
                f"stored {checksum:#x}"
            )

        self.page_count = page_count
        self.free_list_head = free_list_head
        self.catalog_root = catalog_root

    def _write_header(self) -> None:
        """Write header page to disk."""
        raw = bytearray(PAGE_SIZE)
        raw[: len(MAGIC)] = MAGIC

        offset = 8
        # We need to compute checksum over the data, so write a placeholder first
        # then compute and patch
        placeholder_checksum = 0
        struct.pack_into(
            _HEADER_FMT,
            raw,
            offset,
            VERSION,
            PAGE_SIZE,
            self.page_count,
            self.free_list_head,
            self.catalog_root,
            placeholder_checksum,
        )

        # Compute checksum
        header_data = raw[offset:offset + _HEADER_META_SIZE]
        checksum = zlib.crc32(header_data) & 0xFFFFFFFFFFFFFFFF
        struct.pack_into("<Q", raw, offset + _HEADER_META_SIZE - 8, checksum)

        self._file.seek(0)
        self._file.write(bytes(raw))
        self._file.flush()
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_file_manager.py -v`
Expected: PASS (9 tests)

- [x] **Step 5: Commit**

```bash
git add tinydb/file_manager.py tests/test_file_manager.py
git commit -m "feat(file-manager): implement file header, page I/O, free list allocator"
```

---

## Task 6: BufferPool — LRU Cache with Pin/Unpin

**Files:**
- Create: `tinydb/buffer_pool.py`
- Create: `tests/test_buffer_pool.py`

**Interfaces:**
- Consumes: `tinydb.file_manager`, `tinydb.page`, `tinydb.constants`
- Produces: `BufferPool`, `LRU_Node`, `get_page()`, `flush()`, `pin()`, `unpin()`

- [x] **Step 1: Write the failing test**

```python
# tests/test_buffer_pool.py
"""Tests for tinydb.buffer_pool module."""
import pytest
from unittest.mock import MagicMock
from tinydb.buffer_pool import BufferPool, LRU_Node
from tinydb.page import create_empty_page, PageType, parse_page_header
from tinydb.constants import PAGE_SIZE


class TestLRUNode:
    def test_node_creation(self):
        node = LRU_Node(page_id=1, page=None)
        assert node.page_id == 1
        assert node.page is None
        assert node.prev is None
        assert node.next is None
        assert node.ref_count == 0


class TestBufferPool:
    @pytest.fixture
    def mock_fm(self):
        """A mock FileManager that returns synthetic pages."""
        fm = MagicMock()
        fm.read_page.side_effect = lambda pid: _make_page_bytes(pid)
        fm.page_count = 100
        return fm

    def test_get_page_not_in_cache(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        data = pool.get_page(1)
        assert isinstance(data, bytes)
        assert len(data) == PAGE_SIZE
        mock_fm.read_page.assert_called_once_with(1)

    def test_get_page_cache_hit(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        pool.get_page(1)
        mock_fm.read_page.assert_called_once_with(1)
        # Second access should be cached
        pool.get_page(1)
        mock_fm.read_page.assert_called_once()  # still only 1 read

    def test_eviction_when_full(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=3)
        pool.get_page(1)
        pool.get_page(2)
        pool.get_page(3)
        # Pool is full. Accessing page 4 should evict the LRU (page 1)
        pool.get_page(4)
        # page 1 should have been evicted
        assert 1 not in pool._cache
        assert 4 in pool._cache

    def test_access_marks_as_recently_used(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=3)
        pool.get_page(1)
        pool.get_page(2)
        pool.get_page(3)
        # Access page 1 to make it recently used
        pool.get_page(1)
        # Now add page 4, should evict page 2 (oldest)
        pool.get_page(4)
        assert 2 not in pool._cache
        assert 1 in pool._cache

    def test_pin_prevents_eviction(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=3)
        pool.get_page(1)
        pool.get_page(2)
        pool.get_page(3)
        pool.pin(4)
        pool.get_page(4)  # pin also fetches
        # Pool has 4 entries but capacity=3, yet pin prevents eviction
        assert 4 in pool._cache
        # Add page 5, LRU (page 1) should be evicted, not page 4
        pool.get_page(5)
        assert 1 not in pool._cache
        assert 4 in pool._cache

    def test_unpin_allows_eviction(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=3)
        pool.get_page(1)
        pool.get_page(2)
        pool.get_page(3)
        pool.unpin(1)
        # Access page 4, should evict page 1 (now unpinned, LRU)
        pool.get_page(4)
        assert 1 not in pool._cache

    def test_flush_writes_dirty_pages(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        # Mark a page as dirty
        pool.get_page(1)
        pool.mark_dirty(1)
        pool.flush()
        mock_fm.write_page.assert_called()

    def test_evict_dirty_page_flushes_first(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=2)
        pool.get_page(1)
        pool.mark_dirty(1)
        pool.get_page(2)
        # Pool full. Access page 3, must evict page 1 (dirty) — should flush
        mock_fm.write_page.reset_mock()
        pool.get_page(3)
        mock_fm.write_page.assert_called_once()


def _make_page_bytes(page_id: int) -> bytes:
    """Helper to create valid page bytes for mock read_page."""
    data = bytearray(PAGE_SIZE)
    # Write a minimal valid header
    from tinydb.page import pack_page_header
    header = pack_page_header(
        page_id=page_id,
        page_type=PageType.DATA,
        slot_count=0,
        free_space=PAGE_SIZE - 32,
        free_offset=PAGE_SIZE,
        next_page_id=0,
        flags=0,
    )
    data[:len(header)] = header
    return bytes(data)
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_buffer_pool.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

```python
# tinydb/buffer_pool.py
"""Buffer Pool with LRU eviction and pin/unpin support.

Two-layer design for educational clarity:
  1. OrderedDict layer: provides O(1) lookup and move_to_end
  2. Doubly-linked list layer: explicit LRU for teaching purposes

The doubly-linked list is the "source of truth" for eviction order.
OrderedDict provides fast membership checks.
"""
from collections import OrderedDict
from tinydb.constants import DEFAULT_BUFFER_POOL_CAPACITY
from tinydb.page import Page, PageType
from tinydb.exceptions import PageOutOfRangeError


class LRU_Node:
    """Doubly-linked list node for LRU tracking."""

    def __init__(self, page_id: int, page: Page):
        self.page_id = page_id
        self.page = page
        self.prev: "LRU_Node | None" = None
        self.next: "LRU_Node | None" = None
        self.ref_count: int = 0  # pin count


class BufferPool:
    """LRU buffer pool with pin/unpin and dirty page management."""

    def __init__(self, file_manager, capacity: int = DEFAULT_BUFFER_POOL_CAPACITY):
        self._fm = file_manager
        self._capacity = capacity
        self._cache: OrderedDict[int, LRU_Node] = OrderedDict()

        # Doubly-linked list boundaries
        self._head = None  # most recently used
        self._tail = None  # least recently used

    @property
    def size(self) -> int:
        return len(self._cache)

    def get_page(self, page_id: int) -> Page:
        """Get a page from cache or disk."""
        if page_id in self._cache:
            node = self._cache[page_id]
            self._cache.move_to_end(page_id)
            self._move_to_head(node)
            return node.page

        # Fetch from disk
        raw = self._fm.read_page(page_id)
        header = self._parse_header_from_bytes(raw)
        page = Page(
            page_id=page_id,
            page_type=header["page_type"],
            data=raw,
            dirty=False,
        )

        # Insert into pool
        self._insert_page(page_id, page)
        return page

    def mark_dirty(self, page_id: int) -> None:
        """Mark a cached page as dirty."""
        if page_id in self._cache:
            self._cache[page_id].page.dirty = True

    def pin(self, page_id: int) -> None:
        """Pin a page to prevent eviction."""
        if page_id in self._cache:
            self._cache[page_id].ref_count += 1

    def unpin(self, page_id: int) -> None:
        """Unpin a page, making it eligible for eviction again."""
        if page_id in self._cache:
            node = self._cache[page_id]
            if node.ref_count > 0:
                node.ref_count -= 1

    def flush(self) -> None:
        """Write all dirty pages to disk."""
        for node in self._cache.values():
            if node.page.dirty:
                self._fm.write_page(node.page_id, node.page.page_type, node.page.data)
                node.page.dirty = False

    # --- Internal doubly-linked list operations ---

    def _insert_page(self, page_id: int, page: Page) -> None:
        """Insert page into cache, evicting if necessary."""
        # Evict if at capacity
        while len(self._cache) >= self._capacity:
            self._evict_one()

        node = LRU_Node(page_id, page)
        self._cache[page_id] = node
        self._insert_head(node)

    def _evict_one(self) -> None:
        """Evict the LRU page that is not pinned."""
        # Find eviction candidate from tail upward
        candidate = self._tail
        while candidate is not None and candidate.ref_count > 0:
            candidate = candidate.prev

        if candidate is None:
            # All pages pinned — cannot evict
            raise PageOutOfRangeError(
                "Buffer pool full and all pages are pinned"
            )

        # Flush dirty page
        if candidate.page.dirty:
            self._fm.write_page(candidate.page_id, candidate.page.page_type, candidate.page.data)
            candidate.page.dirty = False

        # Remove from linked list
        self._remove_node(candidate)

        # Remove from cache
        del self._cache[candidate.page_id]

    def _insert_head(self, node: LRU_Node) -> None:
        """Insert node at head (most recently used)."""
        node.prev = None
        node.next = self._head
        if self._head:
            self._head.prev = node
        self._head = node
        if self._tail is None:
            self._tail = node

    def _remove_node(self, node: LRU_Node) -> None:
        """Remove node from linked list."""
        if node.prev:
            node.prev.next = node.next
        else:
            self._head = node.next

        if node.next:
            node.next.prev = node.prev
        else:
            self._tail = node.prev

        node.prev = None
        node.next = None

    def _move_to_head(self, node: LRU_Node) -> None:
        """Move an existing node to head (mark as recently used)."""
        if node is self._head:
            return
        self._remove_node(node)
        self._insert_head(node)

    @staticmethod
    def _parse_header_from_bytes(data: bytes) -> dict:
        """Parse page header from raw bytes (re-using page module logic)."""
        return parse_page_header(data)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_buffer_pool.py -v`
Expected: PASS (9 tests)

- [x] **Step 5: Commit**

```bash
git add tinydb/buffer_pool.py tests/test_buffer_pool.py
git commit -m "feat(buffer-pool): implement LRU cache with pin/unpin and dirty page flush"
```

---

## Task 7: Catalog — System Catalog Table

**Files:**
- Create: `tinydb/catalog.py`
- Create: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `tinydb.buffer_pool`, `tinydb.file_manager`, `tinydb.page`, `tinydb.row_format`
- Produces: `Catalog`, `TableMeta`, `load()`, `save()`, `create_table()`, `drop_table()`, `get_table()`, `list_tables()`

- [x] **Step 1: Write the failing test**

```python
# tests/test_catalog.py
"""Tests for tinydb.catalog module."""
import pytest
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog, TableMeta
from tinydb.types import ColumnDef, DataType
from tinydb.exceptions import TableExistsError, TableNotFoundError


class TestCatalog:
    @pytest.fixture
    def catalog(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        pool = BufferPool(fm, capacity=50)
        cat = Catalog(fm, pool)
        cat.load()
        yield cat
        fm.close()

    def test_list_tables_initially_empty(self, catalog):
        assert catalog.list_tables() == []

    def test_create_table(self, catalog):
        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False, primary_key=True),
            ColumnDef(name="name", data_type=DataType.TEXT),
        ]
        catalog.create_table("users", columns, pk="id")
        tables = catalog.list_tables()
        assert "users" in tables

    def test_create_existing_table_raises(self, catalog):
        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
        ]
        catalog.create_table("users", columns, pk="id")
        with pytest.raises(TableExistsError):
            catalog.create_table("users", columns, pk="id")

    def test_get_table_metadata(self, catalog):
        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="name", data_type=DataType.TEXT),
        ]
        catalog.create_table("users", columns, pk="id")
        meta = catalog.get_table("users")
        assert isinstance(meta, TableMeta)
        assert meta.table_name == "users"
        assert meta.primary_key == "id"
        assert len(meta.columns) == 2
        assert meta.root_page > 0

    def test_get_nonexistent_table_raises(self, catalog):
        with pytest.raises(TableNotFoundError):
            catalog.get_table("nonexistent")

    def test_drop_table(self, catalog):
        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
        ]
        catalog.create_table("temp", columns, pk="id")
        catalog.drop_table("temp")
        assert "temp" not in catalog.list_tables()

    def test_persistence(self, tmp_path):
        """Tables survive close + reopen."""
        db_path = str(tmp_path / "persist.db")

        # Create and save
        fm = FileManager(db_path)
        fm.open()
        pool = BufferPool(fm, capacity=50)
        cat = Catalog(fm, pool)
        cat.load()
        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
        ]
        cat.create_table("persistent", columns, pk="id")
        cat.save()
        fm.close()

        # Reopen
        fm2 = FileManager(db_path)
        fm2.open()
        pool2 = BufferPool(fm2, capacity=50)
        cat2 = Catalog(fm2, pool2)
        cat2.load()
        assert "persistent" in cat2.list_tables()
        meta = cat2.get_table("persistent")
        assert meta.table_name == "persistent"
        fm2.close()
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

```python
# tinydb/catalog.py
"""System catalog: manages table metadata in tinydb_master table.

tinydb_master table schema:
  - table_name: TEXT (primary key)
  - columns:    TEXT (JSON array of column definitions)
  - root_page:  INTEGER
  - primary_key: TEXT
"""
import json
from dataclasses import dataclass
from tinydb.types import ColumnDef, DataType, convert_value, validate_value
from tinydb.row_format import serialize_row, deserialize_row
from tinydb.page import (
    Page, PageType, RowId, create_empty_page,
    insert_row_into_page, get_row_from_page, get_all_rows_from_page,
    get_free_space, parse_page_header, pack_page_header,
)
from tinydb.constants import CATALOG_TABLE_NAME
from tinydb.exceptions import TableExistsError, TableNotFoundError


# Catalog table column definitions
_CATALOG_COLUMNS = [
    ColumnDef(name="table_name", data_type=DataType.TEXT, nullable=False),
    ColumnDef(name="columns", data_type=DataType.TEXT, nullable=False),
    ColumnDef(name="root_page", data_type=DataType.INTEGER, nullable=False),
    ColumnDef(name="primary_key", data_type=DataType.TEXT, nullable=False),
]


@dataclass
class TableMeta:
    table_name: str
    columns: list[ColumnDef]
    root_page: int
    primary_key: str


class Catalog:
    """Manages table metadata persistence."""

    def __init__(self, file_manager, buffer_pool):
        self._fm = file_manager
        self._pool = buffer_pool
        self._tables: dict[str, TableMeta] = {}
        self._catalog_page_id: int = 0

    def load(self) -> None:
        """Load catalog from disk. Creates catalog table if not exists."""
        # Check if catalog table exists (catalog_root stored in file header)
        self._catalog_page_id = self._fm.catalog_root

        if self._catalog_page_id == 0:
            # First run: initialize catalog
            self._init_catalog()
        else:
            self._load_from_disk()

    def save(self) -> None:
        """Persist catalog to disk. Write all pages and flush."""
        self._save_to_disk()
        self._pool.flush()

    def create_table(self, name: str, columns: list[ColumnDef], pk: str) -> None:
        """Register a new table in the catalog."""
        if name in self._tables:
            raise TableExistsError(f"Table '{name}' already exists")

        # Allocate a root page for the table's data
        root_page = self._fm.alloc_page()

        meta = TableMeta(
            table_name=name,
            columns=columns,
            root_page=root_page,
            primary_key=pk,
        )
        self._tables[name] = meta

        # Write to catalog page
        self._write_table_meta(meta)

    def drop_table(self, name: str) -> None:
        """Remove a table from the catalog."""
        if name not in self._tables:
            raise TableNotFoundError(f"Table '{name}' not found")

        del self._tables[name]
        # NOTE: In a full implementation we'd also free the data pages.
        # For teaching purposes, we keep it simple.

    def get_table(self, name: str) -> TableMeta:
        """Get table metadata by name."""
        if name not in self._tables:
            raise TableNotFoundError(f"Table '{name}' not found")
        return self._tables[name]

    def list_tables(self) -> list[str]:
        """List all registered table names."""
        return list(self._tables.keys())

    # --- Internal methods ---

    def _init_catalog(self) -> None:
        """Create the initial catalog table."""
        self._catalog_page_id = self._fm.alloc_page()
        self._fm.catalog_root = self._catalog_page_id
        self._fm._write_header()

        # Initialize the catalog page
        empty_page = create_empty_page(self._catalog_page_id, PageType.CATALOG)
        self._fm.write_page(
            self._catalog_page_id,
            PageType.CATALOG,
            empty_page.data,
        )

    def _load_from_disk(self) -> None:
        """Read all table metadata from catalog pages."""
        page_id = self._catalog_page_id
        while page_id != 0:
            raw = self._fm.read_page(page_id)
            header = parse_page_header(raw)
            page = Page(
                page_id=page_id,
                page_type=PageType.CATALOG,
                data=raw,
                dirty=False,
            )

            # Read all rows
            rows = get_all_rows_from_page(page)
            for row_data in rows:
                values = deserialize_row(row_data, _CATALOG_COLUMNS)
                if values is None:
                    continue
                table_name = values[0]
                columns_json = values[1]
                root_page = values[2]
                primary_key = values[3]

                columns = self._parse_columns_json(columns_json)
                self._tables[table_name] = TableMeta(
                    table_name=table_name,
                    columns=columns,
                    root_page=root_page,
                    primary_key=primary_key,
                )

            page_id = header["next_page_id"]

    def _write_table_meta(self, meta: TableMeta) -> None:
        """Write a single table's metadata into the catalog page."""
        columns_json = json.dumps([
            {
                "name": col.name,
                "data_type": col.data_type.value,
                "nullable": col.nullable,
                "primary_key": col.primary_key,
                "unique": col.unique,
            }
            for col in meta.columns
        ])

        row = [meta.table_name, columns_json, meta.root_page, meta.primary_key]
        serialized = serialize_row(row, _CATALOG_COLUMNS)

        # Read current page, insert row, write back
        raw = self._fm.read_page(self._catalog_page_id)
        page = Page(
            page_id=self._catalog_page_id,
            page_type=PageType.CATALOG,
            data=raw,
            dirty=True,
        )
        insert_row_into_page(page, serialized)
        self._fm.write_page(self._catalog_page_id, PageType.CATALOG, page.data)

    def _save_to_disk(self) -> None:
        """Rewrite the catalog pages from in-memory state."""
        # Simple implementation: clear catalog page and re-write all entries
        page = create_empty_page(self._catalog_page_id, PageType.CATALOG)
        for meta in self._tables.values():
            columns_json = json.dumps([
                {
                    "name": col.name,
                    "data_type": col.data_type.value,
                    "nullable": col.nullable,
                    "primary_key": col.primary_key,
                    "unique": col.unique,
                }
                for col in meta.columns
            ])
            row = [meta.table_name, columns_json, meta.root_page, meta.primary_key]
            serialized = serialize_row(row, _CATALOG_COLUMNS)
            insert_row_into_page(page, serialized)

        self._fm.write_page(self._catalog_page_id, PageType.CATALOG, page.data)

    @staticmethod
    def _parse_columns_json(json_str: str) -> list[ColumnDef]:
        """Parse JSON back into ColumnDef list."""
        items = json.loads(json_str)
        return [
            ColumnDef(
                name=item["name"],
                data_type=DataType(item["data_type"]),
                nullable=item.get("nullable", True),
                primary_key=item.get("primary_key", False),
                unique=item.get("unique", False),
            )
            for item in items
        ]
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog.py -v`
Expected: PASS (7 tests)

- [x] **Step 5: Commit**

```bash
git add tinydb/catalog.py tests/test_catalog.py
git commit -m "feat(catalog): implement system catalog with table metadata persistence"
```

---

## Task 8: Table — CRUD API (Insert/Scan/Get/Delete/Update)

**Files:**
- Create: `tinydb/table.py`
- Create: `tests/test_table.py`

**Interfaces:**
- Consumes: `tinydb.buffer_pool`, `tinydb.catalog`, `tinydb.types`, `tinydb.row_format`
- Produces: `Table`, `insert()`, `scan()`, `get()`, `delete()`, `update()`

- [x] **Step 1: Write the failing test**

```python
# tests/test_table.py
"""Tests for tinydb.table module."""
import pytest
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.types import ColumnDef, DataType, convert_value
from tinydb.exceptions import SchemaMismatchError
from tinydb.page import PageType


class TestTableCRUD:
    @pytest.fixture
    def table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        pool = BufferPool(fm, capacity=50)
        cat = Catalog(fm, pool)
        cat.load()

        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="name", data_type=DataType.TEXT, nullable=True),
            ColumnDef(name="score", data_type=DataType.FLOAT, nullable=True),
        ]
        cat.create_table("students", columns, pk="id")

        tbl = cat.get_table("students")
        yield tbl, pool, cat, columns
        fm.close()

    def test_insert_returns_rowid(self, table):
        tbl, pool, cat, columns = table
        rid = tbl.insert(pool, [1, "Alice", 95.5])
        assert rid is not None
        assert rid.page_id > 0

    def test_insert_and_get(self, table):
        tbl, pool, cat, columns = table
        rid = tbl.insert(pool, [1, "Alice", 95.5])
        result = tbl.get(pool, rid)
        assert result[0] == 1
        assert result[1] == "Alice"
        assert abs(result[2] - 95.5) < 0.001

    def test_insert_with_null(self, table):
        tbl, pool, cat, columns = table
        rid = tbl.insert(pool, [2, None, None])
        result = tbl.get(pool, rid)
        assert result[0] == 2
        assert result[1] is None
        assert result[2] is None

    def test_insert_type_mismatch_raises(self, table):
        tbl, pool, cat, columns = table
        with pytest.raises(SchemaMismatchError):
            tbl.insert(pool, ["not_an_int", "Alice", 95.5])

    def test_scan_all_rows(self, table):
        tbl, pool, cat, columns = table
        tbl.insert(pool, [1, "Alice", 95.5])
        tbl.insert(pool, [2, "Bob", 88.0])
        tbl.insert(pool, [3, "Charlie", 72.5])

        rows = list(tbl.scan(pool))
        assert len(rows) == 3
        # Check we get (rowId, row) tuples
        rids = [r[0] for r in rows]
        values = [r[1] for r in rows]
        assert all(r.page_id > 0 for r in rids)
        names = [v[1] for v in values]
        assert "Alice" in names
        assert "Bob" in names

    def test_scan_empty_table(self, table):
        tbl, pool, cat, columns = table
        rows = list(tbl.scan(pool))
        assert rows == []

    def test_delete_row(self, table):
        tbl, pool, cat, columns = table
        rid = tbl.insert(pool, [1, "Alice", 95.5])
        tbl.delete(pool, rid)
        result = tbl.get(pool, rid)
        assert result is None

    def test_update_row(self, table):
        tbl, pool, cat, columns = table
        rid = tbl.insert(pool, [1, "Alice", 95.5])
        tbl.update(pool, rid, [1, "Alice Updated", 99.0])
        result = tbl.get(pool, rid)
        assert result[1] == "Alice Updated"
        assert abs(result[2] - 99.0) < 0.001

    def test_insert_many_crossing_pages(self, table):
        """Insert enough rows to cross page boundary."""
        tbl, pool, cat, columns = table
        for i in range(100):
            tbl.insert(pool, [i, f"user_{i}", float(i)])

        rows = list(tbl.scan(pool))
        assert len(rows) == 100
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_table.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

```python
# tinydb/table.py
"""Table-level CRUD API.

INSERT: find slot with enough space → serialize row → write to page
SCAN:   traverse page chain → pin each page → read all rows → unpin
GET:    locate page + slot → deserialize row
DELETE: mark slot as deleted
UPDATE: in-place update if space allows, else delete + re-insert
"""
from tinydb.types import ColumnDef, convert_value
from tinydb.row_format import serialize_row, deserialize_row
from tinydb.page import (
    PageType, RowId, create_empty_page,
    insert_row_into_page, get_row_from_page, delete_row_from_page,
    get_all_rows_from_page, get_free_space, parse_page_header, pack_page_header,
)


class Table:
    """Provides row-level CRUD operations on a table's data pages."""

    def __init__(self, table_name: str, columns: list[ColumnDef], root_page: int):
        self.table_name = table_name
        self.columns = columns
        self.root_page = root_page

    def insert(self, buffer_pool, row: list) -> RowId:
        """Insert a row. Returns the RowId."""
        # Validate and convert values
        converted = []
        for val, col in zip(row, self.columns):
            converted.append(convert_value(val, col))

        serialized = serialize_row(converted, self.columns)

        # Traverse page chain to find space
        page_id = self.root_page
        data_page_id = None

        while page_id != 0:
            page = buffer_pool.get_page(page_id)
            if page.page_type != PageType.DATA:
                break
            if get_free_space(page) >= len(serialized) + 4:  # 4 = slot entry
                data_page_id = page_id
                break
            header = parse_page_header(page.data)
            page_id = header["next_page_id"]

        if data_page_id is None:
            # No room: allocate new page and append to chain
            data_page_id = buffer_pool._fm.alloc_page()
            # Update previous page's next_page_id
            header = parse_page_header(buffer_pool.get_page(page_id).data)
            page_data = bytearray(buffer_pool.get_page(page_id).data)
            new_header = pack_page_header(
                page_id=header["page_id"],
                page_type=header["page_type"],
                slot_count=header["slot_count"],
                free_space=header["free_space"],
                free_offset=header["free_offset"],
                next_page_id=data_page_id,
                flags=header["flags"],
            )
            page_data[:len(new_header)] = new_header
            buffer_pool._cache[page_id].page.data = bytes(page_data)
            buffer_pool._cache[page_id].page.dirty = True
            buffer_pool.mark_dirty(page_id)

            # Create new empty data page
            new_page = create_empty_page(data_page_id, PageType.DATA)
            buffer_pool._fm.write_page(data_page_id, PageType.DATA, new_page.data)

        # Insert the row
        page = buffer_pool.get_page(data_page_id)
        slot_idx = insert_row_into_page(page, serialized)

        # Mark dirty in buffer pool
        buffer_pool._cache[data_page_id].page.data = page.data
        buffer_pool.mark_dirty(data_page_id)

        return RowId(page_id=data_page_id, slot_index=slot_idx)

    def scan(self, buffer_pool):
        """Yield (RowId, row_values) tuples for all rows in the table."""
        page_id = self.root_page

        while page_id != 0:
            page = buffer_pool.get_page(page_id)
            if page.page_type != PageType.DATA:
                break

            header = parse_page_header(page.data)

            # Read all valid rows from this page
            for slot_idx in range(header["slot_count"]):
                row_data = get_row_from_page(page, slot_idx)
                if row_data is None:
                    continue
                values = deserialize_row(row_data, self.columns)
                if values is not None:
                    yield RowId(page_id=page_id, slot_index=slot_idx), values

            page_id = header["next_page_id"]

    def get(self, buffer_pool, row_id: RowId) -> list | None:
        """Get a single row by RowId."""
        page = buffer_pool.get_page(row_id.page_id)
        row_data = get_row_from_page(page, row_id.slot_index)
        if row_data is None:
            return None
        return deserialize_row(row_data, self.columns)

    def delete(self, buffer_pool, row_id: RowId) -> None:
        """Delete a row by RowId."""
        page = buffer_pool.get_page(row_id.page_id)
        delete_row_from_page(page, row_id.slot_index)

        # Mark dirty
        buffer_pool._cache[row_id.page_id].page.data = page.data
        buffer_pool.mark_dirty(row_id.page_id)

    def update(self, buffer_pool, row_id: RowId, new_row: list) -> None:
        """Update a row in-place if space allows."""
        # Validate and convert
        converted = []
        for val, col in zip(new_row, self.columns):
            converted.append(convert_value(val, col))

        serialized = serialize_row(converted, self.columns)

        page = buffer_pool.get_page(row_id.page_id)
        header = parse_page_header(page.data)

        # For simplicity: delete old + insert new
        self.delete(buffer_pool, row_id)
        # Re-insert (will find space, possibly on same page)
        # We need to find space again - reuse insert logic
        # But we already deleted, just need to put the data back
        slot_idx = insert_row_into_page(page, serialized)
        buffer_pool._cache[row_id.page_id].page.data = page.data
        buffer_pool.mark_dirty(row_id.page_id)
```

- [x] **Step 4: Update Catalog to provide Table instances**

Update `catalog.py` to make `get_table()` return a `Table` instance instead of just metadata. Modify the Catalog class:

```python
# In catalog.py, add import at top:
from tinydb.table import Table

# Replace the get_table return to also provide a Table wrapper:
def get_table(self, name: str) -> Table:
    """Get a Table object for the named table."""
    if name not in self._tables:
        raise TableNotFoundError(f"Table '{name}' not found")
    meta = self._tables[name]
    return Table(meta.table_name, meta.columns, meta.root_page)
```

Apply that change to `tinydb/catalog.py`.

- [x] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_table.py -v`
Expected: PASS (10 tests)

- [x] **Step 6: Commit**

```bash
git add tinydb/table.py tinydb/catalog.py tests/test_table.py
git commit -m "feat(table): implement insert/scan/get/delete/update CRUD API"
```

---

## Task 9: Integration Tests

**Files:**
- Create: `tests/test_integration.py`

**Interfaces:**
- Consumes: all modules

- [x] **Step 1: Write integration tests**

```python
# tests/test_integration.py
"""End-to-end integration tests for tinydb storage engine."""
import pytest
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.types import ColumnDef, DataType


class TestEndToEnd:
    @pytest.fixture
    def db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        pool = BufferPool(fm, capacity=100)
        cat = Catalog(fm, pool)
        cat.load()
        yield fm, pool, cat
        fm.close()

    def test_full_crud_lifecycle(self, db):
        fm, pool, cat = db

        # Create table
        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="name", data_type=DataType.TEXT),
        ]
        cat.create_table("users", columns, pk="id")

        # Insert
        tbl = cat.get_table("users")
        rid1 = tbl.insert(pool, [1, "Alice"])
        rid2 = tbl.insert(pool, [2, "Bob"])

        # Read
        assert tbl.get(pool, rid1)[1] == "Alice"
        assert tbl.get(pool, rid2)[1] == "Bob"

        # Update
        tbl.update(pool, rid1, [1, "Alice Updated"])
        assert tbl.get(pool, rid1)[1] == "Alice Updated"

        # Delete
        tbl.delete(pool, rid2)
        assert tbl.get(pool, rid2) is None

        # Scan
        rows = list(tbl.scan(pool))
        assert len(rows) == 1
        assert rows[0][1][1] == "Alice Updated"

    def test_persistence_across_reopen(self, db):
        fm, pool, cat = db

        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="value", data_type=DataType.TEXT),
        ]
        cat.create_table("kv", columns, pk="id")

        tbl = cat.get_table("kv")
        for i in range(50):
            tbl.insert(pool, [i, f"val_{i}"])

        cat.save()
        fm.close()

        # Reopen
        fm2 = FileManager(str(fm.db_path))
        fm2.open()
        pool2 = BufferPool(fm2, capacity=100)
        cat2 = Catalog(fm2, pool2)
        cat2.load()

        tbl2 = cat2.get_table("kv")
        rows = list(tbl2.scan(pool2))
        assert len(rows) == 50
        assert rows[0][1][1] == "val_0"
        assert rows[49][1][1] == "val_49"

        fm2.close()

    def test_multiple_tables(self, db):
        fm, pool, cat = db

        cat.create_table("users", [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="name", data_type=DataType.TEXT),
        ], pk="id")

        cat.create_table("orders", [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="user_id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="amount", data_type=DataType.FLOAT),
        ], pk="id")

        users = cat.get_table("users")
        orders = cat.get_table("orders")

        users.insert(pool, [1, "Alice"])
        orders.insert(pool, [100, 1, 42.5])
        orders.insert(pool, [101, 1, 30.0])

        assert len(list(users.scan(pool))) == 1
        assert len(list(orders.scan(pool))) == 2

    def test_multi_page_scan(self, db):
        """Data spanning multiple pages is correctly scanned."""
        fm, pool, cat = db

        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="data", data_type=DataType.TEXT),
        ]
        cat.create_table("big", columns, pk="id")

        tbl = cat.get_table("big")
        # Insert enough rows to span multiple pages
        n_rows = 200
        for i in range(n_rows):
            tbl.insert(pool, [i, f"data_{i}" * 20])

        rows = list(tbl.scan(pool))
        assert len(rows) == n_rows

        # Verify ordering by id
        ids = [r[1][0] for r in rows]
        assert ids == list(range(n_rows))
```

- [x] **Step 2: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: PASS (4 tests)

- [x] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: PASS (all tests across all modules)

- [x] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(integration): add end-to-end CRUD and persistence tests"
```

---

## Task 10: `__init__.py` Public API

**Files:**
- Modify: `tinydb/__init__.py`

**Interfaces:**
- Consumes: all modules
- Produces: public API exports

- [x] **Step 1: Update public API**

```python
# tinydb/__init__.py
"""tinydb: a tiny embedded relational database for learning."""

from tinydb.types import DataType, ColumnDef, Value
from tinydb.exceptions import (
    StorageError,
    StorageCorruptionError,
    PageOutOfRangeError,
    TableExistsError,
    TableNotFoundError,
    SchemaMismatchError,
    StorageFullError,
)
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog, TableMeta
from tinydb.table import Table
from tinydb.page import Page, PageType, RowId

__all__ = [
    "DataType",
    "ColumnDef",
    "Value",
    "StorageError",
    "StorageCorruptionError",
    "PageOutOfRangeError",
    "TableExistsError",
    "TableNotFoundError",
    "SchemaMismatchError",
    "StorageFullError",
    "FileManager",
    "BufferPool",
    "Catalog",
    "TableMeta",
    "Table",
    "Page",
    "PageType",
    "RowId",
]
```

- [x] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: PASS

- [x] **Step 3: Commit**

```bash
git add tinydb/__init__.py
git commit -m "feat: expose public API in tinydb __init__.py"
```

---

## Dependency Graph

```
Task 1 (Setup)
  └── Task 2 (TypeSystem) — standalone
        └── Task 3 (RowFormat) — needs TypeSystem
        └── Task 4 (Page) — standalone
              └── Task 5 (FileManager) — needs Page
                    └── Task 6 (BufferPool) — needs Page + FileManager
                          └── Task 7 (Catalog) — needs BufferPool + Page + RowFormat
                                └── Task 8 (Table) — needs Catalog + BufferPool + RowFormat
                                      └── Task 9 (Integration) — needs all
                                            └── Task 10 (Public API) — finalization
```

## TDD Strategy Summary

| Module | Tests | Approach |
|--------|-------|----------|
| TypeSystem | 19 tests | Write all type-check scenarios first, then implement |
| RowFormat | 8 tests | Roundtrip property tests, NULL bitmap edge cases |
| Page | 14 tests | Slot CRUD, free space tracking, header roundtrip |
| FileManager | 9 tests | Free list alloc/free, open/close lifecycle, corruption detection |
| BufferPool | 9 tests | LRU order verification via mock FileManager, pin blocks eviction |
| Catalog | 7 tests | Table create/get/drop, persistence across reopen |
| Table | 10 tests | CRUD operations, multi-page scan, type validation |
| Integration | 4 tests | Full lifecycle, persistence, multi-table, large dataset |

## Test Execution Commands

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/test_types.py -v
pytest tests/test_row_format.py -v
pytest tests/test_page.py -v
pytest tests/test_file_manager.py -v
pytest tests/test_buffer_pool.py -v
pytest tests/test_catalog.py -v
pytest tests/test_table.py -v
pytest tests/test_integration.py -v

# Run with coverage (optional)
pytest tests/ --cov=tinydb --cov-report=term-missing
```
