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
from tinydb.types import ColumnDef, DataType


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

        try:
            if upper.startswith("CREATE TABLE"):
                return self._exec_create_table(sql)
            elif upper.startswith("DROP TABLE"):
                return self._exec_drop_table(sql)
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
            elif upper.startswith("SELECT"):
                return self._exec_sql_select(sql)
            else:
                return self._exec_sql_dml(sql)
        except Exception as e:
            if self._txn_mgr.has_active_txn():
                self._txn_mgr.rollback()
            raise DatabaseError(str(e))

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
        elif stmt.from_table is not None:
            tbl = self._catalog.get_table(stmt.from_table.name)
            col_names = [c.name for c in tbl.columns]
            data_rows = []
        else:
            col_names = []
            data_rows = rows

        return QueryResult(
            columns=col_names,
            rows=data_rows,
            row_count=len(data_rows),
        )

    def _exec_sql_dml(self, sql: str) -> QueryResult:
        """Execute INSERT/UPDATE/DELETE via the SQL engine."""
        from tinydb.sql.lexer import Lexer
        from tinydb.sql.parser import Parser
        tokens = Lexer().tokenize(sql)
        stmt = Parser().parse(tokens)
        if stmt is None:
            raise DatabaseError("Failed to parse SQL")
        pool = self._get_pool()
        operator = self._planner.plan(stmt, pool=pool, index_manager=self._index_mgr)
        result = next(iter(operator))
        return result["_result"]

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
        return self._exec_sql_dml(sql)

    def _exec_create_index(self, sql: str) -> QueryResult:
        m = re.match(r"CREATE INDEX (\w+)\s+ON\s+(\w+)\s*\((\w+)\)", sql, re.IGNORECASE)
        if not m:
            raise DatabaseError(f"Invalid CREATE INDEX: {sql}")
        idx_name = m.group(1)
        table_name = m.group(2)
        col_name = m.group(3)

        self._index_mgr.create_index(table_name, col_name, idx_name)
        return QueryResult(columns=[], rows=[], row_count=0)


