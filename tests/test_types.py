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
