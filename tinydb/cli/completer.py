# tinydb/cli/completer.py
"""Context-aware SQL auto-completion for readline."""


class SQLCompleter:
    """Provides context-aware tab completion for SQL statements."""

    SQL_KEYWORDS = [
        "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE",
        "CREATE", "DROP", "TABLE", "INDEX", "JOIN", "ON", "AND",
        "OR", "NOT", "NULL", "ORDER", "GROUP", "BY", "LIMIT",
        "OFFSET", "AS", "INTO", "VALUES", "SET", "BEGIN", "COMMIT",
        "ROLLBACK", "SHOW", "TABLES", "EXPLAIN", "INNER", "LEFT",
        "RIGHT", "OUTER", "CROSS", "HAVING", "DISTINCT", "ALL",
        "UNION", "EXCEPT", "INTERSECT", "CASE", "WHEN", "THEN",
        "ELSE", "END", "BETWEEN", "LIKE", "IN", "IS", "EXISTS",
        "PRIMARY", "KEY", "UNIQUE", "DEFAULT", "AUTOINCREMENT",
        "INTEGER", "TEXT", "REAL", "BLOB", "NUMERIC", "REFERENCES",
        "CONSTRAINT", "FOREIGN", "CHECK", "CASCADE", "NO", "ACTION",
    ]

    def __init__(self, db):
        self._db = db
        self._table_cache: dict[str, list[str]] = {}
        self._line_buffer = ""

    def complete(self, text: str, state: int) -> str | None:
        """readline completion callback — returns the state-th candidate."""
        candidates = self._get_candidates(text, self._line_buffer)
        if state < len(candidates):
            return candidates[state]
        return None

    def set_line_buffer(self, line: str):
        """Update the current line context for completion."""
        self._line_buffer = line

    def _get_candidates(self, text: str, line: str) -> list[str]:
        """Generate completion candidates based on context."""
        # Determine context from the line so far
        upper_line = line.upper().strip()

        # After FROM/JOIN/INTO/UPDATE → suggest table names
        if self._after_keyword(upper_line, ("FROM", "JOIN", "INTO", "UPDATE")):
            return self._filter_matches(text, list(self._table_cache.keys()))

        # After SELECT or after a dot → suggest column names
        if self._after_keyword(upper_line, ("SELECT",)) or text == ".":
            return self._filter_matches(text, self._all_column_names())

        # Default: keywords + table names
        all_candidates = self.SQL_KEYWORDS + list(self._table_cache.keys())
        return self._filter_matches(text, all_candidates)

    def _after_keyword(self, upper_line: str, keywords: tuple[str, ...]) -> bool:
        """Check if the line ends with one of the given keywords."""
        for kw in keywords:
            if upper_line.endswith(kw) or upper_line.endswith(kw + " "):
                return True
        return False

    def _filter_matches(self, text: str, candidates: list[str]) -> list[str]:
        """Filter candidates that start with text (case-insensitive)."""
        if not text:
            return sorted(candidates)
        upper_text = text.upper()
        return sorted(c for c in candidates if c.upper().startswith(upper_text))

    def _all_column_names(self) -> list[str]:
        """Return all column names across all tables."""
        columns = []
        for cols in self._table_cache.values():
            columns.extend(cols)
        return list(set(columns))

    def refresh_schema(self):
        """Reload table and column names from the database catalog."""
        self._table_cache.clear()
        try:
            result = self._db.execute("SHOW TABLES")
            for row in result.rows:
                table_name = row[0]
                try:
                    schema_result = self._db.execute(f"SELECT * FROM {table_name} LIMIT 0")
                    self._table_cache[table_name] = list(schema_result.columns)
                except Exception:
                    self._table_cache[table_name] = []
        except Exception:
            pass
