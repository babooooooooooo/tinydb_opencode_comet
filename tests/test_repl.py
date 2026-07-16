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
            repl._handle_command(".exit")
        db.close()

    def test_meta_tables(self, tmp_path, capsys):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        repl = REPL(db)
        repl._handle_command(".tables")
        captured = capsys.readouterr()
        assert "t1" in captured.out
        db.close()

    def test_multiline_buffer(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        assert not repl._is_complete("SELECT *")
        assert repl._is_complete("SELECT * FROM t;")
        db.close()

    def test_is_complete_with_brackets(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        # Balanced brackets + semicolon = complete
        assert repl._is_complete("SELECT * FROM t WHERE id IN (1, 2, 3);")
        # Unbalanced brackets = not complete
        assert not repl._is_complete("SELECT * FROM t WHERE id IN (1, 2, 3")
        # No semicolon = not complete
        assert not repl._is_complete("SELECT * FROM t")
        db.close()

    def test_is_complete_nested_brackets(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        assert repl._is_complete("SELECT * FROM t WHERE (a = 1 AND (b = 2 OR c = 3));")
        assert not repl._is_complete("SELECT * FROM t WHERE (a = 1 AND (b = 2 OR c = 3)")
        db.close()

    def test_repl_has_highlighter(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        assert hasattr(repl, '_highlighter')
        db.close()

    def test_repl_has_completer(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        assert hasattr(repl, '_completer')
        db.close()

    def test_repl_has_commands(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        assert hasattr(repl, '_commands')
        db.close()

    def test_multiline_bracket_matching(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        repl = REPL(db)
        # Simulate multi-line input with brackets
        repl._buffer.append("SELECT * FROM t")
        repl._buffer.append("  WHERE id IN (1, 2")
        repl._buffer.append("  , 3)")
        sql = " ".join(repl._buffer)
        assert repl._is_complete(sql + ";")
        assert not repl._is_complete(sql)
        db.close()
