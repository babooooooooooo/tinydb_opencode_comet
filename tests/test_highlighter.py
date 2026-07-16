# tests/test_highlighter.py
import pytest
from tinydb.cli.highlighter import SQLHighlighter


class TestSQLHighlighter:
    def test_highlight_contains_ansi_codes(self):
        h = SQLHighlighter()
        result = h.highlight("SELECT * FROM users")
        assert "\x1b[" in result  # ANSI escape codes present
        assert "SELECT" in result

    def test_highlight_preserves_content(self):
        h = SQLHighlighter()
        sql = "SELECT name, age FROM users WHERE id = 1"
        result = h.highlight(sql)
        # Strip ANSI codes, original tokens remain
        import re
        stripped = re.sub(r"\x1b\[[0-9;]*m", "", result)
        assert "SELECT" in stripped
        assert "users" in stripped

    def test_highlight_empty_string(self):
        h = SQLHighlighter()
        assert h.highlight("") == ""

    def test_highlight_multiline(self):
        h = SQLHighlighter()
        sql = "SELECT *\nFROM users\nWHERE id > 10;"
        result = h.highlight(sql)
        assert "\x1b[" in result
