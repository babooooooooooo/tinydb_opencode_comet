"""QueryResult return object."""
from dataclasses import dataclass


@dataclass
class QueryResult:
    """Result of a SQL query execution."""
    rows: list
    columns: list
    row_count: int

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return self.row_count

    def __repr__(self):
        if not self.rows:
            return f"QueryResult(row_count={self.row_count})"
        return f"QueryResult(columns={self.columns}, rows={len(self.rows)})"
