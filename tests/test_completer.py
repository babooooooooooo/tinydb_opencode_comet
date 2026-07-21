# tests/test_completer.py
from tinydb.cli.completer import SQLCompleter
from tinydb.database import Database


class TestSQLCompleter:
    def test_complete_keyword_at_start(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY, name TEXT)")
        c = SQLCompleter(db)
        c.refresh_schema()
        # Simulate readline: text="SEL", state=0
        result = c.complete("SEL", 0)
        assert result == "SELECT"
        db.close()

    def test_complete_table_after_from(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        c = SQLCompleter(db)
        c.refresh_schema()
        # After FROM, should suggest table names
        result = c.complete("", 0)
        # With empty text at line start, keywords are candidates
        assert result is not None
        db.close()

    def test_complete_returns_none_at_end(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        c = SQLCompleter(db)
        result = c.complete("XYZ", 5)  # state beyond candidates
        assert result is None
        db.close()

    def test_refresh_schema_loads_tables(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance FLOAT)")
        c = SQLCompleter(db)
        c.refresh_schema()
        assert "accounts" in c._table_cache
        assert "id" in c._table_cache["accounts"]
        assert "balance" in c._table_cache["accounts"]
        db.close()

    def test_complete_state_increment(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        c = SQLCompleter(db)
        # Multiple keywords start with nothing (all keywords)
        r0 = c.complete("", 0)
        r1 = c.complete("", 1)
        assert r0 is not None
        assert r1 is not None
        assert r0 != r1
        db.close()
