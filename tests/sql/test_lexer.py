"""Tests for SQL lexer."""
import pytest
from tinydb.sql.lexer import TokenType, Lexer
from tinydb.sql.errors import LexerError


class TestKeywords:
    def test_select_keyword(self):
        tokens = Lexer().tokenize("SELECT")
        assert tokens[0].type == TokenType.SELECT
        assert tokens[0].value == "SELECT"

    def test_from_keyword(self):
        tokens = Lexer().tokenize("FROM")
        assert tokens[0].type == TokenType.FROM

    def test_where_keyword(self):
        tokens = Lexer().tokenize("WHERE")
        assert tokens[0].type == TokenType.WHERE

    def test_all_keywords(self):
        keywords = [
            "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES",
            "UPDATE", "SET", "DELETE", "CREATE", "TABLE", "DROP",
            "ORDER", "BY", "LIMIT", "OFFSET", "AND", "OR", "NOT",
            "NULL", "PRIMARY", "KEY", "UNIQUE", "INTEGER", "FLOAT",
            "TEXT", "BOOLEAN", "ASC", "DESC", "GROUP", "AS",
        ]
        for kw in keywords:
            tokens = Lexer().tokenize(kw)
            assert tokens[0].type == TokenType(kw), f"Failed for keyword: {kw}"

    def test_keywords_case_insensitive(self):
        tokens = Lexer().tokenize("select")
        assert tokens[0].type == TokenType.SELECT
        tokens = Lexer().tokenize("Select")
        assert tokens[0].type == TokenType.SELECT


class TestLiterals:
    def test_integer_literal(self):
        tokens = Lexer().tokenize("42")
        assert tokens[0].type == TokenType.INT_LIT
        assert tokens[0].value == 42

    def test_negative_integer(self):
        tokens = Lexer().tokenize("-7")
        assert tokens[0].type == TokenType.OP
        assert tokens[0].value == '-'
        assert tokens[1].type == TokenType.INT_LIT
        assert tokens[1].value == 7

    def test_float_literal(self):
        tokens = Lexer().tokenize("3.14")
        assert tokens[0].type == TokenType.FLOAT_LIT
        assert tokens[0].value == 3.14

    def test_string_literal(self):
        tokens = Lexer().tokenize("'hello'")
        assert tokens[0].type == TokenType.STR_LIT
        assert tokens[0].value == "hello"

    def test_empty_string_literal(self):
        tokens = Lexer().tokenize("''")
        assert tokens[0].type == TokenType.STR_LIT
        assert tokens[0].value == ""

    def test_boolean_true(self):
        tokens = Lexer().tokenize("TRUE")
        assert tokens[0].type == TokenType.BOOL_LIT
        assert tokens[0].value is True

    def test_boolean_false(self):
        tokens = Lexer().tokenize("FALSE")
        assert tokens[0].type == TokenType.BOOL_LIT
        assert tokens[0].value is False


class TestOperators:
    def test_equals(self):
        tokens = Lexer().tokenize("=")
        assert tokens[0].type == TokenType.OP
        assert tokens[0].value == '='

    def test_not_equal_bang(self):
        tokens = Lexer().tokenize("!=")
        assert tokens[0].type == TokenType.OP
        assert tokens[0].value == '!='

    def test_not_equal_angle(self):
        tokens = Lexer().tokenize("<>")
        assert tokens[0].type == TokenType.OP
        assert tokens[0].value == '<>'

    def test_less_than(self):
        tokens = Lexer().tokenize("<")
        assert tokens[0].type == TokenType.OP
        assert tokens[0].value == '<'

    def test_less_equal(self):
        tokens = Lexer().tokenize("<=")
        assert tokens[0].type == TokenType.OP
        assert tokens[0].value == '<='

    def test_greater_than(self):
        tokens = Lexer().tokenize(">")
        assert tokens[0].type == TokenType.OP
        assert tokens[0].value == '>'

    def test_greater_equal(self):
        tokens = Lexer().tokenize(">=")
        assert tokens[0].type == TokenType.OP
        assert tokens[0].value == '>='

    def test_arithmetic_ops(self):
        for op in ['+', '-', '/']:
            tokens = Lexer().tokenize(op)
            assert tokens[0].type == TokenType.OP
            assert tokens[0].value == op
        # * is a STAR token, not OP
        tokens = Lexer().tokenize('*')
        assert tokens[0].type == TokenType.STAR


class TestDelimiters:
    def test_comma(self):
        tokens = Lexer().tokenize(",")
        assert tokens[0].type == TokenType.COMMA

    def test_lparen(self):
        tokens = Lexer().tokenize("(")
        assert tokens[0].type == TokenType.LPAREN

    def test_rparen(self):
        tokens = Lexer().tokenize(")")
        assert tokens[0].type == TokenType.RPAREN

    def test_semicolon(self):
        tokens = Lexer().tokenize(";")
        assert tokens[0].type == TokenType.SEMICOLON

    def test_star(self):
        tokens = Lexer().tokenize("*")
        assert tokens[0].type == TokenType.STAR


class TestIdentifiers:
    def test_simple_identifier(self):
        tokens = Lexer().tokenize("users")
        assert tokens[0].type == TokenType.IDENT
        assert tokens[0].value == "users"

    def test_underscore_identifier(self):
        tokens = Lexer().tokenize("user_name")
        assert tokens[0].type == TokenType.IDENT
        assert tokens[0].value == "user_name"

    def test_leading_underscore(self):
        tokens = Lexer().tokenize("_temp")
        assert tokens[0].type == TokenType.IDENT
        assert tokens[0].value == "_temp"

    def test_identifier_with_digits(self):
        tokens = Lexer().tokenize("col1")
        assert tokens[0].type == TokenType.IDENT
        assert tokens[0].value == "col1"


class TestComplexInput:
    def test_select_statement(self):
        tokens = Lexer().tokenize("SELECT id, name FROM users")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [
            TokenType.SELECT, TokenType.IDENT, TokenType.COMMA,
            TokenType.IDENT, TokenType.FROM, TokenType.IDENT,
        ]

    def test_where_clause(self):
        tokens = Lexer().tokenize("WHERE id = 1")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [
            TokenType.WHERE, TokenType.IDENT, TokenType.OP, TokenType.INT_LIT,
        ]

    def test_whitespace_skipped(self):
        tokens = Lexer().tokenize("  SELECT   id  FROM  users  ")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [
            TokenType.SELECT, TokenType.IDENT, TokenType.FROM, TokenType.IDENT,
        ]

    def test_eof_always_present(self):
        tokens = Lexer().tokenize("SELECT")
        assert tokens[-1].type == TokenType.EOF

    def test_empty_input(self):
        tokens = Lexer().tokenize("")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF


class TestLexerErrors:
    def test_unexpected_character(self):
        with pytest.raises(LexerError):
            Lexer().tokenize("@")

    def test_unterminated_string(self):
        with pytest.raises(LexerError):
            Lexer().tokenize("'unterminated")


class TestTokenPosition:
    def test_line_column_tracking(self):
        tokens = Lexer().tokenize("SELECT\n  id")
        assert tokens[0].line == 1
        assert tokens[0].column == 1
        assert tokens[1].line == 2
        assert tokens[1].column == 3
