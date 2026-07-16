# tinydb/cli/commands.py
"""Dot-command handler for tinydb CLI."""


class CommandHandler:
    """Handles dot-commands (.explain, .import, .dump, .timing)."""

    def __init__(self, db):
        self._db = db
        self._timing_enabled = False
        self._highlight_enabled = True

    def handle(self, cmd: str, arg: str) -> str | None:
        """Dispatch a dot-command. Returns output string or None if unknown."""
        match cmd:
            case "explain":
                return self._explain(arg)
            case "timing":
                return self._timing(arg)
            case "highlight":
                return self._highlight(arg)
            case "import":
                return self._import(arg)
            case "dump":
                return self._dump(arg)
            case _:
                return None

    def _explain(self, sql: str) -> str:
        """Format the query execution plan as a tree string."""
        try:
            from tinydb.sql.lexer import Lexer
            from tinydb.sql.parser import Parser
            tokens = Lexer().tokenize(sql)
            stmt = Parser().parse(tokens)
            if stmt is None:
                return "Error: could not parse SQL"
            plan = self._db._planner.plan(stmt)
            return self._format_plan(plan)
        except Exception as e:
            return f"Error: {e}"

    def _format_plan(self, op, indent: int = 0) -> str:
        """Recursively format an operator tree."""
        prefix = "  " * indent
        lines = []

        op_name = type(op).__name__.replace("Operator", "")

        # Describe the operator
        detail = self._describe_op(op)
        if detail:
            lines.append(f"{prefix}{op_name} [{detail}]")
        else:
            lines.append(f"{prefix}{op_name}")

        # Recurse into child operators
        child = self._get_child(op)
        if child is not None:
            lines.append(self._format_plan(child, indent + 1))

        return "\n".join(lines)

    def _describe_op(self, op) -> str:
        """Return a short description of an operator."""
        name = type(op).__name__
        if name == "ScanOperator":
            return f"table={op.table.table_name}"
        elif name == "FilterOperator":
            return f"condition={op.condition}"
        elif name == "ProjectOperator":
            cols = [str(c[0]) for c in op.columns]
            return f"columns=[{', '.join(cols)}]"
        elif name == "AggregateOperator":
            return f"groups={op.group_keys}"
        elif name == "SortOperator":
            return f"keys={op.order_keys}"
        elif name == "LimitOperator":
            return f"limit={op.limit}, offset={op.offset}"
        elif name == "DmlOperator":
            return f"{type(op.stmt).__name__}"
        elif name == "CreateTableOperator":
            return f"table={op.stmt.table}"
        elif name == "DropTableOperator":
            return f"table={op.stmt.table}"
        return ""

    def _get_child(self, op):
        """Get the child operator for tree traversal."""
        if hasattr(op, "source"):
            return op.source
        if hasattr(op, "table") and type(op).__name__ == "ScanOperator":
            return None  # leaf node
        return None

    def _timing(self, arg: str) -> str:
        """Toggle query timing display."""
        arg = arg.strip().lower()
        if arg == "on":
            self._timing_enabled = True
            return "Timing enabled."
        elif arg == "off":
            self._timing_enabled = False
            return "Timing disabled."
        else:
            state = "on" if self._timing_enabled else "off"
            return f"Timing is {state}. Usage: .timing on|off"

    def _highlight(self, arg: str) -> str:
        """Toggle SQL syntax highlighting."""
        arg = arg.strip().lower()
        if arg == "on":
            self._highlight_enabled = True
            return "Highlighting enabled."
        elif arg == "off":
            self._highlight_enabled = False
            return "Highlighting disabled."
        else:
            state = "on" if self._highlight_enabled else "off"
            return f"Highlighting is {state}. Usage: .highlight on|off"

    def _import(self, arg: str) -> str:
        """Import data from a CSV or JSON file into a table."""
        import csv
        import json
        import os

        parts = arg.strip().split()
        if len(parts) < 2:
            return "Usage: .import <table> <filepath>"

        table_name = parts[0]
        filepath = parts[1]

        if not os.path.isfile(filepath):
            return f"Error: file not found: {filepath}"

        ext = os.path.splitext(filepath)[1].lower()

        try:
            if ext == ".csv":
                rows = self._read_csv(filepath)
            elif ext == ".json":
                rows = self._read_json(filepath)
            else:
                # Try CSV first, then JSON
                try:
                    rows = self._read_csv(filepath)
                except Exception:
                    rows = self._read_json(filepath)

            if not rows:
                return "Error: no data found in file"

            # Get column names from first row
            col_names = list(rows[0].keys())

            # Build and execute INSERT statements
            # The parser expects: INSERT INTO table VALUES (...)
            count = 0
            for row in rows:
                values = []
                for col in col_names:
                    val = row.get(col, None)
                    if val is None:
                        values.append("NULL")
                    elif isinstance(val, str):
                        values.append(f"'{val}'")
                    else:
                        values.append(str(val))
                sql = f"INSERT INTO {table_name} VALUES ({', '.join(values)})"
                self._db.execute(sql)
                count += 1

            return f"{count} rows imported into {table_name}"

        except Exception as e:
            return f"Error: {e}"

    def _read_csv(self, filepath: str) -> list[dict]:
        """Read CSV file, return list of dicts."""
        import csv
        rows = []
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                parsed = {}
                for key, val in row.items():
                    parsed[key.strip()] = self._parse_value(val.strip())
                rows.append(parsed)
        return rows

    def _read_json(self, filepath: str) -> list[dict]:
        """Read JSON file, return list of dicts."""
        import json
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            raise ValueError("JSON must be an array of objects or a single object")

    def _parse_value(self, val: str):
        """Parse a string value into the appropriate Python type."""
        if val.upper() == "NULL" or val == "":
            return None
        try:
            return int(val)
        except ValueError:
            pass
        try:
            return float(val)
        except ValueError:
            pass
        return val

    def _dump(self, arg: str) -> str:
        """Export table data to CSV (stdout) or a file."""
        import csv
        import json
        import os

        parts = arg.strip().split()
        if not parts:
            return "Usage: .dump <table> [filepath]"

        table_name = parts[0]
        filepath = parts[1] if len(parts) > 1 else None

        try:
            result = self._db.execute(f"SELECT * FROM {table_name}")
        except Exception as e:
            return f"Error: {e}"

        if not result.rows:
            return f"0 rows (table {table_name} is empty)"

        columns = result.columns
        rows = result.rows

        # Determine format from filepath extension
        fmt = "csv"
        if filepath:
            ext = os.path.splitext(filepath)[1].lower()
            if ext == ".json":
                fmt = "json"

        if fmt == "csv":
            output = self._format_csv(columns, rows)
        else:
            output = self._format_json(columns, rows)

        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(output)
            return f"{len(rows)} rows dumped to {filepath}"
        else:
            return output

    def _format_csv(self, columns: list[str], rows: list[list]) -> str:
        """Format rows as CSV string."""
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)
        return buf.getvalue().rstrip("\r\n")

    def _format_json(self, columns: list[str], rows: list[list]) -> str:
        """Format rows as JSON string."""
        import json
        result = []
        for row in rows:
            result.append(dict(zip(columns, row)))
        return json.dumps(result, indent=2, ensure_ascii=False)
