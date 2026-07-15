# tests/test_repl.py
import pytest
from unittest.mock import patch
from tinydb.cli.repl import REPL
from tinydb.database import Database, QueryResult


class TestREPL:
    def test_format_output(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        result = QueryResult(
            columns=["id", "name"],
            rows=[[1, "Alice"], [2, "Bob"]],
            row_count=2
        )
        output = repl._format_output(result)
        assert "id" in output
        assert "Alice" in output
        assert "2 rows" in output
        db.close()

    def test_meta_exit(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        with pytest.raises(SystemExit):
            repl._handle_meta(".exit")
        db.close()

    def test_meta_tables(self, tmp_path, capsys):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        repl = REPL(db)
        repl._handle_meta(".tables")
        captured = capsys.readouterr()
        assert "t1" in captured.out
        db.close()

    def test_multiline_buffer(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        assert not repl._is_complete("SELECT *")
        assert repl._is_complete("SELECT * FROM t;")
        db.close()
