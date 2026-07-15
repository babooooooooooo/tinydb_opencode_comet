"""Database entry point: assembles all SQL engine modules."""
from tinydb.sql.lexer import Lexer
from tinydb.sql.parser import Parser
from tinydb.sql.planner import Planner
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
)
from tinydb.sql.expressions import StarExpr, AggregateExpr, ColumnRef
from tinydb.sql.result import QueryResult
from tinydb.sql.errors import PlanningError, ExecutionError
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.exceptions import StorageError


class Database:
    """Main entry point for SQL execution."""

    def __init__(self, path: str):
        self.file_manager = FileManager(path)
        self.file_manager.open()
        self.buffer_pool = BufferPool(self.file_manager, capacity=100)
        self.catalog = Catalog(self.file_manager, self.buffer_pool)
        self.catalog.load()
        self._planner = Planner(self.catalog, self.buffer_pool)

    def execute(self, sql: str) -> QueryResult:
        tokens = Lexer().tokenize(sql)
        stmt = Parser().parse(tokens)

        try:
            if isinstance(stmt, SelectStatement):
                return self._execute_select(stmt)
            elif isinstance(stmt, InsertStatement):
                return self._execute_dml(stmt)
            elif isinstance(stmt, UpdateStatement):
                return self._execute_dml(stmt)
            elif isinstance(stmt, DeleteStatement):
                return self._execute_dml(stmt)
            elif isinstance(stmt, CreateTableStatement):
                return self._execute_ddl(stmt)
            elif isinstance(stmt, DropTableStatement):
                return self._execute_ddl(stmt)
            else:
                raise PlanningError(f"Unknown statement type: {type(stmt)}")
        except StorageError as e:
            raise ExecutionError(str(e))

    def _execute_select(self, stmt: SelectStatement) -> QueryResult:
        operator = self._planner.plan(stmt)
        rows = list(operator)

        columns = []
        for col in stmt.columns:
            if isinstance(col, StarExpr):
                table = self.catalog.get_table(stmt.table)
                columns.extend(c.name for c in table.columns)
            elif isinstance(col, ColumnRef):
                columns.append(col.name)
            elif isinstance(col, AggregateExpr):
                if isinstance(col.arg, StarExpr):
                    columns.append(col.func.lower() + "_*")
                else:
                    columns.append(col.func.lower())
            else:
                columns.append(str(col))

        return QueryResult(rows, columns, len(rows))

    def _execute_dml(self, stmt) -> QueryResult:
        operator = self._planner.plan(stmt)
        for row in operator:
            return row["_result"]
        return QueryResult([], [], 0)

    def _execute_ddl(self, stmt) -> QueryResult:
        operator = self._planner.plan(stmt)
        for row in operator:
            return row["_result"]
        return QueryResult([], [], 0)

    def close(self):
        self.catalog.save()
        self.file_manager.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
