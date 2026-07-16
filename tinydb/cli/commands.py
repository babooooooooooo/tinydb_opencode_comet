# tinydb/cli/commands.py
"""Dot-command handler for tinydb CLI."""


class CommandHandler:
    """Handles dot-commands (.explain, .import, .dump, .timing)."""

    def __init__(self, db):
        self._db = db
        self._timing_enabled = False

    def handle(self, cmd: str, arg: str) -> str | None:
        """Dispatch a dot-command. Returns output string or None if unknown."""
        match cmd:
            case "explain":
                return self._explain(arg)
            case "timing":
                return self._timing(arg)
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

    def _import(self, arg: str) -> str:
        """Import data from CSV/JSON — placeholder for Task 4."""
        return "Not yet implemented (see Task 4)"

    def _dump(self, arg: str) -> str:
        """Dump table data — placeholder for Task 5."""
        return "Not yet implemented (see Task 5)"
