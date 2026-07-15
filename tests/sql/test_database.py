"""Tests for Database entry point."""
import pytest
from tinydb.sql.database import Database
from tinydb.sql.result import QueryResult
from tinydb.sql.errors import SQLError


class TestDatabase:
    def test_create_table(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        result = db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        assert isinstance(result, QueryResult)
        assert result.row_count == 0
        db.close()

    def test_insert_and_select(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        result = db.execute("SELECT id, name FROM users")
        assert result.row_count == 1
        assert result.columns == ["id", "name"]
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["name"] == "Alice"
        db.close()

    def test_select_star(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 1
        assert "id" in result.rows[0]
        assert "name" in result.rows[0]
        db.close()

    def test_select_where(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, 'Bob')")
        result = db.execute("SELECT * FROM users WHERE id = 1")
        assert result.row_count == 1
        assert result.rows[0]["name"] == "Alice"
        db.close()

    def test_update(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        result = db.execute("UPDATE users SET name = 'Alice2' WHERE id = 1")
        assert result.row_count == 1
        result = db.execute("SELECT name FROM users WHERE id = 1")
        assert result.rows[0]["name"] == "Alice2"
        db.close()

    def test_delete(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, 'Bob')")
        result = db.execute("DELETE FROM users WHERE id = 1")
        assert result.row_count == 1
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 1
        db.close()

    def test_drop_table(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        result = db.execute("DROP TABLE users")
        assert result.row_count == 0
        db.close()

    def test_count_star(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, 'Bob')")
        result = db.execute("SELECT COUNT(*) FROM users")
        assert result.row_count == 1
        assert result.rows[0]["count_*"] == 2
        db.close()

    def test_order_by(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Charlie')")
        db.execute("INSERT INTO users VALUES (2, 'Alice')")
        db.execute("INSERT INTO users VALUES (3, 'Bob')")
        result = db.execute("SELECT name FROM users ORDER BY name ASC")
        names = [r["name"] for r in result.rows]
        assert names == ["Alice", "Bob", "Charlie"]
        db.close()

    def test_limit(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        for i in range(5):
            db.execute(f"INSERT INTO users VALUES ({i}, 'user_{i}')")
        result = db.execute("SELECT * FROM users LIMIT 3")
        assert result.row_count == 3
        db.close()

    def test_multi_row_insert(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'A'), (2, 'B'), (3, 'C')")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 3
        db.close()

    def test_is_null(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, NULL)")
        result = db.execute("SELECT * FROM users WHERE name IS NULL")
        assert result.row_count == 1
        assert result.rows[0]["id"] == 2
        db.close()

    def test_is_not_null(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, NULL)")
        result = db.execute("SELECT * FROM users WHERE name IS NOT NULL")
        assert result.row_count == 1
        assert result.rows[0]["id"] == 1
        db.close()

    def test_sql_error_propagation(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        with pytest.raises(SQLError):
            db.execute("SELECT * FROM nonexistent")
        db.close()

    def test_context_manager(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
            db.execute("INSERT INTO users VALUES (1, 'Alice')")
            result = db.execute("SELECT * FROM users")
            assert result.row_count == 1
