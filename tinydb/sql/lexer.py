"""SQL lexer: tokenizes SQL strings into Token list."""
from dataclasses import dataclass
from enum import Enum

from tinydb.sql.errors import LexerError


class TokenType(Enum):
    """Token type enumeration."""

    # Keywords
    SELECT = "SELECT"
    FROM = "FROM"
    WHERE = "WHERE"
    INSERT = "INSERT"
    INTO = "INTO"
    VALUES = "VALUES"
    UPDATE = "UPDATE"
    SET = "SET"
    DELETE = "DELETE"
    CREATE = "CREATE"
    TABLE = "TABLE"
    DROP = "DROP"
    ORDER = "ORDER"
    BY = "BY"
    LIMIT = "LIMIT"
    OFFSET = "OFFSET"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    NULL = "NULL"
    PRIMARY = "PRIMARY"
    KEY = "KEY"
    UNIQUE = "UNIQUE"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    ASC = "ASC"
    DESC = "DESC"
    GROUP = "GROUP"
    AS = "AS"

    # Literals
    INT_LIT = "INT_LIT"
    FLOAT_LIT = "FLOAT_LIT"
    STR_LIT = "STR_LIT"
    BOOL_LIT = "BOOL_LIT"
    IDENT = "IDENT"

    # Operators
    OP = "OP"

    # Delimiters
    COMMA = "COMMA"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    SEMICOLON = "SEMICOLON"
    STAR = "STAR"

    EOF = "EOF"


_KEYWORDS: dict = {
    "SELECT": TokenType.SELECT,
    "FROM": TokenType.FROM,
    "WHERE": TokenType.WHERE,
    "INSERT": TokenType.INSERT,
    "INTO": TokenType.INTO,
    "VALUES": TokenType.VALUES,
    "UPDATE": TokenType.UPDATE,
    "SET": TokenType.SET,
    "DELETE": TokenType.DELETE,
    "CREATE": TokenType.CREATE,
    "TABLE": TokenType.TABLE,
    "DROP": TokenType.DROP,
    "ORDER": TokenType.ORDER,
    "BY": TokenType.BY,
    "LIMIT": TokenType.LIMIT,
    "OFFSET": TokenType.OFFSET,
    "AND": TokenType.AND,
    "OR": TokenType.OR,
    "NOT": TokenType.NOT,
    "NULL": TokenType.NULL,
    "PRIMARY": TokenType.PRIMARY,
    "KEY": TokenType.KEY,
    "UNIQUE": TokenType.UNIQUE,
    "INTEGER": TokenType.INTEGER,
    "FLOAT": TokenType.FLOAT,
    "TEXT": TokenType.TEXT,
    "BOOLEAN": TokenType.BOOLEAN,
    "ASC": TokenType.ASC,
    "DESC": TokenType.DESC,
    "GROUP": TokenType.GROUP,
    "AS": TokenType.AS,
    "TRUE": TokenType.BOOL_LIT,
    "FALSE": TokenType.BOOL_LIT,
}


@dataclass
class Token:
    """A single token from the lexer."""

    type: TokenType
    value: object
    line: int
    column: int
    offset: int
    text: str


class Lexer:
    """Tokenizes SQL strings into a list of tokens."""

    def tokenize(self, sql: str) -> list:
        """Tokenize a SQL string into tokens."""
        tokens = []
        self._sql = sql
        self._pos = 0
        self._line = 1
        self._col = 1

        while self._pos < len(sql):
            self._skip_whitespace()
            if self._pos >= len(sql):
                break

            ch = sql[self._pos]

            if ch == ',':
                tokens.append(self._make_token(TokenType.COMMA, ','))
            elif ch == '(':
                tokens.append(self._make_token(TokenType.LPAREN, '('))
            elif ch == ')':
                tokens.append(self._make_token(TokenType.RPAREN, ')'))
            elif ch == ';':
                tokens.append(self._make_token(TokenType.SEMICOLON, ';'))
            elif ch == '*':
                tokens.append(self._make_token(TokenType.STAR, '*'))
            elif ch in '+-/':
                tokens.append(self._make_op(ch))
            elif ch == '!':
                tokens.append(self._scan_not_equal())
            elif ch == '=':
                tokens.append(self._make_op('='))
            elif ch == '<':
                tokens.append(self._scan_lt())
            elif ch == '>':
                tokens.append(self._scan_gt())
            elif ch == "'":
                tokens.append(self._scan_string())
            elif ch.isdigit():
                tokens.append(self._scan_number())
            elif ch.isalpha() or ch == '_':
                tokens.append(self._scan_identifier())
            else:
                raise LexerError(
                    f"Unexpected character '{ch}'", self._line, self._col
                )

        tokens.append(Token(TokenType.EOF, None, self._line, self._col, self._pos, ""))
        return tokens

    def _skip_whitespace(self) -> None:
        sql = self._sql
        while self._pos < len(sql) and sql[self._pos] in ' \t\r\n':
            if sql[self._pos] == '\n':
                self._line += 1
                self._col = 1
            else:
                self._col += 1
            self._pos += 1

    def _make_token(self, type: TokenType, value: object) -> Token:
        tok = Token(type, value, self._line, self._col, self._pos, str(value))
        self._pos += 1
        self._col += 1
        return tok

    def _make_op(self, op: str) -> Token:
        tok = Token(TokenType.OP, op, self._line, self._col, self._pos, op)
        self._pos += 1
        self._col += 1
        return tok

    def _scan_not_equal(self) -> Token:
        if self._pos + 1 < len(self._sql) and self._sql[self._pos + 1] == '=':
            tok = Token(TokenType.OP, '!=', self._line, self._col, self._pos, '!=')
            self._pos += 2
            self._col += 2
            return tok
        raise LexerError("Expected '=' after '!'", self._line, self._col)

    def _scan_lt(self) -> Token:
        if self._pos + 1 < len(self._sql) and self._sql[self._pos + 1] == '=':
            tok = Token(TokenType.OP, '<=', self._line, self._col, self._pos, '<=')
            self._pos += 2
            self._col += 2
            return tok
        if self._pos + 1 < len(self._sql) and self._sql[self._pos + 1] == '>':
            tok = Token(TokenType.OP, '<>', self._line, self._col, self._pos, '<>')
            self._pos += 2
            self._col += 2
            return tok
        return self._make_op('<')

    def _scan_gt(self) -> Token:
        if self._pos + 1 < len(self._sql) and self._sql[self._pos + 1] == '=':
            tok = Token(TokenType.OP, '>=', self._line, self._col, self._pos, '>=')
            self._pos += 2
            self._col += 2
            return tok
        return self._make_op('>')

    def _scan_string(self) -> Token:
        start_line, start_col = self._line, self._col
        self._pos += 1
        self._col += 1
        sql = self._sql
        chars = []
        while self._pos < len(sql) and sql[self._pos] != "'":
            if sql[self._pos] == '\n':
                self._line += 1
                self._col = 1
            else:
                self._col += 1
            chars.append(sql[self._pos])
            self._pos += 1
        if self._pos >= len(sql):
            raise LexerError("Unterminated string literal", start_line, start_col)
        self._pos += 1
        self._col += 1
        value = ''.join(chars)
        return Token(TokenType.STR_LIT, value, start_line, start_col, self._pos, f"'{value}'")

    def _scan_number(self) -> Token:
        start_line, start_col = self._line, self._col
        sql = self._sql
        chars = []
        while self._pos < len(sql) and sql[self._pos].isdigit():
            chars.append(sql[self._pos])
            self._pos += 1
            self._col += 1
        if self._pos < len(sql) and sql[self._pos] == '.':
            chars.append('.')
            self._pos += 1
            self._col += 1
            while self._pos < len(sql) and sql[self._pos].isdigit():
                chars.append(sql[self._pos])
                self._pos += 1
                self._col += 1
            return Token(TokenType.FLOAT_LIT, float(''.join(chars)), start_line, start_col, self._pos, ''.join(chars))
        return Token(TokenType.INT_LIT, int(''.join(chars)), start_line, start_col, self._pos, ''.join(chars))

    def _scan_identifier(self) -> Token:
        start_line, start_col = self._line, self._col
        sql = self._sql
        chars = []
        while self._pos < len(sql) and (sql[self._pos].isalnum() or sql[self._pos] == '_'):
            chars.append(sql[self._pos])
            self._pos += 1
            self._col += 1
        text = ''.join(chars)
        upper = text.upper()
        if upper in _KEYWORDS:
            tt = _KEYWORDS[upper]
            if tt == TokenType.BOOL_LIT:
                return Token(tt, upper == "TRUE", start_line, start_col, self._pos, text)
            return Token(tt, upper, start_line, start_col, self._pos, text)
        return Token(TokenType.IDENT, text, start_line, start_col, self._pos, text)
