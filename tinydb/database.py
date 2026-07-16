# tinydb/database.py
"""Database: unified entry point integrating storage, SQL, index, and transaction."""
import re
from dataclasses import dataclass
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.index.index_manager import IndexManager
from tinydb.transaction.txn_manager import TransactionManager, TransactionError
from tinydb.concurrency.isolation import IsolationLevel
from tinydb.sql.planner import Planner
from tinydb.types import ColumnDef, DataType, convert_value
from tinydb.page import RowId


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    row_count: int


class DatabaseError(Exception):
    pass


class Database:
    """Unified database interface."""

    def __init__(self, path: str):
        self._fm = FileManager(path)
        self._fm.open()
        self._pool = BufferPool(self._fm)
        self._catalog = Catalog(self._fm, self._pool)
        self._catalog.load()
        self._index_mgr = IndexManager(self._catalog, self._fm, self._pool)
        self._txn_mgr = TransactionManager(self._fm, self._pool, self._index_mgr)
        self._planner = Planner(self._catalog, self._pool)

    def get_table_info(self, table_name: str) -> list[dict]:
        """Return column info for a table: [{name, type, nullable, primary_key}]."""
        try:
            tbl = self._catalog.get_table(table_name)
        except Exception:
            return []
        return [
            {
                "name": c.name,
                "type": c.data_type.value,
                "nullable": c.nullable,
                "primary_key": c.primary_key,
            }
            for c in tbl.columns
        ]

    def execute(self, sql: str) -> QueryResult:
        """Execute SQL and return result."""
        sql = sql.strip().rstrip(";").strip()
        upper = sql.upper()

        ctx = self._txn_mgr.get_active_context()

        try:
            if upper.startswith("CREATE TABLE"):
                return self._exec_create_table(sql)
            elif upper.startswith("DROP TABLE"):
                return self._exec_drop_table(sql)
            elif upper.startswith("INSERT INTO"):
                return self._exec_insert(sql, ctx)
            elif upper.startswith("SELECT"):
                if self._is_complex_select(upper):
                    return self._exec_sql_select(sql)
                return self._exec_select(sql, ctx)
            elif upper.startswith("UPDATE"):
                return self._exec_update(sql, ctx)
            elif upper.startswith("DELETE FROM"):
                return self._exec_delete(sql, ctx)
            elif upper.startswith("CREATE INDEX"):
                return self._exec_create_index(sql)
            elif upper.startswith("BEGIN"):
                self._txn_mgr.begin()
                return QueryResult(columns=[], rows=[], row_count=0)
            elif upper.startswith("COMMIT"):
                self._txn_mgr.commit()
                return QueryResult(columns=[], rows=[], row_count=0)
            elif upper.startswith("ROLLBACK"):
                self._txn_mgr.rollback()
                return QueryResult(columns=[], rows=[], row_count=0)
            elif upper.startswith("SHOW TABLES"):
                tables = self._catalog.list_tables()
                return QueryResult(columns=["table_name"], rows=[[t] for t in tables], row_count=len(tables))
            else:
                raise DatabaseError(f"Unsupported SQL: {sql}")
        except Exception as e:
            if self._txn_mgr.has_active_txn():
                self._txn_mgr.rollback()
            raise DatabaseError(str(e))

    def _is_complex_select(self, upper: str) -> bool:
        """Check if a SELECT statement needs the full SQL engine (JOINs, GROUP BY, aggregates)."""
        return (
            " JOIN " in upper
            or " GROUP BY " in upper
            or " COUNT(" in upper
            or " SUM(" in upper
            or " AVG(" in upper
            or " MIN(" in upper
            or " MAX(" in upper
        )

    def _exec_sql_select(self, sql: str) -> QueryResult:
        """Execute SELECT via the full SQL engine (supports JOINs, GROUP BY, aggregates)."""
        from tinydb.sql.lexer import Lexer
        from tinydb.sql.parser import Parser
        tokens = Lexer().tokenize(sql)
        stmt = Parser().parse(tokens)
        if stmt is None:
            raise DatabaseError("Failed to parse SQL")
        plan = self._planner.plan(stmt)
        pool = self._get_pool()
        operator = plan
        rows = list(operator)

        if rows and isinstance(rows[0], dict):
            col_names = [k for k in rows[0].keys() if k != "_rowid"]
            data_rows = [[r.get(c) for c in col_names] for r in rows]
        else:
            col_names = []
            data_rows = rows

        return QueryResult(
            columns=col_names,
            rows=data_rows,
            row_count=len(data_rows),
        )

    def _get_pool(self):
        """Return active pool: shadow pool if in transaction, else main pool."""
        if self._txn_mgr.has_active_txn():
            from tinydb.transaction.shadow_paging import ShadowBufferPool
            entry = next(iter(self._txn_mgr.get_active_txns().values()))
            return ShadowBufferPool(self._pool, entry.txn, self._fm, mvcc_manager=self._txn_mgr._mvcc)
        return self._pool

    def commit(self):
        self._txn_mgr.commit()

    def rollback(self):
        self._txn_mgr.rollback()

    def close(self):
        self._pool.flush()
        self._catalog.save()
        self._fm.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _exec_create_table(self, sql: str) -> QueryResult:
        m = re.match(r"CREATE TABLE (\w+)\s*\((.+)\)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid CREATE TABLE: {sql}")
        table_name = m.group(1)
        cols_str = m.group(2)

        columns = []
        pk = ""
        for col_def in cols_str.split(","):
            parts = col_def.strip().split()
            col_name = parts[0]
            col_type = DataType(parts[1].upper())
            is_pk = "PRIMARY" in col_def.upper() and "KEY" in col_def.upper()
            nullable = "NOT NULL" not in col_def.upper() and not is_pk
            columns.append(ColumnDef(name=col_name, data_type=col_type,
                                     nullable=nullable, primary_key=is_pk))
            if is_pk:
                pk = col_name

        self._catalog.create_table(table_name, columns, pk)
        self._catalog.save()
        return QueryResult(columns=[], rows=[], row_count=0)

    def _exec_drop_table(self, sql: str) -> QueryResult:
        m = re.match(r"DROP TABLE (\w+)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid DROP TABLE: {sql}")
        self._catalog.drop_table(m.group(1))
        self._catalog.save()
        return QueryResult(columns=[], rows=[], row_count=0)

    def _exec_insert(self, sql: str, ctx=None) -> QueryResult:
        m = re.match(r"INSERT INTO (\w+)\s+VALUES\s*\((.+)\)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid INSERT: {sql}")
        table_name = m.group(1)
        values_str = m.group(2)

        tbl = self._catalog.get_table(table_name)
        values = self._parse_values(values_str, tbl.columns)
        converted = [convert_value(v, col) for v, col in zip(values, tbl.columns)]

        pool = self._get_pool()
        rid = tbl.insert(pool, converted, ctx=ctx)
        self._index_mgr.after_insert(table_name, rid, converted)
        return QueryResult(columns=[], rows=[], row_count=1)

    def _exec_select(self, sql: str, ctx=None) -> QueryResult:
        m = re.match(r"SELECT\s+(.+?)\s+FROM\s+(\w+)\s+WHERE\s+(.+)", sql, re.IGNORECASE)
        if m:
            cols_str = m.group(1).strip()
            table_name = m.group(2)
            where_str = m.group(3)
        else:
            m = re.match(r"SELECT\s+(.+?)\s+FROM\s+(\w+)", sql, re.IGNORECASE)
            if not m:
                raise DatabaseError(f"Invalid SELECT: {sql}")
            cols_str = m.group(1).strip()
            table_name = m.group(2)
            where_str = None

        tbl = self._catalog.get_table(table_name)
        columns = [c.name for c in tbl.columns]

        if cols_str == "*":
            selected_cols = columns
        else:
            selected_cols = [c.strip() for c in cols_str.split(",")]

        pool = self._get_pool()
        rows = []
        for row_ptr, row in tbl.scan(pool, ctx=ctx):
            if where_str and not self._eval_where(row, tbl.columns, where_str):
                continue
            selected = [row[columns.index(c)] for c in selected_cols]
            rows.append(selected)

        return QueryResult(columns=selected_cols, rows=rows, row_count=len(rows))

    def _exec_update(self, sql: str, ctx=None) -> QueryResult:
        m = re.match(r"UPDATE\s+(\w+)\s+SET\s+(.+?)\s+WHERE\s+(.+)", sql, re.IGNORECASE)
        if not m:
            m = re.match(r"UPDATE\s+(\w+)\s+SET\s+(.+)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid UPDATE: {sql}")
        table_name = m.group(1)
        set_str = m.group(2)
        where_str = m.group(3)

        tbl = self._catalog.get_table(table_name)
        set_clause = self._parse_set(set_str, tbl.columns)

        pool = self._get_pool()
        count = 0
        for row_ptr, row in tbl.scan(pool, ctx=ctx):
            if where_str and not self._eval_where(row, tbl.columns, where_str):
                continue
            new_row = list(row)
            for col_idx, val in set_clause.items():
                new_row[col_idx] = val
            tbl.update(pool, row_ptr, new_row, ctx=ctx)
            self._index_mgr.after_update(table_name, row_ptr, row, new_row)
            count += 1

        return QueryResult(columns=[], rows=[], row_count=count)

    def _exec_delete(self, sql: str, ctx=None) -> QueryResult:
        m = re.match(r"DELETE FROM\s+(\w+)\s+WHERE\s+(.+)", sql, re.IGNORECASE)
        if not m:
            m = re.match(r"DELETE FROM\s+(\w+)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid DELETE: {sql}")
        table_name = m.group(1)
        where_str = m.group(2)

        tbl = self._catalog.get_table(table_name)
        pool = self._get_pool()
        to_delete = []
        for row_ptr, row in tbl.scan(pool, ctx=ctx):
            if where_str and not self._eval_where(row, tbl.columns, where_str):
                continue
            to_delete.append((row_ptr, row))

        count = 0
        for row_ptr, row in to_delete:
            self._index_mgr.after_delete(table_name, row_ptr, row)
            tbl.delete(pool, row_ptr, ctx=ctx)
            count += 1

        return QueryResult(columns=[], rows=[], row_count=count)

    def _exec_create_index(self, sql: str) -> QueryResult:
        m = re.match(r"CREATE INDEX (\w+)\s+ON\s+(\w+)\s*\((\w+)\)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid CREATE INDEX: {sql}")
        idx_name = m.group(1)
        table_name = m.group(2)
        col_name = m.group(3)

        self._index_mgr.create_index(table_name, col_name, idx_name)
        return QueryResult(columns=[], rows=[], row_count=0)

    def _parse_values(self, values_str: str, columns: list[ColumnDef]) -> list:
        values = []
        for raw in re.split(r",\s*(?=(?:[^']*'[^']*')*[^']*$)", values_str):
            raw = raw.strip()
            if raw.startswith("'") and raw.endswith("'"):
                values.append(raw[1:-1])
            elif raw.upper() == "NULL":
                values.append(None)
            elif "." in raw:
                values.append(float(raw))
            else:
                values.append(int(raw))
        return values

    def _parse_set(self, set_str: str, columns: list[ColumnDef]) -> dict:
        result = {}
        for assignment in set_str.split(","):
            col_name, val_str = assignment.split("=", 1)
            col_name = col_name.strip()
            val_str = val_str.strip()
            col_idx = next((i for i, c in enumerate(columns) if c.name == col_name), -1)
            if col_idx < 0:
                raise DatabaseError(f"Unknown column: {col_name}")
            if val_str.startswith("'") and val_str.endswith("'"):
                result[col_idx] = val_str[1:-1]
            elif val_str.upper() == "NULL":
                result[col_idx] = None
            elif "." in val_str:
                result[col_idx] = float(val_str)
            else:
                result[col_idx] = int(val_str)
        return result

    def _eval_where(self, row: list, columns: list[ColumnDef], where_str: str) -> bool:
        m = re.match(r"(\w+)\s*(=|!=|<>|>=|<=|>|<)\s*(.+)", where_str.strip())
        if not m:
            return True
        col_name = m.group(1)
        op = m.group(2)
        val_str = m.group(3).strip()

        col_idx = next((i for i, c in enumerate(columns) if c.name == col_name), -1)
        if col_idx < 0:
            return True

        val = row[col_idx]
        if val_str.startswith("'") and val_str.endswith("'"):
            compare = val_str[1:-1]
        elif val_str.upper() == "NULL":
            compare = None
        elif "." in val_str:
            compare = float(val_str)
        else:
            compare = int(val_str)

        if op == "=":
            return val == compare
        elif op in ("!=", "<>"):
            return val != compare
        elif op == ">":
            return val is not None and val > compare
        elif op == ">=":
            return val is not None and val >= compare
        elif op == "<":
            return val is not None and val < compare
        elif op == "<=":
            return val is not None and val <= compare
        return True
