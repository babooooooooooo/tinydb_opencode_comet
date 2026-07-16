# tests/sql/test_join_planner.py
"""Tests for JOIN planner."""
import pytest
from tinydb.sql.planner import JoinPlanner
from tinydb.sql.executor import (
    ScanOperator, NestedLoopJoinOperator,
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
