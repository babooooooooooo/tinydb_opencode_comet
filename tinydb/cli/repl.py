# tinydb/cli/repl.py
"""Interactive REPL for tinydb with syntax highlighting, completion, and dot-commands."""
import readline
import time
from tinydb.cli.highlighter import SQLHighlighter
from tinydb.cli.completer import SQLCompleter
from tinydb.cli.commands import CommandHandler


class REPL:
    """Read-Eval-Print Loop for tinydb SQL with modern CLI features."""

    def __init__(self, db):
        self._db = db
        self._buffer = []
        self._highlighter = SQLHighlighter()
        self._completer = SQLCompleter(db)
        self._commands = CommandHandler(db)

    def run(self):
        self._setup_readline()
        while True:
            try:
                prompt = self._get_prompt()
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break

            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("."):
                self._handle_command(stripped)
                continue

            self._buffer.append(line)
            if self._is_complete():
                self._execute_buffer()

    def _setup_readline(self):
        """Configure readline with completion and history."""
        readline.set_history_length(1000)
        readline.set_completer(self._readline_complete)
        readline.parse_and_bind("tab: complete")
        # Enable emacs keybindings (default on most systems)
        readline.parse_and_bind("set editing-mode emacs")

    def _readline_complete(self, text: str, state: int) -> str | None:
        """Bridge readline completion to SQLCompleter."""
        line = readline.get_line_buffer()
        self._completer.set_line_buffer(line)
        return self._completer.complete(text, state)

    def _get_prompt(self) -> str:
        """Return the appropriate prompt based on buffer state."""
        if self._buffer:
            return ".. "
        return "tinydb> "

    def _handle_command(self, cmd: str):
        """Dispatch a dot-command."""
        parts = cmd.split(None, 1)
        command = parts[0]
        arg = parts[1] if len(parts) > 1 else ""

        # Built-in commands handled directly
        match command:
            case ".exit" | ".quit":
                raise SystemExit
            case ".tables":
                result = self._db.execute("SHOW TABLES")
                for row in result.rows:
                    print(row[0])
                return
            case ".schema":
                if not arg:
                    print("Usage: .schema <table>")
                else:
                    result = self._db.execute(f"SELECT * FROM {arg} LIMIT 0")
                    print(" | ".join(result.columns))
                return
            case ".help":
                self._print_help()
                return

        # Delegate to CommandHandler for .explain, .import, .dump, .timing
        output = self._commands.handle(command.lstrip("."), arg)
        if output is not None:
            print(output)
        else:
            print(f"Unknown command: {command}")

    def _print_help(self):
        """Print help text for all available commands."""
        print("Meta-commands:")
        print("  .exit              Exit the REPL")
        print("  .quit              Exit the REPL")
        print("  .tables            List all tables")
        print("  .schema <table>    Show table columns")
        print("  .explain <sql>     Show query execution plan")
        print("  .import <table> <file>  Import data from CSV/JSON")
        print("  .dump <table> [file]   Export table data to CSV/JSON")
        print("  .timing on|off     Toggle query timing display")
        print("  .help              Show this help message")

    def _is_complete(self, sql: str = None) -> bool:
        """Check if the buffered SQL is complete (balanced brackets + semicolon)."""
        if sql is None:
            sql = " ".join(self._buffer)
        if not sql.rstrip().endswith(";"):
            return False
        return self._brackets_balanced(sql)

    def _brackets_balanced(self, sql: str) -> bool:
        """Check if all bracket types are balanced in the SQL."""
        stack = []
        pairs = {"(": ")", "[": "]", "{": "}"}
        closing = set(pairs.values())
        in_string = False
        string_char = None

        for ch in sql:
            if in_string:
                if ch == string_char:
                    in_string = False
                continue
            if ch in ("'", '"'):
                in_string = True
                string_char = ch
                continue
            if ch in pairs:
                stack.append(ch)
            elif ch in closing:
                if not stack:
                    return False
                if pairs[stack[-1]] != ch:
                    return False
                stack.pop()

        return len(stack) == 0

    def _execute_buffer(self):
        """Execute the SQL accumulated in the buffer."""
        sql = " ".join(self._buffer)
        self._buffer.clear()

        # Refresh schema cache after DDL
        upper = sql.strip().upper()
        needs_refresh = any(
            upper.startswith(kw)
            for kw in ("CREATE TABLE", "DROP TABLE", "INSERT INTO", "UPDATE", "DELETE FROM")
        )

        start = time.perf_counter_ns()
        try:
            result = self._db.execute(sql)
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

            print(self._format_output(result))

            if self._commands._timing_enabled:
                print(f"Time: {elapsed_ms:.2f} ms")

        except Exception as e:
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            print(f"Error: {e}")
            if self._commands._timing_enabled:
                print(f"Time: {elapsed_ms:.2f} ms")

        if needs_refresh:
            self._completer.refresh_schema()

    def _format_output(self, result) -> str:
        """Format query result as an ASCII table."""
        if not result.rows:
            return f"{result.row_count} rows in set"

        col_widths = [len(c) for c in result.columns]
        for row in result.rows:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))

        lines = []
        sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        lines.append(sep)

        header = "|" + "|".join(
            f" {c.ljust(w)} " for c, w in zip(result.columns, col_widths)
        ) + "|"
        lines.append(header)
        lines.append(sep)

        for row in result.rows:
            row_str = "|" + "|".join(
                f" {str(v).ljust(w)} " for v, w in zip(row, col_widths)
            ) + "|"
            lines.append(row_str)

        lines.append(sep)
        lines.append(f"{result.row_count} rows in set")
        return "\n".join(lines)
