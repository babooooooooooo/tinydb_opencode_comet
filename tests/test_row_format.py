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
