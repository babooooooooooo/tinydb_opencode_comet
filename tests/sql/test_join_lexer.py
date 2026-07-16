# tests/sql/test_join_lexer.py
"""Tests for JOIN-related lexer tokens."""
from tinydb.sql.lexer import TokenType, Lexer


class TestJoinKeywords:
    def test_join_keyword(self):
        tokens = Lexer().tokenize("JOIN")
        assert tokens[0].type == TokenType.JOIN
        assert tokens[0].value == "JOIN"

    def test_inner_keyword(self):
        tokens = Lexer().tokenize("INNER")
        assert tokens[0].type == TokenType.INNER

    def test_left_keyword(self):
        tokens = Lexer().tokenize("LEFT")
        assert tokens[0].type == TokenType.LEFT

    def test_right_keyword(self):
        tokens = Lexer().tokenize("RIGHT")
        assert tokens[0].type == TokenType.RIGHT

    def test_full_keyword(self):
        tokens = Lexer().tokenize("FULL")
        assert tokens[0].type == TokenType.FULL

    def test_outer_keyword(self):
        tokens = Lexer().tokenize("OUTER")
        assert tokens[0].type == TokenType.OUTER

    def test_cross_keyword(self):
        tokens = Lexer().tokenize("CROSS")
        assert tokens[0].type == TokenType.CROSS

    def test_natural_keyword(self):
        tokens = Lexer().tokenize("NATURAL")
        assert tokens[0].type == TokenType.NATURAL

    def test_on_keyword(self):
        tokens = Lexer().tokenize("ON")
        assert tokens[0].type == TokenType.ON

    def test_using_keyword(self):
        tokens = Lexer().tokenize("USING")
        assert tokens[0].type == TokenType.USING

    def test_keywords_case_insensitive(self):
        for kw in ["join", "inner", "left", "right", "full", "outer", "cross", "natural", "on", "using"]:
            tokens = Lexer().tokenize(kw)
            assert tokens[0].type == TokenType(kw.upper()), f"Failed for: {kw}"


class TestDotToken:
    def test_dot_token(self):
        tokens = Lexer().tokenize(".")
        assert tokens[0].type == TokenType.DOT
        assert tokens[0].value == "."

    def test_qualified_column(self):
        tokens = Lexer().tokenize("u.name")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [TokenType.IDENT, TokenType.DOT, TokenType.IDENT]

    def test_join_expression(self):
        tokens = Lexer().tokenize("JOIN orders ON users.id = orders.user_id")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [
            TokenType.JOIN, TokenType.IDENT, TokenType.ON,
            TokenType.IDENT, TokenType.DOT, TokenType.IDENT,
            TokenType.OP,
            TokenType.IDENT, TokenType.DOT, TokenType.IDENT,
        ]
