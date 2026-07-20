# tests/sql/test_join_integration.py
"""End-to-end JOIN integration tests."""
import tempfile
from pathlib import Path
from tinydb.database import Database


def make_db():
    """Create a test database with users and orders tables."""
    tmp = tempfile.mkdtemp()
    db_path = str(Path(tmp) / "test.db")
    db = Database(db_path)
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
    db.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
    db.execute("INSERT INTO users VALUES (3, 'Charlie', 35)")

    db.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER)")
    db.execute("INSERT INTO orders VALUES (1, 1, 100)")
    db.execute("INSERT INTO orders VALUES (2, 1, 200)")
    db.execute("INSERT INTO orders VALUES (3, 2, 150)")
    return db


class TestDatabaseJoin:
    def test_inner_join_end_to_end(self):
        db = make_db()
        result = db.execute(
            "SELECT u.id, u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert result.row_count == 3
        amounts = sorted([r[2] for r in result.rows])
        assert amounts == [100, 150, 200]
        db.close()

    def test_select_star_with_join(self):
        db = make_db()
        result = db.execute(
            "SELECT * FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert result.row_count == 3
        assert "name" in result.columns
        assert "amount" in result.columns
        db.close()


class TestAllJoinTypes:
    def test_inner_join(self):
        db = make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u INNER JOIN orders o ON u.id = o.user_id"
        )
        assert result.row_count == 3
        db.close()

    def test_left_join(self):
        db = make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u LEFT JOIN orders o ON u.id = o.user_id"
        )
        # 3 matched + 1 unmatched (Charlie) = 4
        assert result.row_count == 4
        charlie = [r for r in result.rows if r[0] == "Charlie"]
        assert len(charlie) == 1
        assert charlie[0][1] is None
        db.close()

    def test_left_outer_join(self):
        db = make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u LEFT OUTER JOIN orders o ON u.id = o.user_id"
        )
        assert result.row_count == 4
        db.close()

    def test_cross_join(self):
        db = make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u CROSS JOIN orders"
        )
        # 3 users × 3 orders = 9
        assert result.row_count == 9
        db.close()

    def test_natural_join(self):
        db = make_db()
        result = db.execute(
            "SELECT * FROM users NATURAL JOIN orders"
        )
        # NATURAL JOIN on "id" column: users.id=1 matches orders.id=1, etc.
        assert result.row_count == 3
        db.close()

    def test_join_with_where(self):
        db = make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE o.amount > 150"
        )
        assert result.row_count == 1
        assert result.rows[0][1] == 200
        db.close()

    def test_join_with_order_by(self):
        db = make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id ORDER BY o.amount DESC"
        )
        amounts = [r[1] for r in result.rows]
        assert amounts == [200, 150, 100]
        db.close()

    def test_join_with_limit(self):
        db = make_db()
        result = db.execute(
            "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id LIMIT 2"
        )
        assert result.row_count == 2
        db.close()


class TestEdgeCases:
    def _make_db(self):
        tmp = tempfile.mkdtemp()
        db_path = str(Path(tmp) / "test.db")
        db = Database(db_path)
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, 'Bob')")
        db.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount INTEGER)")
        db.execute("INSERT INTO orders VALUES (1, 1, 100)")
        return db

    def test_self_join(self):
        """Self-join: join a table to itself using aliases."""
        db = self._make_db()
        result = db.execute(
            "SELECT a.name, b.name FROM users a JOIN users b ON a.id <> b.id"
        )
        # 2 users × 1 other = 2 rows
        assert result.row_count == 2
        db.close()

    def test_empty_table_join(self):
        """Join with empty table returns no rows (INNER) or NULLs (LEFT)."""
        db = self._make_db()
        db.execute("CREATE TABLE empty (id INTEGER PRIMARY KEY)")

        result = db.execute(
            "SELECT u.name FROM users u INNER JOIN empty e ON u.id = e.id"
        )
        assert result.row_count == 0

        result = db.execute(
            "SELECT u.name FROM users u LEFT JOIN empty e ON u.id = e.id"
        )
        assert result.row_count == 2  # both users preserved with NULLs
        db.close()

    def test_null_in_join_key(self):
        """NULL values should not match in join conditions."""
        db = self._make_db()
        db.execute("INSERT INTO orders VALUES (2, NULL, 50)")

        result = db.execute(
            "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id"
        )
        # NULL user_id should not match any user
        assert result.row_count == 1  # only Alice's order
        db.close()

    def test_column_name_conflict(self):
        """When both tables have 'id', output should prefix with alias."""
        db = self._make_db()
        result = db.execute(
            "SELECT * FROM users u JOIN orders o ON u.id = o.user_id LIMIT 1"
        )
        row = result.rows[0]
        # Both tables have 'id' → should be prefixed
        assert len(row) == len(result.columns)
        db.close()


class TestRegression:
    def test_single_table_queries_unchanged(self):
        """Verify v0.1 single-table queries still work."""
        tmp = tempfile.mkdtemp()
        db_path = str(Path(tmp) / "test.db")
        db = Database(db_path)
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
        db.execute("INSERT INTO users VALUES (3, 'Charlie', 35)")

        # Simple select
        result = db.execute("SELECT id, name FROM users")
        assert result.row_count == 3

        # WHERE
        result = db.execute("SELECT name FROM users WHERE id = 1")
        assert result.row_count == 1
        assert result.rows[0][0] == "Alice"

        # ORDER BY
        result = db.execute("SELECT name FROM users ORDER BY name ASC")
        names = [r[0] for r in result.rows]
        assert names == ["Alice", "Bob", "Charlie"]

        # LIMIT
        result = db.execute("SELECT name FROM users LIMIT 2")
        assert result.row_count == 2

        # SELECT *
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 3
        assert "id" in result.columns
        assert "name" in result.columns
        assert "age" in result.columns

        db.close()
