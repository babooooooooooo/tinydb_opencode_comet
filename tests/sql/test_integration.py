"""End-to-end integration tests for SQL engine."""
import pytest
from tinydb.sql.database import Database
from tinydb.sql.result import QueryResult
from tinydb.sql.errors import SQLError, ConstraintError


class TestCRUDLifecycle:
    def test_full_crud(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
            db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
            db.execute("INSERT INTO users VALUES (2, 'Bob', 25)")

            result = db.execute("SELECT * FROM users ORDER BY id")
            assert result.row_count == 2

            db.execute("UPDATE users SET age = 31 WHERE id = 1")
            result = db.execute("SELECT age FROM users WHERE id = 1")
            assert result.rows[0]["age"] == 31

            db.execute("DELETE FROM users WHERE id = 2")
            result = db.execute("SELECT * FROM users")
            assert result.row_count == 1


class TestComplexQueries:
    def test_where_with_and_or(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, a INTEGER, b INTEGER)")
            db.execute("INSERT INTO t VALUES (1, 10, 20)")
            db.execute("INSERT INTO t VALUES (2, 10, 30)")
            db.execute("INSERT INTO t VALUES (3, 20, 20)")

            result = db.execute("SELECT * FROM t WHERE a = 10 AND b = 20")
            assert result.row_count == 1
            assert result.rows[0]["id"] == 1

    def test_group_by_with_count(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount FLOAT)")
            db.execute("INSERT INTO orders VALUES (1, 1, 10.0)")
            db.execute("INSERT INTO orders VALUES (2, 1, 20.0)")
            db.execute("INSERT INTO orders VALUES (3, 2, 15.0)")

            result = db.execute("SELECT user_id, COUNT(*) FROM orders GROUP BY user_id ORDER BY user_id")
            assert result.row_count == 2

    def test_sum_and_avg(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE scores (id INTEGER PRIMARY KEY, score FLOAT)")
            db.execute("INSERT INTO scores VALUES (1, 80.0)")
            db.execute("INSERT INTO scores VALUES (2, 90.0)")
            db.execute("INSERT INTO scores VALUES (3, 100.0)")

            result = db.execute("SELECT SUM(score) FROM scores")
            assert result.rows[0]["sum"] == 270.0

            result = db.execute("SELECT AVG(score) FROM scores")
            assert result.rows[0]["avg"] == 90.0


class TestEdgeCases:
    def test_empty_table_select(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE empty (id INTEGER PRIMARY KEY)")
            result = db.execute("SELECT * FROM empty")
            assert result.row_count == 0
            assert result.rows == []

    def test_limit_beyond_count(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            db.execute("INSERT INTO t VALUES (1)")
            result = db.execute("SELECT * FROM t LIMIT 100")
            assert result.row_count == 1

    def test_offset_beyond_count(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            db.execute("INSERT INTO t VALUES (1)")
            result = db.execute("SELECT * FROM t OFFSET 100")
            assert result.row_count == 0

    def test_multi_row_insert_three_rows(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
            db.execute("INSERT INTO t VALUES (1, 'A'), (2, 'B'), (3, 'C')")
            result = db.execute("SELECT * FROM t ORDER BY id")
            assert result.row_count == 3
            assert result.rows[0]["name"] == "A"
            assert result.rows[2]["name"] == "C"


class TestErrorHandling:
    def test_syntax_error(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            with pytest.raises(SQLError):
                db.execute("SELLECT id FROM users")

    def test_table_not_found(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            with pytest.raises(SQLError):
                db.execute("SELECT * FROM nonexistent")

    def test_duplicate_table(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            with pytest.raises(SQLError):
                db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
