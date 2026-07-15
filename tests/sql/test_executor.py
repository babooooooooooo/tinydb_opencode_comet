"""Tests for executor operators."""
import pytest
from tinydb.sql.executor import (
    ScanOperator, FilterOperator, ProjectOperator,
    AggregateOperator, SortOperator, LimitOperator,
)
from tinydb.sql.expressions import (
    ColumnRef, Literal, BinaryOp, AggregateExpr, StarExpr,
    _to_bool,
)
from tinydb.types import ColumnDef, DataType


class TestScanOperator:
    def test_scan_all_rows(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        op = ScanOperator(table, pool)
        rows = list(op)
        assert len(rows) == 3

    def test_scan_empty_table(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        catalog.create_table("empty", [
            ColumnDef(name="id", data_type=DataType.INTEGER),
        ], pk="id")
        table = catalog.get_table("empty")
        op = ScanOperator(table, pool)
        rows = list(op)
        assert len(rows) == 0


class TestFilterOperator:
    def test_filter_with_where(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        condition = BinaryOp('=', ColumnRef("name"), Literal("Alice"))
        filtered = FilterOperator(scan, condition)
        rows = list(filtered)
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"

    def test_filter_no_match(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        condition = BinaryOp('=', ColumnRef("name"), Literal("Nobody"))
        filtered = FilterOperator(scan, condition)
        rows = list(filtered)
        assert len(rows) == 0


class TestProjectOperator:
    def test_project_columns(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        proj = ProjectOperator(scan, [("id", ColumnRef("id")), ("name", ColumnRef("name"))])
        rows = list(proj)
        assert len(rows) == 3
        assert set(rows[0].keys()) == {"id", "name"}

    def test_project_with_expression(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        proj = ProjectOperator(scan, [("id_plus_one", BinaryOp('+', ColumnRef("id"), Literal(1)))])
        rows = list(proj)
        assert rows[0]["id_plus_one"] == 2


class TestAggregateOperator:
    def test_count_all(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        agg = AggregateOperator(scan, [], [("count", "COUNT", StarExpr())])
        rows = list(agg)
        assert len(rows) == 1
        assert rows[0]["count"] == 3

    def test_sum(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        agg = AggregateOperator(scan, [], [("total", "SUM", ColumnRef("id"))])
        rows = list(agg)
        assert len(rows) == 1
        assert rows[0]["total"] == 6

    def test_avg(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        agg = AggregateOperator(scan, [], [("avg_val", "AVG", ColumnRef("id"))])
        rows = list(agg)
        assert len(rows) == 1
        assert rows[0]["avg_val"] == 2.0

    def test_group_by(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        agg = AggregateOperator(
            scan,
            [ColumnRef("name")],
            [("count", "COUNT", StarExpr())]
        )
        rows = list(agg)
        assert len(rows) == 3


class TestSortOperator:
    def test_sort_ascending(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        sorted_op = SortOperator(scan, [(ColumnRef("name"), "ASC")])
        rows = list(sorted_op)
        names = [r["name"] for r in rows]
        assert names == ["Alice", "Bob", "Charlie"]

    def test_sort_descending(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        sorted_op = SortOperator(scan, [(ColumnRef("name"), "DESC")])
        rows = list(sorted_op)
        names = [r["name"] for r in rows]
        assert names == ["Charlie", "Bob", "Alice"]


class TestLimitOperator:
    def test_limit_only(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        limited = LimitOperator(scan, 2, 0)
        rows = list(limited)
        assert len(rows) == 2

    def test_offset_only(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        limited = LimitOperator(scan, None, 1)
        rows = list(limited)
        assert len(rows) == 2

    def test_limit_and_offset(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        limited = LimitOperator(scan, 1, 1)
        rows = list(limited)
        assert len(rows) == 1
