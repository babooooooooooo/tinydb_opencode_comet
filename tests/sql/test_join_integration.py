# tests/sql/test_join_integration.py
"""End-to-end JOIN integration tests."""
import tempfile
from pathlib import Path
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.sql.database import Database
from tinydb.types import ColumnDef, DataType


def make_db():
    """Create a test database with users and orders tables."""
    tmp = tempfile.mkdtemp()
    db_path = str(Path(tmp) / "test.db")
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    cat = Catalog(fm, pool)
    cat.load()

    cat.create_table("users", [
        ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
        ColumnDef(name="name", data_type=DataType.TEXT),
        ColumnDef(name="age", data_type=DataType.INTEGER),
    ], pk="id")
    users_tbl = cat.get_table("users")
    users_tbl.insert(pool, [1, "Alice", 30])
    users_tbl.insert(pool, [2, "Bob", 25])
    users_tbl.insert(pool, [3, "Charlie", 35])

    cat.create_table("orders", [
        ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
        ColumnDef(name="user_id", data_type=DataType.INTEGER),
        ColumnDef(name="amount", data_type=DataType.INTEGER),
    ], pk="id")
    orders_tbl = cat.get_table("orders")
    orders_tbl.insert(pool, [1, 1, 100])
    orders_tbl.insert(pool, [2, 1, 200])
    orders_tbl.insert(pool, [3, 2, 150])

    return db_path, fm, pool, cat


class TestDatabaseJoin:
    def test_inner_join_end_to_end(self):
        db_path, fm, pool, cat = make_db()
        db = Database.__new__(Database)
        db.file_manager = fm
        db.buffer_pool = pool
        db.catalog = cat
        db._planner = cat  # will be replaced

        from tinydb.sql.planner import Planner
        db._planner = Planner(cat, pool)

        result = db.execute(
            "SELECT u.id, u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert result.row_count == 3
        amounts = sorted([r["amount"] for r in result.rows])
        assert amounts == [100, 150, 200]
        fm.close()

    def test_select_star_with_join(self):
        db_path, fm, pool, cat = make_db()
        from tinydb.sql.planner import Planner
        db = Database.__new__(Database)
        db.file_manager = fm
        db.buffer_pool = pool
        db.catalog = cat
        db._planner = Planner(cat, pool)

        result = db.execute(
            "SELECT * FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert result.row_count == 3
        # Should have columns from both tables
        assert "name" in result.columns
        assert "amount" in result.columns
        fm.close()


class TestAllJoinTypes:
    def _make_db(self):
        tmp = tempfile.mkdtemp()
        db_path = str(Path(tmp) / "test.db")
        fm = FileManager(db_path)
        fm.open()
        pool = BufferPool(fm, capacity=100)
        cat = Catalog(fm, pool)
        cat.load()

        cat.create_table("users", [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="name", data_type=DataType.TEXT),
        ], pk="id")
        users_tbl = cat.get_table("users")
        users_tbl.insert(pool, [1, "Alice"])
        users_tbl.insert(pool, [2, "Bob"])
        users_tbl.insert(pool, [3, "Charlie"])

        cat.create_table("orders", [
            ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
            ColumnDef(name="user_id", data_type=DataType.INTEGER),
            ColumnDef(name="amount", data_type=DataType.INTEGER),
        ], pk="id")
        orders_tbl = cat.get_table("orders")
        orders_tbl.insert(pool, [1, 1, 100])
        orders_tbl.insert(pool, [2, 1, 200])
        orders_tbl.insert(pool, [3, 2, 150])

        from tinydb.sql.planner import Planner
        db = Database.__new__(Database)
        db.file_manager = fm
        db.buffer_pool = pool
        db.catalog = cat
        db._planner = Planner(cat, pool)
        return db, fm

    def test_inner_join(self):
        db, fm = self._make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u INNER JOIN orders o ON u.id = o.user_id"
        )
        assert result.row_count == 3
        fm.close()

    def test_left_join(self):
        db, fm = self._make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u LEFT JOIN orders o ON u.id = o.user_id"
        )
        # 3 matched + 1 unmatched (Charlie) = 4
        assert result.row_count == 4
        charlie = [r for r in result.rows if r.get("name") == "Charlie"]
        assert len(charlie) == 1
        assert charlie[0]["amount"] is None
        fm.close()

    def test_left_outer_join(self):
        db, fm = self._make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u LEFT OUTER JOIN orders o ON u.id = o.user_id"
        )
        assert result.row_count == 4
        fm.close()

    def test_cross_join(self):
        db, fm = self._make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u CROSS JOIN orders"
        )
        # 3 users × 3 orders = 9
        assert result.row_count == 9
        fm.close()

    def test_natural_join(self):
        db, fm = self._make_db()
        result = db.execute(
            "SELECT * FROM users NATURAL JOIN orders"
        )
        # NATURAL JOIN on "id" column: users.id=1 matches orders.id=1, etc.
        assert result.row_count == 3
        fm.close()

    def test_join_with_where(self):
        db, fm = self._make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE o.amount > 150"
        )
        assert result.row_count == 1
        assert result.rows[0]["amount"] == 200
        fm.close()

    def test_join_with_order_by(self):
        db, fm = self._make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id ORDER BY o.amount DESC"
        )
        amounts = [r["amount"] for r in result.rows]
        assert amounts == [200, 150, 100]
        fm.close()

    def test_join_with_limit(self):
        db, fm = self._make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id LIMIT 2"
        )
        assert result.row_count == 2
        fm.close()
