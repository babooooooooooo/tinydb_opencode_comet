# tinydb/cli/repl.py
"""Interactive REPL for tinydb."""
import readline


class REPL:
    """Read-Eval-Print Loop for tinydb SQL."""

    def __init__(self, db):
        self._db = db
        self._buffer = []

    def run(self):
        readline.set_history_length(1000)
        while True:
            try:
                prompt = "tinydb> " if not self._buffer else "   ...> "
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break

            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("."):
                self._handle_meta(stripped)
                continue

            self._buffer.append(line)
            sql = " ".join(self._buffer)

            if sql.rstrip().endswith(";"):
                self._buffer.clear()
                try:
                    result = self._db.execute(sql)
                    print(self._format_output(result))
                except Exception as e:
                    print(f"Error: {e}")

    def _handle_meta(self, cmd: str):
        parts = cmd.split()
        if not parts:
            return
        match parts[0]:
            case ".exit" | ".quit":
                raise SystemExit
            case ".tables":
                result = self._db.execute("SHOW TABLES")
                for row in result.rows:
                    print(row[0])
            case ".schema":
                if len(parts) < 2:
                    print("Usage: .schema <table>")
                else:
                    result = self._db.execute(f"SELECT * FROM {parts[1]} LIMIT 0")
                    print(" | ".join(result.columns))
            case ".help":
                print("Meta-commands: .exit .tables .schema .help")
            case _:
                print(f"Unknown command: {parts[0]}")

    def _format_output(self, result) -> str:
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

    def _is_complete(self, sql: str) -> bool:
        return sql.rstrip().endswith(";")
