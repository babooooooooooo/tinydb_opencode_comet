"""Tests for constraint enforcement."""
import pytest
from tinydb.sql.database import Database
from tinydb.sql.errors import ConstraintError


class TestNotNullConstraint:
    def test_not_null_violation(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        with pytest.raises(ConstraintError, match="NOT NULL"):
            db.execute("INSERT INTO users VALUES (1, NULL)")
        db.close()

    def test_not_null_valid(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 1
        db.close()


class TestPrimaryKeyConstraint:
    def test_primary_key_duplicate(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        with pytest.raises(ConstraintError, match="PRIMARY KEY"):
            db.execute("INSERT INTO users VALUES (1, 'Bob')")
        db.close()

    def test_primary_key_unique(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, 'Bob')")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 2
        db.close()


class TestUniqueConstraint:
    def test_unique_violation(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)")
        db.execute("INSERT INTO users VALUES (1, 'a@b.com')")
        with pytest.raises(ConstraintError, match="UNIQUE"):
            db.execute("INSERT INTO users VALUES (2, 'a@b.com')")
        db.close()

    def test_unique_valid(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)")
        db.execute("INSERT INTO users VALUES (1, 'a@b.com')")
        db.execute("INSERT INTO users VALUES (2, 'c@d.com')")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 2
        db.close()
