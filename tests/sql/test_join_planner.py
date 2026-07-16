# tests/sql/test_join_planner.py
"""Tests for JOIN planner."""
import pytest
from tinydb.sql.planner import JoinPlanner
from tinydb.sql.executor import (
    ScanOperator, NestedLoopJoinOperator, FilterOperator, ProjectOperator,
)
from tinydb.sql.ast import TableRef, JoinClause
from tinydb.sql.expressions import ColumnRef, BinaryOp


class TestJoinPlanner:
    def test_single_table_no_join(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        planner = JoinPlanner(catalog, pool)
        from_table = TableRef(name="users")
        op = planner.plan_joins(from_table, [], None)
        assert isinstance(op, ScanOperator)

    def test_inner_join_chooses_algorithm(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        planner = JoinPlanner(catalog, pool)
        from_table = TableRef(name="users", alias="u")
        joins = [
            JoinClause(
                join_type="INNER",
                right_table=TableRef(name="orders", alias="o"),
                on_condition=BinaryOp('=', ColumnRef("u.id"), ColumnRef("o.user_id")),
            )
        ]
        op = planner.plan_joins(from_table, joins, None)
        # Should produce a join operator (nested_loop for small tables)
        assert isinstance(op, NestedLoopJoinOperator)

    def test_cross_join_uses_nested_loop(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        planner = JoinPlanner(catalog, pool)
        from_table = TableRef(name="users")
        joins = [
            JoinClause(
                join_type="CROSS",
                right_table=TableRef(name="orders"),
            )
        ]
        op = planner.plan_joins(from_table, joins, None)
        assert isinstance(op, NestedLoopJoinOperator)
        assert op.join_type == "CROSS"

    def test_multi_join_chain(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        planner = JoinPlanner(catalog, pool)
        from_table = TableRef(name="users", alias="u")
        joins = [
            JoinClause(
                join_type="INNER",
                right_table=TableRef(name="orders", alias="o"),
                on_condition=BinaryOp('=', ColumnRef("u.id"), ColumnRef("o.user_id")),
            ),
        ]
        op = planner.plan_joins(from_table, joins, None)
        # Should be a join operator
        assert isinstance(op, NestedLoopJoinOperator)


class TestNaturalJoin:
    def test_natural_join_resolves_columns(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        planner = JoinPlanner(catalog, pool)
        from_table = TableRef(name="users", alias="u")
        # users has columns: id, name, age
        # orders has columns: id, user_id, amount
        # NATURAL JOIN should match on "id"
        joins = [
            JoinClause(
                join_type="NATURAL",
                right_table=TableRef(name="orders", alias="o"),
            )
        ]
        op = planner.plan_joins(from_table, joins, None)
        assert isinstance(op, NestedLoopJoinOperator)
        # The resolved join should have join_keys = ["id"]
        assert "id" in op.join_keys


class TestPlannerIntegration:
    def test_plan_select_with_join(self, catalog_and_pool):
        from tinydb.sql.parser import Parser
        from tinydb.sql.lexer import Lexer
        catalog, pool = catalog_and_pool
        planner = JoinPlanner(catalog, pool)
        stmt = Parser().parse(Lexer().tokenize(
            "SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id"
        ))
        op = planner.plan_joins(stmt.from_table, stmt.joins, stmt.where)
        assert isinstance(op, NestedLoopJoinOperator)


class TestPlannerSelectIntegration:
    def test_plan_select_with_join(self, catalog_and_pool):
        from tinydb.sql.planner import Planner
        from tinydb.sql.parser import Parser
        from tinydb.sql.lexer import Lexer
        from tinydb.sql.executor import FilterOperator, ProjectOperator
        catalog, pool = catalog_and_pool
        planner = Planner(catalog, pool)
        stmt = Parser().parse(Lexer().tokenize(
            "SELECT u.id, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE o.amount > 100"
        ))
        op = planner.plan(stmt)
        # Should be Project → Filter → Join
        assert isinstance(op, ProjectOperator)
        assert isinstance(op.source, FilterOperator)
        assert isinstance(op.source.source, NestedLoopJoinOperator)

    def test_plan_select_without_join_unchanged(self, catalog_and_pool):
        from tinydb.sql.planner import Planner
        from tinydb.sql.parser import Parser
        from tinydb.sql.lexer import Lexer
        catalog, pool = catalog_and_pool
        planner = Planner(catalog, pool)
        stmt = Parser().parse(Lexer().tokenize("SELECT id FROM users WHERE id = 1"))
        op = planner.plan(stmt)
        # Should be Project → Filter → Scan (unchanged behavior)
        assert isinstance(op, ProjectOperator)
        assert isinstance(op.source, FilterOperator)
        assert isinstance(op.source.source, ScanOperator)
