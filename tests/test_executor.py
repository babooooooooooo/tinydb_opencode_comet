# tests/test_executor.py
import pytest
from tinydb.sql.executor import IndexScanOperator
from tinydb.sql.planner import Planner
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
        assert len(results) == 2

    def test_range_scan(self, db_env):
        fm, pool, cat, tbl, imgr = db_env
        meta = imgr.get_index("users", "age")

        class MockCond:
            column = "age"
            op = ">"
            value = 30

        op = IndexScanOperator(tbl, meta, MockCond())
        results = list(op.execute(pool))
        assert len(results) == 2


