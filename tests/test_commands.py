# tests/test_commands.py
import pytest
from tinydb.cli.commands import CommandHandler
from tinydb.database import Database


class TestCommandHandler:
    def test_explain_select(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        ch = CommandHandler(db)
        output = ch.handle("explain", "SELECT * FROM users")
        assert output is not None
        assert "Scan" in output or "users" in output
        db.close()

    def test_explain_with_where(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount FLOAT)")
        ch = CommandHandler(db)
        output = ch.handle("explain", "SELECT * FROM orders WHERE amount > 100")
        assert output is not None
        assert "Filter" in output
        db.close()

    def test_timing_on(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        ch = CommandHandler(db)
        output = ch.handle("timing", "on")
        assert "on" in output.lower() or "enabled" in output.lower()
        assert ch._timing_enabled is True
        db.close()

    def test_timing_off(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        ch = CommandHandler(db)
        ch._timing_enabled = True
        output = ch.handle("timing", "off")
        assert "off" in output.lower() or "disabled" in output.lower()
        assert ch._timing_enabled is False
        db.close()

    def test_timing_toggle(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        ch = CommandHandler(db)
        assert ch._timing_enabled is False
        ch.handle("timing", "on")
        assert ch._timing_enabled is True
        ch.handle("timing", "off")
        assert ch._timing_enabled is False
        db.close()

    def test_unknown_command_returns_none(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        ch = CommandHandler(db)
        result = ch.handle("foobar", "")
        assert result is None
        db.close()
