# tests/sql/test_join_executor.py
"""Tests for JOIN executor operators."""
import pytest
from tinydb.sql.executor import (
    ScanOperator, NestedLoopJoinOperator,
)
from tinydb.sql.expressions import ColumnRef, Literal, BinaryOp, _to_bool
from tinydb.types import ColumnDef, DataType


def make_scan(catalog, pool, table_name):
    """Helper to create a ScanOperator for a table."""
    table = catalog.get_table(table_name)
    return ScanOperator(table, pool)


class TestNestedLoopInnerJoin:
    def test_inner_join_basic(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        left = make_scan(catalog, pool, "users")
        right = make_scan(catalog, pool, "orders")
        on = BinaryOp('=', ColumnRef("id"), ColumnRef("user_id"))
        op = NestedLoopJoinOperator(
            left, right, "INNER", on,
            "users", None, ["id", "name", "age"],
            "orders", None, ["id", "user_id", "amount"],
            ["id"]
        )
        rows = list(op)
        # users: (1,Alice,30), (2,Bob,25), (3,Charlie,35)
        # orders: (1,1,100), (2,1,200), (3,2,150)
        # join on users.id = orders.user_id → (1,1,100), (1,1,200), (2,2,150)
        assert len(rows) == 3
        amounts = sorted([r["amount"] for r in rows])
        assert amounts == [100, 150, 200]

    def test_inner_join_with_alias(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        left = make_scan(catalog, pool, "users")
        right = make_scan(catalog, pool, "orders")
        on = BinaryOp('=', ColumnRef("id"), ColumnRef("user_id"))
        op = NestedLoopJoinOperator(
            left, right, "INNER", on,
            "users", "u", ["id", "name", "age"],
            "orders", "o", ["id", "user_id", "amount"],
            ["id"]
        )
        rows = list(op)
        assert len(rows) == 3
        # With aliases, conflicting "id" column should be prefixed
        assert "u_id" in rows[0]
        assert "o_id" in rows[0]


class TestNestedLoopLeftJoin:
    def test_left_join_unmatched_nulls(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        left = make_scan(catalog, pool, "users")
        right = make_scan(catalog, pool, "orders")
        on = BinaryOp('=', ColumnRef("id"), ColumnRef("user_id"))
        op = NestedLoopJoinOperator(
            left, right, "LEFT", on,
            "users", None, ["id", "name", "age"],
            "orders", None, ["id", "user_id", "amount"],
            ["id"]
        )
        rows = list(op)
        # Charlie (id=3) has no orders → NULL row
        charlie_rows = [r for r in rows if r.get("name") == "Charlie"]
        assert len(charlie_rows) == 1
        assert charlie_rows[0]["amount"] is None


class TestNestedLoopCrossJoin:
    def test_cross_join(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        left = make_scan(catalog, pool, "users")
        right = make_scan(catalog, pool, "orders")
        op = NestedLoopJoinOperator(
            left, right, "CROSS", None,
            "users", None, ["id", "name", "age"],
            "orders", None, ["id", "user_id", "amount"],
            []
        )
        rows = list(op)
        # 3 users × 3 orders = 9 rows
        assert len(rows) == 9


class TestNestedLoopEmptyTable:
    def test_inner_join_empty_right(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        catalog.create_table("empty", [
            ColumnDef(name="id", data_type=DataType.INTEGER),
        ], pk="id")
        left = make_scan(catalog, pool, "users")
        right = make_scan(catalog, pool, "empty")
        on = BinaryOp('=', ColumnRef("id"), ColumnRef("id"))
        op = NestedLoopJoinOperator(
            left, right, "INNER", on,
            "users", None, ["id", "name", "age"],
            "empty", None, ["id"],
            ["id"]
        )
        rows = list(op)
        assert len(rows) == 0


class TestHashJoin:
    def test_inner_join(self, catalog_and_pool):
        from tinydb.sql.executor import HashJoinOperator
        catalog, pool = catalog_and_pool
        left = make_scan(catalog, pool, "users")
        right = make_scan(catalog, pool, "orders")
        on = BinaryOp('=', ColumnRef("id"), ColumnRef("user_id"))
        op = HashJoinOperator(
            left, right, "INNER", on,
            "users", None, ["id", "name", "age"],
            "orders", None, ["id", "user_id", "amount"],
            ["id"]
        )
        rows = list(op)
        assert len(rows) == 3

    def test_left_join(self, catalog_and_pool):
        from tinydb.sql.executor import HashJoinOperator
        catalog, pool = catalog_and_pool
        left = make_scan(catalog, pool, "users")
        right = make_scan(catalog, pool, "orders")
        on = BinaryOp('=', ColumnRef("id"), ColumnRef("user_id"))
        op = HashJoinOperator(
            left, right, "LEFT", on,
            "users", None, ["id", "name", "age"],
            "orders", None, ["id", "user_id", "amount"],
            ["id"]
        )
        rows = list(op)
        # 3 matched + 1 unmatched (Charlie) = 4
        assert len(rows) == 4
        charlie_rows = [r for r in rows if r.get("name") == "Charlie"]
        assert len(charlie_rows) == 1
        assert charlie_rows[0]["amount"] is None

    def test_no_match(self, catalog_and_pool):
        from tinydb.sql.executor import HashJoinOperator
        catalog, pool = catalog_and_pool
        catalog.create_table("other", [
            ColumnDef(name="id", data_type=DataType.INTEGER),
            ColumnDef(name="ref_id", data_type=DataType.INTEGER),
        ], pk="id")
        other_tbl = catalog.get_table("other")
        other_tbl.insert(pool, [1, 999])  # no match with users
        left = make_scan(catalog, pool, "users")
        right = make_scan(catalog, pool, "other")
        on = BinaryOp('=', ColumnRef("id"), ColumnRef("ref_id"))
        op = HashJoinOperator(
            left, right, "INNER", on,
            "users", None, ["id", "name", "age"],
            "other", None, ["id", "ref_id"],
            ["id"]
        )
        rows = list(op)
        assert len(rows) == 0
