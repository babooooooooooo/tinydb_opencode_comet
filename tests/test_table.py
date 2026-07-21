# tests/test_table.py
"""Tests for tinydb.table module."""
import pytest
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.types import ColumnDef, DataType
from tinydb.exceptions import SchemaMismatchError


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
