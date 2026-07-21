"""Tests for SQL parser."""
import pytest
from tinydb.sql.parser import Parser
from tinydb.sql.lexer import Lexer
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
    ColumnDefAST,
)
from tinydb.sql.expressions import (
    ColumnRef, BinaryOp, StarExpr, AggregateExpr,
    IsNullExpr, UnaryOp,
)
from tinydb.sql.errors import ParserError


def parse(sql: str):
    return Parser().parse(Lexer().tokenize(sql))


class TestSelectParsing:
    def test_simple_select(self):
        stmt = parse("SELECT id, name FROM users")
        assert isinstance(stmt, SelectStatement)
        assert stmt.table == "users"
        assert len(stmt.columns) == 2
        assert isinstance(stmt.columns[0], ColumnRef)
        assert stmt.columns[0].name == "id"

    def test_select_star(self):
        stmt = parse("SELECT * FROM users")
        assert isinstance(stmt, SelectStatement)
        assert len(stmt.columns) == 1
        assert isinstance(stmt.columns[0], StarExpr)

    def test_select_where(self):
        stmt = parse("SELECT id FROM users WHERE id = 1")
        assert isinstance(stmt, SelectStatement)
        assert isinstance(stmt.where, BinaryOp)
        assert stmt.where.op == '='

    def test_select_order_by(self):
        stmt = parse("SELECT id FROM users ORDER BY id ASC")
        assert isinstance(stmt, SelectStatement)
        assert stmt.order_by is not None
        assert len(stmt.order_by) == 1
        assert stmt.order_by[0][1] == "ASC"

    def test_select_limit(self):
        stmt = parse("SELECT id FROM users LIMIT 10")
        assert isinstance(stmt, SelectStatement)
        assert stmt.limit == 10

    def test_select_offset(self):
        stmt = parse("SELECT id FROM users LIMIT 10 OFFSET 5")
        assert isinstance(stmt, SelectStatement)
        assert stmt.limit == 10
        assert stmt.offset == 5

    def test_select_group_by(self):
        stmt = parse("SELECT name FROM users GROUP BY name")
        assert isinstance(stmt, SelectStatement)
        assert stmt.group_by is not None
        assert len(stmt.group_by) == 1

    def test_select_all_clauses(self):
        stmt = parse(
            "SELECT id, name FROM users WHERE id > 1 ORDER BY name ASC LIMIT 10 OFFSET 5"
        )
        assert isinstance(stmt, SelectStatement)
        assert stmt.table == "users"
        assert len(stmt.columns) == 2
        assert stmt.where is not None
        assert stmt.order_by is not None
        assert stmt.limit == 10
        assert stmt.offset == 5


class TestInsertParsing:
    def test_insert_with_columns(self):
        stmt = parse("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        assert isinstance(stmt, InsertStatement)
        assert stmt.table == "users"
        assert stmt.columns == ["id", "name"]
        assert len(stmt.values) == 1

    def test_insert_without_columns(self):
        stmt = parse("INSERT INTO users VALUES (1, 'Alice')")
        assert isinstance(stmt, InsertStatement)
        assert stmt.columns is None

    def test_insert_multi_row(self):
        stmt = parse("INSERT INTO users VALUES (1, 'A'), (2, 'B'), (3, 'C')")
        assert isinstance(stmt, InsertStatement)
        assert len(stmt.values) == 3


class TestUpdateParsing:
    def test_update_set(self):
        stmt = parse("UPDATE users SET name = 'Bob' WHERE id = 1")
        assert isinstance(stmt, UpdateStatement)
        assert stmt.table == "users"
        assert len(stmt.assignments) == 1
        assert stmt.assignments[0][0] == "name"
        assert isinstance(stmt.where, BinaryOp)

    def test_update_multiple_sets(self):
        stmt = parse("UPDATE users SET name = 'Bob', age = 30 WHERE id = 1")
        assert isinstance(stmt, UpdateStatement)
        assert len(stmt.assignments) == 2


class TestDeleteParsing:
    def test_delete(self):
        stmt = parse("DELETE FROM users WHERE id = 1")
        assert isinstance(stmt, DeleteStatement)
        assert stmt.table == "users"
        assert isinstance(stmt.where, BinaryOp)

    def test_delete_no_where(self):
        stmt = parse("DELETE FROM users")
        assert isinstance(stmt, DeleteStatement)
        assert stmt.where is None


class TestCreateTableParsing:
    def test_create_table(self):
        stmt = parse("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        assert isinstance(stmt, CreateTableStatement)
        assert stmt.table == "users"
        assert len(stmt.columns) == 2
        assert isinstance(stmt.columns[0], ColumnDefAST)
        assert stmt.columns[0].name == "id"
        assert stmt.columns[0].data_type == "INTEGER"
        assert stmt.columns[0].primary_key is True

    def test_create_table_with_constraints(self):
        stmt = parse("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE)")
        assert isinstance(stmt, CreateTableStatement)
        assert stmt.columns[1].not_null is True
        assert stmt.columns[2].unique is True


class TestDropTableParsing:
    def test_drop_table(self):
        stmt = parse("DROP TABLE users")
        assert isinstance(stmt, DropTableStatement)
        assert stmt.table == "users"


class TestExpressionPrecedence:
    def test_and_or_precedence(self):
        stmt = parse("SELECT id FROM users WHERE a = 1 AND b = 2 OR c = 3")
        assert isinstance(stmt.where, BinaryOp)
        assert stmt.where.op == 'OR'

    def test_not_precedence(self):
        stmt = parse("SELECT id FROM users WHERE NOT a = 1")
        assert isinstance(stmt.where, UnaryOp)
        assert stmt.where.op == 'NOT'

    def test_arithmetic_precedence(self):
        stmt = parse("SELECT id FROM users WHERE a + b * c = 1")
        assert isinstance(stmt.where, BinaryOp)
        assert stmt.where.op == '='

    def test_parentheses_override(self):
        stmt = parse("SELECT id FROM users WHERE (a + b) * c = 1")
        assert isinstance(stmt.where, BinaryOp)
        assert stmt.where.op == '='


class TestIsNull:
    def test_is_null(self):
        stmt = parse("SELECT id FROM users WHERE name IS NULL")
        assert isinstance(stmt.where, IsNullExpr)
        assert stmt.where.negated is False

    def test_is_not_null(self):
        stmt = parse("SELECT id FROM users WHERE name IS NOT NULL")
        assert isinstance(stmt.where, IsNullExpr)
        assert stmt.where.negated is True


class TestAggregateFunctions:
    def test_count_star(self):
        stmt = parse("SELECT COUNT(*) FROM users")
        assert isinstance(stmt.columns[0], AggregateExpr)
        assert stmt.columns[0].func == 'COUNT'
        assert isinstance(stmt.columns[0].arg, StarExpr)

    def test_count_column(self):
        stmt = parse("SELECT COUNT(id) FROM users")
        assert isinstance(stmt.columns[0], AggregateExpr)
        assert stmt.columns[0].func == 'COUNT'

    def test_sum(self):
        stmt = parse("SELECT SUM(amount) FROM orders")
        assert isinstance(stmt.columns[0], AggregateExpr)
        assert stmt.columns[0].func == 'SUM'

    def test_avg(self):
        stmt = parse("SELECT AVG(score) FROM exams")
        assert isinstance(stmt.columns[0], AggregateExpr)
        assert stmt.columns[0].func == 'AVG'


class TestParserErrors:
    def test_empty_input(self):
        with pytest.raises(ParserError):
            parse("")

    def test_unexpected_token(self):
        with pytest.raises(ParserError):
            parse("SELECT FROM WHERE")

    def test_missing_from(self):
        with pytest.raises(ParserError):
            parse("SELECT id users")

    def test_unexpected_eof(self):
        with pytest.raises(ParserError):
            parse("SELECT id FROM ")
