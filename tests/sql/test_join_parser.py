# tests/sql/test_join_parser.py
"""Tests for JOIN parsing."""
import pytest
from tinydb.sql.parser import Parser
from tinydb.sql.lexer import Lexer
from tinydb.sql.ast import TableRef
from tinydb.sql.expressions import ColumnRef, BinaryOp


def parse(sql: str):
    return Parser().parse(Lexer().tokenize(sql))


class TestParseTableRef:
    def test_simple_table(self):
        stmt = parse("SELECT id FROM users")
        assert isinstance(stmt.from_table, TableRef)
        assert stmt.from_table.name == "users"
        assert stmt.from_table.alias is None

    def test_table_with_alias(self):
        stmt = parse("SELECT id FROM users AS u")
        assert stmt.from_table.name == "users"
        assert stmt.from_table.alias == "u"

    def test_table_with_implicit_alias(self):
        stmt = parse("SELECT id FROM users u")
        assert stmt.from_table.name == "users"
        assert stmt.from_table.alias == "u"


class TestParseInnerJoin:
    def test_inner_join_on(self):
        stmt = parse("SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id")
        assert len(stmt.joins) == 1
        join = stmt.joins[0]
        assert join.join_type == "INNER"
        assert join.right_table.name == "orders"
        assert join.right_table.alias == "o"
        assert isinstance(join.on_condition, BinaryOp)

    def test_join_without_inner_keyword(self):
        stmt = parse("SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id")
        assert stmt.joins[0].join_type == "INNER"

    def test_inner_join_explicit(self):
        stmt = parse("SELECT u.id FROM users u INNER JOIN orders o ON u.id = o.user_id")
        assert stmt.joins[0].join_type == "INNER"


class TestParseLeftJoin:
    def test_left_join(self):
        stmt = parse("SELECT u.id FROM users u LEFT JOIN orders o ON u.id = o.user_id")
        assert stmt.joins[0].join_type == "LEFT"

    def test_left_outer_join(self):
        stmt = parse("SELECT u.id FROM users u LEFT OUTER JOIN orders o ON u.id = o.user_id")
        assert stmt.joins[0].join_type == "LEFT"


class TestParseRightJoin:
    def test_right_join(self):
        stmt = parse("SELECT u.id FROM users u RIGHT JOIN orders o ON u.id = o.user_id")
        assert stmt.joins[0].join_type == "RIGHT"

    def test_right_outer_join(self):
        stmt = parse("SELECT u.id FROM users u RIGHT OUTER JOIN orders o ON u.id = o.user_id")
        assert stmt.joins[0].join_type == "RIGHT"


class TestParseFullJoin:
    def test_full_join(self):
        stmt = parse("SELECT u.id FROM users u FULL JOIN orders o ON u.id = o.user_id")
        assert stmt.joins[0].join_type == "FULL"

    def test_full_outer_join(self):
        stmt = parse("SELECT u.id FROM users u FULL OUTER JOIN orders o ON u.id = o.user_id")
        assert stmt.joins[0].join_type == "FULL"


class TestParseCrossJoin:
    def test_cross_join(self):
        stmt = parse("SELECT u.id FROM users u CROSS JOIN orders")
        assert len(stmt.joins) == 1
        assert stmt.joins[0].join_type == "CROSS"
        assert stmt.joins[0].on_condition is None


class TestParseNaturalJoin:
    def test_natural_join(self):
        stmt = parse("SELECT u.id FROM users u NATURAL JOIN orders")
        assert len(stmt.joins) == 1
        assert stmt.joins[0].join_type == "NATURAL"
        assert stmt.joins[0].on_condition is None


class TestParseJoinUsing:
    def test_join_using(self):
        stmt = parse("SELECT u.id FROM users u JOIN orders o USING (id)")
        join = stmt.joins[0]
        assert join.using_columns == ["id"]

    def test_join_using_multiple_columns(self):
        stmt = parse("SELECT u.id FROM users u JOIN orders o USING (id, name)")
        assert stmt.joins[0].using_columns == ["id", "name"]


class TestParseMultiJoin:
    def test_three_table_join(self):
        sql = """SELECT u.id FROM users u
                 JOIN orders o ON u.id = o.user_id
                 JOIN items i ON o.id = i.order_id"""
        stmt = parse(sql)
        assert len(stmt.joins) == 2
        assert stmt.joins[0].right_table.name == "orders"
        assert stmt.joins[1].right_table.name == "items"


class TestParseQualifiedColumnRef:
    def test_qualified_column_in_select(self):
        stmt = parse("SELECT u.id, o.amount FROM users u JOIN orders o ON u.id = o.user_id")
        col0 = stmt.columns[0]
        assert isinstance(col0, ColumnRef)
        assert col0.name == "id"
        assert col0.table == "u"

    def test_qualified_column_in_on(self):
        stmt = parse("SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id")
        on = stmt.joins[0].on_condition
        assert isinstance(on, BinaryOp)
        assert isinstance(on.left, ColumnRef)
        assert on.left.table == "u"
        assert on.left.name == "id"
        assert isinstance(on.right, ColumnRef)
        assert on.right.table == "o"
        assert on.right.name == "user_id"


class TestParserErrors:
    def test_join_without_table(self):
        with pytest.raises(Exception):
            parse("SELECT id FROM users JOIN")

    def test_join_without_on_or_using(self):
        with pytest.raises(Exception):
            parse("SELECT id FROM users JOIN orders")
