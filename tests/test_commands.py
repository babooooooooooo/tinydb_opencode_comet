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

    def test_import_csv(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        # Create a CSV file
        csv_path = tmp_path / "users.csv"
        csv_path.write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\n")
        ch = CommandHandler(db)
        output = ch.handle("import", f"users {csv_path}")
        assert "3" in output  # 3 rows imported
        # Verify data
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 3
        db.close()

    def test_import_json(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price FLOAT)")
        json_path = tmp_path / "products.json"
        json_path.write_text('[{"id": 1, "name": "Widget", "price": 9.99}, {"id": 2, "name": "Gadget", "price": 19.99}]')
        ch = CommandHandler(db)
        output = ch.handle("import", f"products {json_path}")
        assert "2" in output
        result = db.execute("SELECT * FROM products")
        assert result.row_count == 2
        db.close()

    def test_import_file_not_found(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        ch = CommandHandler(db)
        output = ch.handle("import", "t1 /nonexistent/file.csv")
        assert "Error" in output or "not found" in output.lower()
        db.close()

    def test_dump_csv_to_stdout(self, tmp_path, capsys):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, 'Bob')")
        ch = CommandHandler(db)
        output = ch.handle("dump", "users")
        assert "Alice" in output
        assert "Bob" in output
        assert "id" in output
        db.close()

    def test_dump_json_to_stdout(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO items VALUES (1, 'Widget')")
        ch = CommandHandler(db)
        output = ch.handle("dump", "items")
        # JSON output should contain the data
        assert "Widget" in output
        assert '"id"' in output or "id" in output
        db.close()

    def test_dump_to_file(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        db.execute("CREATE TABLE data (id INTEGER PRIMARY KEY, val TEXT)")
        db.execute("INSERT INTO data VALUES (1, 'test')")
        ch = CommandHandler(db)
        out_path = tmp_path / "output.csv"
        output = ch.handle("dump", f"data {out_path}")
        assert "1 rows" in output or "1 row" in output
        assert out_path.exists()
        content = out_path.read_text()
        assert "test" in content
        db.close()

    def test_dump_nonexistent_table(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        ch = CommandHandler(db)
        output = ch.handle("dump", "nonexistent")
        assert "Error" in output or "not found" in output.lower() or "no such" in output.lower()
        db.close()
