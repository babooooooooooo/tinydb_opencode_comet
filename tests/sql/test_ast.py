"""Tests for AST node definitions."""
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
    ColumnDefAST,
)


class TestASTNodes:
    def test_select_statement(self):
        stmt = SelectStatement(columns=["id", "name"], table="users")
        assert stmt.table == "users"
        assert stmt.columns == ["id", "name"]
        assert stmt.where is None
        assert stmt.order_by is None
        assert stmt.limit is None
        assert stmt.offset is None
        assert stmt.group_by is None

    def test_insert_statement(self):
        stmt = InsertStatement(table="users", columns=["id", "name"], values=[[1, "Alice"]])
        assert stmt.table == "users"
        assert stmt.columns == ["id", "name"]
        assert stmt.values == [[1, "Alice"]]

    def test_insert_without_columns(self):
        stmt = InsertStatement(table="users", columns=None, values=[[1, "Alice"]])
        assert stmt.columns is None

    def test_update_statement(self):
        stmt = UpdateStatement(table="users", assignments=[("name", "Bob")])
        assert stmt.table == "users"
        assert stmt.assignments == [("name", "Bob")]
        assert stmt.where is None

    def test_delete_statement(self):
        stmt = DeleteStatement(table="users")
        assert stmt.table == "users"
        assert stmt.where is None

    def test_create_table_statement(self):
        cols = [ColumnDefAST("id", "INTEGER", primary_key=True)]
        stmt = CreateTableStatement(table="users", columns=cols)
        assert stmt.table == "users"
        assert len(stmt.columns) == 1
        assert stmt.columns[0].name == "id"

    def test_drop_table_statement(self):
        stmt = DropTableStatement(table="users")
        assert stmt.table == "users"
