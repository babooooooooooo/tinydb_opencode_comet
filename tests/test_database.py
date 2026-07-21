# tests/test_database.py
import pytest
from tinydb.database import Database


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    database.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    yield database
    database.close()


class TestDatabase:
    def test_execute_insert(self, db):
        result = db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        assert result.row_count == 1

    def test_execute_select(self, db):
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        db.execute("INSERT INTO users VALUES (2, 'Bob', 25)")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 2
        assert result.columns == ["id", "name", "age"]

    def test_execute_update(self, db):
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        result = db.execute("UPDATE users SET age = 31 WHERE id = 1")
        assert result.row_count == 1

    def test_execute_delete(self, db):
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        result = db.execute("DELETE FROM users WHERE id = 1")
        assert result.row_count == 1

    def test_context_manager(self, tmp_path):
        with Database(str(tmp_path / "test.db")) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            db.execute("INSERT INTO t VALUES (1)")
            result = db.execute("SELECT * FROM t")
            assert result.row_count == 1

    def test_commit_rollback(self, db):
        db.execute("BEGIN")
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        db.execute("ROLLBACK")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 0
