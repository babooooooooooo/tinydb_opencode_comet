"""Tests for expression tree and evaluation."""
import pytest
from tinydb.sql.expressions import (
    Expression, ColumnRef, Literal, BinaryOp, UnaryOp,
    AggregateExpr, StarExpr, IsNullExpr,
    _to_bool, _compare_eq, _compare_lt,
)
from tinydb.sql.errors import ExecutionError


class TestLiteral:
    def test_literal_value(self):
        lit = Literal(42)
        assert lit.evaluate({}) == 42

    def test_literal_string(self):
        lit = Literal("hello")
        assert lit.evaluate({}) == "hello"

    def test_literal_none(self):
        lit = Literal(None)
        assert lit.evaluate({}) is None


class TestColumnRef:
    def test_column_ref(self):
        ref = ColumnRef("name")
        assert ref.evaluate({"name": "Alice"}) == "Alice"

    def test_column_ref_missing(self):
        ref = ColumnRef("missing")
        assert ref.evaluate({"name": "Alice"}) is None


class TestBinaryOp:
    def test_addition(self):
        op = BinaryOp('+', Literal(2), Literal(3))
        assert op.evaluate({}) == 5

    def test_subtraction(self):
        op = BinaryOp('-', Literal(10), Literal(4))
        assert op.evaluate({}) == 6

    def test_multiplication(self):
        op = BinaryOp('*', Literal(3), Literal(7))
        assert op.evaluate({}) == 21

    def test_division(self):
        op = BinaryOp('/', Literal(10), Literal(2))
        assert op.evaluate({}) == 5.0

    def test_division_by_zero(self):
        op = BinaryOp('/', Literal(10), Literal(0))
        with pytest.raises(ExecutionError, match="Division by zero"):
            op.evaluate({})

    def test_equality_true(self):
        op = BinaryOp('=', Literal(1), Literal(1))
        assert op.evaluate({}) is True

    def test_equality_false(self):
        op = BinaryOp('=', Literal(1), Literal(2))
        assert op.evaluate({}) is False

    def test_not_equal(self):
        op = BinaryOp('!=', Literal(1), Literal(2))
        assert op.evaluate({}) is True

    def test_less_than(self):
        op = BinaryOp('<', Literal(1), Literal(2))
        assert op.evaluate({}) is True

    def test_greater_than(self):
        op = BinaryOp('>', Literal(5), Literal(3))
        assert op.evaluate({}) is True

    def test_less_equal(self):
        op = BinaryOp('<=', Literal(3), Literal(3))
        assert op.evaluate({}) is True

    def test_greater_equal(self):
        op = BinaryOp('>=', Literal(4), Literal(3))
        assert op.evaluate({}) is True

    def test_and(self):
        op = BinaryOp('AND', Literal(True), Literal(False))
        assert op.evaluate({}) is False

    def test_or(self):
        op = BinaryOp('OR', Literal(True), Literal(False))
        assert op.evaluate({}) is True

    def test_null_comparison_eq(self):
        op = BinaryOp('=', Literal(None), Literal(1))
        assert op.evaluate({}) is False

    def test_null_comparison_neq(self):
        op = BinaryOp('!=', Literal(None), Literal(1))
        assert op.evaluate({}) is True


class TestUnaryOp:
    def test_not(self):
        op = UnaryOp('NOT', Literal(True))
        assert op.evaluate({}) is False

    def test_negate(self):
        op = UnaryOp('-', Literal(5))
        assert op.evaluate({}) == -5


class TestToBool:
    def test_none_is_false(self):
        assert _to_bool(None) is False

    def test_true(self):
        assert _to_bool(True) is True

    def test_false(self):
        assert _to_bool(False) is False

    def test_nonzero_int(self):
        assert _to_bool(42) is True

    def test_zero(self):
        assert _to_bool(0) is False

    def test_nonempty_string(self):
        assert _to_bool("hello") is True

    def test_empty_string(self):
        assert _to_bool("") is False


class TestCompare:
    def test_compare_eq_with_null(self):
        assert _compare_eq(None, 1) is False
        assert _compare_eq(1, None) is False

    def test_compare_lt_with_null(self):
        assert _compare_lt(None, 1) is False

    def test_compare_lt_numeric(self):
        assert _compare_lt(1, 2) is True
        assert _compare_lt(2, 1) is False

    def test_compare_lt_string(self):
        assert _compare_lt("a", "b") is True


class TestStarExpr:
    def test_star_expr(self):
        star = StarExpr()
        assert star.evaluate({}) == '*'


class TestAggregateExpr:
    def test_count_star(self):
        agg = AggregateExpr('COUNT', StarExpr())
        assert agg.func == 'COUNT'
        assert isinstance(agg.arg, StarExpr)

    def test_count_column(self):
        agg = AggregateExpr('COUNT', ColumnRef("id"))
        assert agg.func == 'COUNT'

    def test_sum(self):
        agg = AggregateExpr('SUM', ColumnRef("amount"))
        assert agg.func == 'SUM'

    def test_avg(self):
        agg = AggregateExpr('AVG', ColumnRef("score"))
        assert agg.func == 'AVG'

    def test_evaluate_raises(self):
        agg = AggregateExpr('COUNT', ColumnRef("id"))
        with pytest.raises(NotImplementedError):
            agg.evaluate({})


class TestIsNullExpr:
    def test_is_null_true(self):
        expr = IsNullExpr(ColumnRef("name"), negated=False)
        assert expr.evaluate({"name": None}) is True

    def test_is_null_false(self):
        expr = IsNullExpr(ColumnRef("name"), negated=False)
        assert expr.evaluate({"name": "Alice"}) is False

    def test_is_not_null_true(self):
        expr = IsNullExpr(ColumnRef("name"), negated=True)
        assert expr.evaluate({"name": "Alice"}) is True

    def test_is_not_null_false(self):
        expr = IsNullExpr(ColumnRef("name"), negated=True)
        assert expr.evaluate({"name": None}) is False
