# tests/test_catalog.py
"""Tests for tinydb.catalog module."""
import pytest
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
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
        from tinydb.table import Table
        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="name", data_type=DataType.TEXT),
        ]
        catalog.create_table("users", columns, pk="id")
        tbl = catalog.get_table("users")
        assert isinstance(tbl, Table)
        assert tbl.table_name == "users"
        assert tbl.primary_key == "id"
        assert len(tbl.columns) == 2
        assert tbl.root_page > 0

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
