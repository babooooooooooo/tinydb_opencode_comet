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

        class MockCond:
            column = "age"
            op = "="
            value = 30

        meta = imgr.find_matching_index("users", MockCond())
        assert meta is not None
        assert meta.name == "idx_users_age"
