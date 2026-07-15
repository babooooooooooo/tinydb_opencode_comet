"""Tests for SQL error hierarchy."""
import pytest
from tinydb.sql.errors import (
    SQLError, LexerError, ParserError,
    PlanningError, ExecutionError, ConstraintError,
)


class TestSQLError:
    def test_base_error_with_message(self):
        err = SQLError("something went wrong")
        assert "something went wrong" in str(err)
        assert err.line == 0
        assert err.column == 0

    def test_error_with_position(self):
        err = SQLError("bad token", line=3, column=12)
        assert err.line == 3
        assert err.column == 12
        assert "[3:12]" in str(err)

    def test_error_is_exception(self):
        with pytest.raises(Exception):
            raise SQLError("test")


class TestLexerError:
    def test_lexer_error_is_sql_error(self):
        err = LexerError("unexpected char", line=1, column=5)
        assert isinstance(err, SQLError)
        assert err.line == 1
        assert err.column == 5


class TestParserError:
    def test_parser_error_is_sql_error(self):
        err = ParserError("expected FROM", line=2, column=8)
        assert isinstance(err, SQLError)


class TestPlanningError:
    def test_planning_error_is_sql_error(self):
        err = PlanningError("unknown table")
        assert isinstance(err, SQLError)


class TestExecutionError:
    def test_execution_error_is_sql_error(self):
        err = ExecutionError("division by zero")
        assert isinstance(err, SQLError)


class TestConstraintError:
    def test_constraint_error_is_sql_error(self):
        err = ConstraintError("NOT NULL violated")
        assert isinstance(err, SQLError)
