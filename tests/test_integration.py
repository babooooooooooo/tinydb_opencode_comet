# tests/test_integration.py
"""端到端集成测试：验证存储引擎各模块协同工作。"""
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

        # 建表
        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="name", data_type=DataType.TEXT),
        ]
        cat.create_table("users", columns, pk="id")

        # 插入
        tbl = cat.get_table("users")
        rid1 = tbl.insert(pool, [1, "Alice"])
        rid2 = tbl.insert(pool, [2, "Bob"])

        # 查询
        assert tbl.get(pool, rid1)[1] == "Alice"
        assert tbl.get(pool, rid2)[1] == "Bob"

        # 更新
        tbl.update(pool, rid1, [1, "Alice Updated"])
        assert tbl.get(pool, rid1)[1] == "Alice Updated"

        # 删除
        tbl.delete(pool, rid2)
        assert tbl.get(pool, rid2) is None

        # 全表扫描
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

        # 重新打开数据库
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
        """跨多页的数据能够被正确扫描。"""
        fm, pool, cat = db

        columns = [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="data", data_type=DataType.TEXT),
        ]
        cat.create_table("big", columns, pk="id")

        tbl = cat.get_table("big")
        # 插入足够多的行以跨越多个页
        n_rows = 200
        for i in range(n_rows):
            tbl.insert(pool, [i, f"data_{i}" * 20])

        rows = list(tbl.scan(pool))
        assert len(rows) == n_rows

        # 验证按 id 排序
        ids = [r[1][0] for r in rows]
        assert ids == list(range(n_rows))
