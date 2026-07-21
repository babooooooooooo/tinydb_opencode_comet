"""Tests for query planner."""
import pytest
from tinydb.sql.planner import Planner, ScanOperator, FilterOperator, ProjectOperator, SortOperator, LimitOperator, AggregateOperator
from tinydb.sql.parser import Parser
from tinydb.sql.lexer import Lexer


class TestPlanner:
    def test_simple_select_plan(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT id, name FROM users"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        assert isinstance(op, ProjectOperator)
        assert isinstance(op.source, ScanOperator)

    def test_select_with_where(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT id FROM users WHERE id = 1"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        assert isinstance(op, ProjectOperator)
        assert isinstance(op.source, FilterOperator)
        assert isinstance(op.source.source, ScanOperator)

    def test_select_with_order_by(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT id FROM users ORDER BY id DESC"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        assert isinstance(op, SortOperator)

    def test_select_with_limit(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT id FROM users LIMIT 10"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        assert isinstance(op, LimitOperator)

    def test_aggregate_plan(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT COUNT(*) FROM users"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        assert isinstance(op, AggregateOperator)
        assert isinstance(op.source, ScanOperator)

    def test_group_by_plan(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT name, COUNT(*) FROM users GROUP BY name"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        assert isinstance(op, AggregateOperator)
        assert len(op.group_keys) == 1

    def test_unknown_table_raises(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT id FROM nonexistent"))
        planner = Planner(catalog, pool)
        with pytest.raises(Exception):
            planner.plan(stmt)
