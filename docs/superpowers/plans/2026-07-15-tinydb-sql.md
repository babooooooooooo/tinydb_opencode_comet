---
change: tinydb-sql
design-doc: docs/superpowers/specs/2026-07-15-tinydb-sql-design.md
base-ref: e57b8135ac3360f61ca8e560c3c1b4cec648f988
---

# tinydb-sql Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a SQL engine layer for tinydb that parses SQL strings, plans queries, and executes them against the storage engine.

**Architecture:** Classic database architecture: Lexer → Parser → Planner → Executor (Volcano model). Each stage is a separate module with clear interfaces. The SQL engine wraps the existing storage engine (Catalog + Table API) without modifying it.

**Tech Stack:** Python 3.10+, pytest, dataclasses, enum, standard library only.

## Global Constraints

- Zero external dependencies (Python 3.10+ stdlib only)
- All code in `tinydb/sql/` package
- Tests in `tests/sql/` package
- Follow existing codebase style (dataclasses, type hints, Chinese comments acceptable)
- TDD: write failing test first, then implement
- Each task ends with a commit
- IS NULL / IS NOT NULL: YES
- COUNT(*): YES (special literal)
- Multi-row VALUES: YES
- MIN/MAX: NO
- Quoted identifiers: NO

---

## File Structure

```
tinydb/sql/
  __init__.py        # package exports
  errors.py          # SQLError hierarchy
  lexer.py           # Lexer + Token + TokenType
  ast.py             # AST statement nodes
  expressions.py     # Expression tree + evaluate(row)
  parser.py          # Recursive descent parser
  planner.py         # AST → Operator tree
  executor.py        # Volcano model operators
  result.py          # QueryResult
  database.py        # Database.execute() entry point

tests/sql/
  __init__.py
  conftest.py        # shared fixtures
  test_lexer.py
  test_parser.py
  test_expressions.py
  test_planner.py
  test_executor.py
  test_constraints.py
  test_database.py
  test_integration.py
```

---

## Task 1: Package Skeleton + Error Hierarchy

**Files:**
- Create: `tinydb/sql/__init__.py`
- Create: `tinydb/sql/errors.py`
- Create: `tests/sql/__init__.py`
- Create: `tests/sql/test_errors.py`

**Interfaces:**
- Produces: `SQLError`, `LexerError`, `ParserError`, `PlanningError`, `ExecutionError`, `ConstraintError`

- [ ] **Step 1: Write the failing test**

```python
# tests/sql/test_errors.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_errors.py -v`
Expected: FAIL with "No module named 'tinydb.sql'"

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/sql/__init__.py
"""tinydb SQL engine package."""

# tinydb/sql/errors.py
"""SQL engine error hierarchy."""


class SQLError(Exception):
    """SQL 引擎所有异常的基类."""

    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.line = line
        self.column = column
        if line > 0:
            super().__init__(f"[{line}:{column}] {message}")
        else:
            super().__init__(message)


class LexerError(SQLError):
    """词法分析错误."""
    pass


class ParserError(SQLError):
    """语法分析错误."""
    pass


class PlanningError(SQLError):
    """查询计划错误."""
    pass


class ExecutionError(SQLError):
    """执行时错误."""
    pass


class ConstraintError(SQLError):
    """约束违反错误."""
    pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_errors.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tinydb/sql/__init__.py tinydb/sql/errors.py tests/sql/__init__.py tests/sql/test_errors.py
git commit -m "feat(sql): add error hierarchy (SQLError and subclasses)"
```

---

## Task 2: Lexer — Token Types + Keyword Recognition

**Files:**
- Create: `tinydb/sql/lexer.py`
- Create: `tests/sql/test_lexer.py`

**Interfaces:**
- Consumes: `LexerError` from `tinydb.sql.errors`
- Produces: `Token`, `TokenType`, `Lexer` class

- [ ] **Step 1: Write the failing test**

```python
# tests/sql/test_lexer.py
"""Tests for SQL lexer."""
import pytest
from tinydb.sql.lexer import Token, TokenType, Lexer
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
        # '-' is an OP, '7' is INT_LIT
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
        for op in ['+', '-', '*', '/']:
            tokens = Lexer().tokenize(op)
            assert tokens[0].type == TokenType.OP
            assert tokens[0].value == op


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_lexer.py -v`
Expected: FAIL with "No module named 'tinydb.sql.lexer'"

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/sql/lexer.py
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


_KEYWORDS: dict[str, TokenType] = {
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

    def tokenize(self, sql: str) -> list[Token]:
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

            # Single-char delimiters / operators
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
            elif ch in '+-':
                tokens.append(self._make_op(ch))
            elif ch == '!':
                tokens.append(self._scan_not_equal())

            # Multi-char operators
            elif ch == '=':
                tokens.append(self._make_op('='))
            elif ch == '<':
                tokens.append(self._scan_lt())
            elif ch == '>':
                tokens.append(self._scan_gt())

            # Literals
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
        self._pos += 1  # skip opening quote
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
        self._pos += 1  # skip closing quote
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
        # Check if it's a keyword (case-insensitive)
        upper = text.upper()
        if upper in _KEYWORDS:
            tt = _KEYWORDS[upper]
            if tt == TokenType.BOOL_LIT:
                return Token(tt, upper == "TRUE", start_line, start_col, self._pos, text)
            return Token(tt, upper, start_line, start_col, self._pos, text)
        return Token(TokenType.IDENT, text, start_line, start_col, self._pos, text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_lexer.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tinydb/sql/lexer.py tests/sql/test_lexer.py
git commit -m "feat(sql): implement SQL lexer with keyword recognition"
```

---

## Task 3: AST Nodes

**Files:**
- Create: `tinydb/sql/ast.py`
- Create: `tests/sql/test_ast.py`

**Interfaces:**
- Produces: `SelectStatement`, `InsertStatement`, `UpdateStatement`, `DeleteStatement`, `CreateTableStatement`, `DropTableStatement`, `ColumnDefAST`

- [ ] **Step 1: Write the failing test**

```python
# tests/sql/test_ast.py
"""Tests for AST node definitions."""
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
    ColumnDefAST,
)


class TestASTNodes:
    def test_select_statement(self):
        stmt = SelectStatement(columns=["id", "name"], table="users")
        assert stmt.table == "users"
        assert stmt.columns == ["id", "name"]
        assert stmt.where is None
        assert stmt.order_by is None
        assert stmt.limit is None
        assert stmt.offset is None
        assert stmt.group_by is None

    def test_insert_statement(self):
        stmt = InsertStatement(table="users", columns=["id", "name"], values=[[1, "Alice"]])
        assert stmt.table == "users"
        assert stmt.columns == ["id", "name"]
        assert stmt.values == [[1, "Alice"]]

    def test_insert_without_columns(self):
        stmt = InsertStatement(table="users", columns=None, values=[[1, "Alice"]])
        assert stmt.columns is None

    def test_update_statement(self):
        stmt = UpdateStatement(table="users", assignments=[("name", "Bob")])
        assert stmt.table == "users"
        assert stmt.assignments == [("name", "Bob")]
        assert stmt.where is None

    def test_delete_statement(self):
        stmt = DeleteStatement(table="users")
        assert stmt.table == "users"
        assert stmt.where is None

    def test_create_table_statement(self):
        cols = [ColumnDefAST("id", "INTEGER", primary_key=True)]
        stmt = CreateTableStatement(table="users", columns=cols)
        assert stmt.table == "users"
        assert len(stmt.columns) == 1
        assert stmt.columns[0].name == "id"

    def test_drop_table_statement(self):
        stmt = DropTableStatement(table="users")
        assert stmt.table == "users"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_ast.py -v`
Expected: FAIL with "No module named 'tinydb.sql.ast'"

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/sql/ast.py
"""AST node definitions for SQL statements."""
from dataclasses import dataclass
from typing import Optional

from tinydb.sql.expressions import Expression


@dataclass
class SelectStatement:
    """SELECT statement AST node."""
    columns: list  # list[Expression]
    table: str
    where: Optional[Expression] = None
    order_by: Optional[list] = None  # list[tuple[Expression, str]]
    limit: Optional[int] = None
    offset: Optional[int] = None
    group_by: Optional[list] = None  # list[Expression]


@dataclass
class InsertStatement:
    """INSERT statement AST node."""
    table: str
    columns: Optional[list[str]]  # None means not specified
    values: list[list]  # list[list[Expression]] — supports multi-row


@dataclass
class UpdateStatement:
    """UPDATE statement AST node."""
    table: str
    assignments: list  # list[tuple[str, Expression]]
    where: Optional[Expression] = None


@dataclass
class DeleteStatement:
    """DELETE statement AST node."""
    table: str
    where: Optional[Expression] = None


@dataclass
class ColumnDefAST:
    """Column definition in CREATE TABLE."""
    name: str
    data_type: str  # "INTEGER", "FLOAT", "TEXT", "BOOLEAN"
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    not_null: bool = False


@dataclass
class CreateTableStatement:
    """CREATE TABLE statement AST node."""
    table: str
    columns: list  # list[ColumnDefAST]


@dataclass
class DropTableStatement:
    """DROP TABLE statement AST node."""
    table: str


# Union type for all statements
Statement = SelectStatement | InsertStatement | UpdateStatement | DeleteStatement | CreateTableStatement | DropTableStatement
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_ast.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tinydb/sql/ast.py tests/sql/test_ast.py
git commit -m "feat(sql): add AST node definitions"
```

---

## Task 4: Expressions + Evaluation

**Files:**
- Create: `tinydb/sql/expressions.py`
- Create: `tests/sql/test_expressions.py`

**Interfaces:**
- Consumes: `ExecutionError` from `tinydb.sql.errors`
- Produces: `Expression`, `ColumnRef`, `Literal`, `BinaryOp`, `UnaryOp`, `AggregateExpr`, `StarExpr`, `IsNullExpr`

- [ ] **Step 1: Write the failing test**

```python
# tests/sql/test_expressions.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_expressions.py -v`
Expected: FAIL with "No module named 'tinydb.sql.expressions'"

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/sql/expressions.py
"""Expression tree definitions and evaluation."""
from dataclasses import dataclass

from tinydb.sql.errors import ExecutionError


class Expression:
    """Base class for all expressions."""

    def evaluate(self, row: dict) -> object:
        raise NotImplementedError


@dataclass
class Literal(Expression):
    """Literal value expression."""
    value: object

    def evaluate(self, row: dict) -> object:
        return self.value


@dataclass
class ColumnRef(Expression):
    """Column reference expression."""
    name: str

    def evaluate(self, row: dict) -> object:
        return row.get(self.name)


@dataclass
class StarExpr(Expression):
    """STAR (*) expression for SELECT * and COUNT(*)."""
    def evaluate(self, row: dict) -> object:
        return '*'


@dataclass
class BinaryOp(Expression):
    """Binary operation expression."""
    op: str
    left: Expression
    right: Expression

    def evaluate(self, row: dict) -> object:
        left_val = self.left.evaluate(row)
        right_val = self.right.evaluate(row)

        if self.op == 'AND':
            return _to_bool(left_val) and _to_bool(right_val)
        if self.op == 'OR':
            return _to_bool(left_val) or _to_bool(right_val)
        if self.op == '=':
            return _compare_eq(left_val, right_val)
        if self.op in ('!=', '<>'):
            return not _compare_eq(left_val, right_val)
        if self.op == '<':
            return _compare_lt(left_val, right_val)
        if self.op == '>':
            return _compare_gt(left_val, right_val)
        if self.op == '<=':
            return _compare_le(left_val, right_val)
        if self.op == '>=':
            return _compare_ge(left_val, right_val)
        if self.op == '+':
            return left_val + right_val
        if self.op == '-':
            return left_val - right_val
        if self.op == '*':
            return left_val * right_val
        if self.op == '/':
            if right_val == 0:
                raise ExecutionError("Division by zero")
            return left_val / right_val

        raise ExecutionError(f"Unknown operator: {self.op}")


@dataclass
class UnaryOp(Expression):
    """Unary operation expression."""
    op: str
    operand: Expression

    def evaluate(self, row: dict) -> object:
        val = self.operand.evaluate(row)
        if self.op == 'NOT':
            return not _to_bool(val)
        if self.op == '-':
            return -val
        raise ExecutionError(f"Unknown unary operator: {self.op}")


@dataclass
class AggregateExpr(Expression):
    """Aggregate function expression (COUNT, SUM, AVG)."""
    func: str
    arg: Expression
    distinct: bool = False

    def evaluate(self, row: dict) -> object:
        raise NotImplementedError("AggregateExpr requires AggregateOperator")


@dataclass
class IsNullExpr(Expression):
    """IS NULL / IS NOT NULL expression."""
    operand: Expression
    negated: bool = False  # False = IS NULL, True = IS NOT NULL

    def evaluate(self, row: dict) -> object:
        val = self.operand.evaluate(row)
        is_null = val is None
        return not is_null if self.negated else is_null


# --- Helper functions ---

def _to_bool(val: object) -> bool:
    """Convert value to boolean. NULL → False."""
    if val is None:
        return False
    return bool(val)


def _compare_eq(left: object, right: object) -> bool:
    """Equality comparison. NULL on either side → False."""
    if left is None or right is None:
        return False
    return left == right


def _compare_lt(left: object, right: object) -> bool:
    """Less-than comparison. NULL → False."""
    if left is None or right is None:
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left < right
    if isinstance(left, str) and isinstance(right, str):
        return left < right
    raise ExecutionError(f"Cannot compare {type(left)} with {type(right)}")


def _compare_gt(left: object, right: object) -> bool:
    """Greater-than comparison. NULL → False."""
    if left is None or right is None:
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left > right
    if isinstance(left, str) and isinstance(right, str):
        return left > right
    raise ExecutionError(f"Cannot compare {type(left)} with {type(right)}")


def _compare_le(left: object, right: object) -> bool:
    """Less-than-or-equal comparison. NULL → False."""
    if left is None or right is None:
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left <= right
    if isinstance(left, str) and isinstance(right, str):
        return left <= right
    raise ExecutionError(f"Cannot compare {type(left)} with {type(right)}")


def _compare_ge(left: object, right: object) -> bool:
    """Greater-than-or-equal comparison. NULL → False."""
    if left is None or right is None:
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left >= right
    if isinstance(left, str) and isinstance(right, str):
        return left >= right
    raise ExecutionError(f"Cannot compare {type(left)} with {type(right)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_expressions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tinydb/sql/expressions.py tests/sql/test_expressions.py
git commit -m "feat(sql): implement expression tree with evaluation"
```

---

## Task 5: Parser — Core Statements

**Files:**
- Create: `tinydb/sql/parser.py`
- Create: `tests/sql/test_parser.py`

**Interfaces:**
- Consumes: `Token`, `TokenType`, `Lexer`, `ParserError`, AST nodes, expressions
- Produces: `Parser` class

- [ ] **Step 1: Write the failing test**

```python
# tests/sql/test_parser.py
"""Tests for SQL parser."""
import pytest
from tinydb.sql.parser import Parser
from tinydb.sql.lexer import Lexer
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
    ColumnDefAST,
)
from tinydb.sql.expressions import (
    ColumnRef, Literal, BinaryOp, StarExpr, AggregateExpr,
    IsNullExpr,
)
from tinydb.sql.errors import ParserError


def parse(sql: str):
    return Parser().parse(Lexer().tokenize(sql))


class TestSelectParsing:
    def test_simple_select(self):
        stmt = parse("SELECT id, name FROM users")
        assert isinstance(stmt, SelectStatement)
        assert stmt.table == "users"
        assert len(stmt.columns) == 2
        assert isinstance(stmt.columns[0], ColumnRef)
        assert stmt.columns[0].name == "id"

    def test_select_star(self):
        stmt = parse("SELECT * FROM users")
        assert isinstance(stmt, SelectStatement)
        assert len(stmt.columns) == 1
        assert isinstance(stmt.columns[0], StarExpr)

    def test_select_where(self):
        stmt = parse("SELECT id FROM users WHERE id = 1")
        assert isinstance(stmt, SelectStatement)
        assert isinstance(stmt.where, BinaryOp)
        assert stmt.where.op == '='

    def test_select_order_by(self):
        stmt = parse("SELECT id FROM users ORDER BY id ASC")
        assert isinstance(stmt, SelectStatement)
        assert stmt.order_by is not None
        assert len(stmt.order_by) == 1
        assert stmt.order_by[0][1] == "ASC"

    def test_select_limit(self):
        stmt = parse("SELECT id FROM users LIMIT 10")
        assert isinstance(stmt, SelectStatement)
        assert stmt.limit == 10

    def test_select_offset(self):
        stmt = parse("SELECT id FROM users LIMIT 10 OFFSET 5")
        assert isinstance(stmt, SelectStatement)
        assert stmt.limit == 10
        assert stmt.offset == 5

    def test_select_group_by(self):
        stmt = parse("SELECT name FROM users GROUP BY name")
        assert isinstance(stmt, SelectStatement)
        assert stmt.group_by is not None
        assert len(stmt.group_by) == 1

    def test_select_all_clauses(self):
        stmt = parse(
            "SELECT id, name FROM users WHERE id > 1 ORDER BY name ASC LIMIT 10 OFFSET 5"
        )
        assert isinstance(stmt, SelectStatement)
        assert stmt.table == "users"
        assert len(stmt.columns) == 2
        assert stmt.where is not None
        assert stmt.order_by is not None
        assert stmt.limit == 10
        assert stmt.offset == 5


class TestInsertParsing:
    def test_insert_with_columns(self):
        stmt = parse("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        assert isinstance(stmt, InsertStatement)
        assert stmt.table == "users"
        assert stmt.columns == ["id", "name"]
        assert len(stmt.values) == 1

    def test_insert_without_columns(self):
        stmt = parse("INSERT INTO users VALUES (1, 'Alice')")
        assert isinstance(stmt, InsertStatement)
        assert stmt.columns is None

    def test_insert_multi_row(self):
        stmt = parse("INSERT INTO users VALUES (1, 'A'), (2, 'B'), (3, 'C')")
        assert isinstance(stmt, InsertStatement)
        assert len(stmt.values) == 3


class TestUpdateParsing:
    def test_update_set(self):
        stmt = parse("UPDATE users SET name = 'Bob' WHERE id = 1")
        assert isinstance(stmt, UpdateStatement)
        assert stmt.table == "users"
        assert len(stmt.assignments) == 1
        assert stmt.assignments[0][0] == "name"
        assert isinstance(stmt.where, BinaryOp)

    def test_update_multiple_sets(self):
        stmt = parse("UPDATE users SET name = 'Bob', age = 30 WHERE id = 1")
        assert isinstance(stmt, UpdateStatement)
        assert len(stmt.assignments) == 2


class TestDeleteParsing:
    def test_delete(self):
        stmt = parse("DELETE FROM users WHERE id = 1")
        assert isinstance(stmt, DeleteStatement)
        assert stmt.table == "users"
        assert isinstance(stmt.where, BinaryOp)

    def test_delete_no_where(self):
        stmt = parse("DELETE FROM users")
        assert isinstance(stmt, DeleteStatement)
        assert stmt.where is None


class TestCreateTableParsing:
    def test_create_table(self):
        stmt = parse("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        assert isinstance(stmt, CreateTableStatement)
        assert stmt.table == "users"
        assert len(stmt.columns) == 2
        assert isinstance(stmt.columns[0], ColumnDefAST)
        assert stmt.columns[0].name == "id"
        assert stmt.columns[0].data_type == "INTEGER"
        assert stmt.columns[0].primary_key is True

    def test_create_table_with_constraints(self):
        stmt = parse("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE)")
        assert isinstance(stmt, CreateTableStatement)
        assert stmt.columns[1].not_null is True
        assert stmt.columns[2].unique is True


class TestDropTableParsing:
    def test_drop_table(self):
        stmt = parse("DROP TABLE users")
        assert isinstance(stmt, DropTableStatement)
        assert stmt.table == "users"


class TestExpressionPrecedence:
    def test_and_or_precedence(self):
        stmt = parse("SELECT id FROM users WHERE a = 1 AND b = 2 OR c = 3")
        # OR should be at the top (lower precedence)
        assert isinstance(stmt.where, BinaryOp)
        assert stmt.where.op == 'OR'

    def test_not_precedence(self):
        stmt = parse("SELECT id FROM users WHERE NOT a = 1")
        from tinydb.sql.expressions import UnaryOp
        assert isinstance(stmt.where, UnaryOp)
        assert stmt.where.op == 'NOT'

    def test_arithmetic_precedence(self):
        stmt = parse("SELECT id FROM users WHERE a + b * c = 1")
        # * binds tighter than +
        assert isinstance(stmt.where, BinaryOp)
        assert stmt.where.op == '='

    def test_parentheses_override(self):
        stmt = parse("SELECT id FROM users WHERE (a + b) * c = 1")
        assert isinstance(stmt.where, BinaryOp)
        assert stmt.where.op == '='


class TestIsNull:
    def test_is_null(self):
        stmt = parse("SELECT id FROM users WHERE name IS NULL")
        assert isinstance(stmt.where, IsNullExpr)
        assert stmt.where.negated is False

    def test_is_not_null(self):
        stmt = parse("SELECT id FROM users WHERE name IS NOT NULL")
        assert isinstance(stmt.where, IsNullExpr)
        assert stmt.where.negated is True


class TestAggregateFunctions:
    def test_count_star(self):
        stmt = parse("SELECT COUNT(*) FROM users")
        assert isinstance(stmt.columns[0], AggregateExpr)
        assert stmt.columns[0].func == 'COUNT'
        assert isinstance(stmt.columns[0].arg, StarExpr)

    def test_count_column(self):
        stmt = parse("SELECT COUNT(id) FROM users")
        assert isinstance(stmt.columns[0], AggregateExpr)
        assert stmt.columns[0].func == 'COUNT'

    def test_sum(self):
        stmt = parse("SELECT SUM(amount) FROM orders")
        assert isinstance(stmt.columns[0], AggregateExpr)
        assert stmt.columns[0].func == 'SUM'

    def test_avg(self):
        stmt = parse("SELECT AVG(score) FROM exams")
        assert isinstance(stmt.columns[0], AggregateExpr)
        assert stmt.columns[0].func == 'AVG'


class TestParserErrors:
    def test_empty_input(self):
        with pytest.raises(ParserError):
            parse("")

    def test_unexpected_token(self):
        with pytest.raises(ParserError):
            parse("SELECT FROM WHERE")

    def test_missing_from(self):
        with pytest.raises(ParserError):
            parse("SELECT id users")

    def test_unexpected_eof(self):
        with pytest.raises(ParserError):
            parse("SELECT id FROM ")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_parser.py -v`
Expected: FAIL with "No module named 'tinydb.sql.parser'"

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/sql/parser.py
"""Recursive descent SQL parser."""
from tinydb.sql.lexer import Token, TokenType, Lexer
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
    ColumnDefAST,
)
from tinydb.sql.expressions import (
    Expression, ColumnRef, Literal, BinaryOp, UnaryOp,
    AggregateExpr, StarExpr, IsNullExpr,
)
from tinydb.sql.errors import ParserError


class Parser:
    """Recursive descent parser for SQL statements."""

    def __init__(self):
        self._tokens: list[Token] = []
        self._pos: int = 0

    def parse(self, tokens: list[Token]) -> object:
        """Parse a list of tokens into a Statement AST node."""
        self._tokens = tokens
        self._pos = 0
        stmt = self._parse_statement()
        self._expect(TokenType.EOF)
        return stmt

    def _parse_statement(self) -> object:
        tok = self._peek()
        if tok.type == TokenType.SELECT:
            return self._parse_select()
        elif tok.type == TokenType.INSERT:
            return self._parse_insert()
        elif tok.type == TokenType.UPDATE:
            return self._parse_update()
        elif tok.type == TokenType.DELETE:
            return self._parse_delete()
        elif tok.type == TokenType.CREATE:
            return self._parse_create()
        elif tok.type == TokenType.DROP:
            return self._parse_drop()
        else:
            raise ParserError(
                f"Unexpected token: {tok.text}", tok.line, tok.column
            )

    def _parse_select(self) -> SelectStatement:
        self._expect(TokenType.SELECT)
        columns = self._parse_select_columns()
        self._expect(TokenType.FROM)
        table = self._expect(TokenType.IDENT).value
        where = self._parse_where() if self._match(TokenType.WHERE) else None
        group_by = self._parse_group_by() if self._check(TokenType.GROUP) else None
        order_by = self._parse_order_by() if self._check(TokenType.ORDER) else None
        limit = self._parse_limit() if self._match(TokenType.LIMIT) else None
        offset = self._parse_offset() if self._match(TokenType.OFFSET) else None
        return SelectStatement(columns, table, where, order_by, limit, offset, group_by)

    def _parse_select_columns(self) -> list[Expression]:
        """Parse SELECT column list (handles * and aggregates)."""
        if self._peek().type == TokenType.STAR:
            self._advance()
            return [StarExpr()]
        return self._parse_expression_list()

    def _parse_insert(self) -> InsertStatement:
        self._expect(TokenType.INSERT)
        self._expect(TokenType.INTO)
        table = self._expect(TokenType.IDENT).value
        columns = None
        if self._match(TokenType.LPAREN):
            columns = []
            while self._peek().type == TokenType.IDENT:
                columns.append(self._advance().value)
                if not self._match(TokenType.COMMA):
                    break
            self._expect(TokenType.RPAREN)
        self._expect(TokenType.VALUES)
        values = self._parse_value_lists()
        return InsertStatement(table, columns, values)

    def _parse_value_lists(self) -> list[list]:
        """Parse one or more VALUE lists: (expr, ...), (expr, ...)"""
        values = []
        self._expect(TokenType.LPAREN)
        row = self._parse_expression_list()
        self._expect(TokenType.RPAREN)
        values.append(row)
        while self._match(TokenType.COMMA):
            self._expect(TokenType.LPAREN)
            row = self._parse_expression_list()
            self._expect(TokenType.RPAREN)
            values.append(row)
        return values

    def _parse_update(self) -> UpdateStatement:
        self._expect(TokenType.UPDATE)
        table = self._expect(TokenType.IDENT).value
        self._expect(TokenType.SET)
        assignments = self._parse_assignment_list()
        where = self._parse_where() if self._match(TokenType.WHERE) else None
        return UpdateStatement(table, assignments, where)

    def _parse_delete(self) -> DeleteStatement:
        self._expect(TokenType.DELETE)
        self._expect(TokenType.FROM)
        table = self._expect(TokenType.IDENT).value
        where = self._parse_where() if self._match(TokenType.WHERE) else None
        return DeleteStatement(table, where)

    def _parse_create(self) -> CreateTableStatement:
        self._expect(TokenType.CREATE)
        self._expect(TokenType.TABLE)
        table = self._expect(TokenType.IDENT).value
        self._expect(TokenType.LPAREN)
        columns = self._parse_column_definitions()
        self._expect(TokenType.RPAREN)
        return CreateTableStatement(table, columns)

    def _parse_column_definitions(self) -> list[ColumnDefAST]:
        columns = []
        while self._peek().type == TokenType.IDENT:
            name = self._advance().value
            data_type_tok = self._advance()
            data_type = data_type_tok.value.upper()
            nullable = True
            primary_key = False
            unique = False
            not_null = False
            # Parse constraints
            while self._peek().type in (TokenType.PRIMARY, TokenType.UNIQUE, TokenType.NOT, TokenType.NULL):
                if self._match(TokenType.PRIMARY):
                    self._expect(TokenType.KEY)
                    primary_key = True
                    nullable = False
                elif self._match(TokenType.UNIQUE):
                    unique = True
                elif self._match(TokenType.NOT):
                    self._expect(TokenType.NULL)
                    not_null = True
                    nullable = False
                elif self._match(TokenType.NULL):
                    nullable = True
            columns.append(ColumnDefAST(name, data_type, nullable, primary_key, unique, not_null))
            if not self._match(TokenType.COMMA):
                break
        return columns

    def _parse_drop(self) -> DropTableStatement:
        self._expect(TokenType.DROP)
        self._expect(TokenType.TABLE)
        table = self._expect(TokenType.IDENT).value
        return DropTableStatement(table)

    def _parse_where(self) -> Expression:
        return self._parse_expression()

    def _parse_group_by(self) -> list[Expression]:
        self._expect(TokenType.GROUP)
        self._expect(TokenType.BY)
        return self._parse_expression_list()

    def _parse_order_by(self) -> list:
        self._expect(TokenType.ORDER)
        self._expect(TokenType.BY)
        items = []
        expr = self._parse_expression()
        direction = "ASC"
        if self._match(TokenType.ASC):
            direction = "ASC"
        elif self._match(TokenType.DESC):
            direction = "DESC"
        items.append((expr, direction))
        while self._match(TokenType.COMMA):
            expr = self._parse_expression()
            direction = "ASC"
            if self._match(TokenType.ASC):
                direction = "ASC"
            elif self._match(TokenType.DESC):
                direction = "DESC"
            items.append((expr, direction))
        return items

    def _parse_limit(self) -> int:
        return self._expect(TokenType.INT_LIT).value

    def _parse_offset(self) -> int:
        return self._expect(TokenType.INT_LIT).value

    def _parse_assignment_list(self) -> list:
        assignments = []
        col = self._expect(TokenType.IDENT).value
        self._expect(TokenType.OP)  # =
        # The '=' is an OP token with value '='
        if self._peek().value == '=':
            self._advance()
        expr = self._parse_expression()
        assignments.append((col, expr))
        while self._match(TokenType.COMMA):
            col = self._expect(TokenType.IDENT).value
            self._expect(TokenType.OP)
            if self._peek().value == '=':
                self._advance()
            expr = self._parse_expression()
            assignments.append((col, expr))
        return assignments

    def _parse_expression_list(self) -> list[Expression]:
        exprs = [self._parse_expression()]
        while self._match(TokenType.COMMA):
            exprs.append(self._parse_expression())
        return exprs

    # --- Expression parsing with precedence ---

    def _parse_expression(self) -> Expression:
        """OR (lowest precedence)"""
        left = self._parse_and()
        while self._match(TokenType.OR):
            right = self._parse_and()
            left = BinaryOp('OR', left, right)
        return left

    def _parse_and(self) -> Expression:
        left = self._parse_not()
        while self._match(TokenType.AND):
            right = self._parse_not()
            left = BinaryOp('AND', left, right)
        return left

    def _parse_not(self) -> Expression:
        if self._match(TokenType.NOT):
            operand = self._parse_not()
            return UnaryOp('NOT', operand)
        return self._parse_isnull()

    def _parse_isnull(self) -> Expression:
        left = self._parse_comparison()
        if self._match(TokenType.IS):
            negated = False
            if self._match(TokenType.NOT):
                negated = True
            self._expect(TokenType.NULL)
            return IsNullExpr(left, negated=negated)
        return left

    def _parse_comparison(self) -> Expression:
        left = self._parse_additive()
        comp_ops = ('=', '!=', '<>', '<', '>', '<=', '>=')
        while (self._peek().type == TokenType.OP and self._peek().value in comp_ops):
            op = self._advance().value
            right = self._parse_additive()
            left = BinaryOp(op, left, right)
        return left

    def _parse_additive(self) -> Expression:
        left = self._parse_multiplicative()
        while self._peek().type == TokenType.OP and self._peek().value in ('+', '-'):
            op = self._advance().value
            right = self._parse_multiplicative()
            left = BinaryOp(op, left, right)
        return left

    def _parse_multiplicative(self) -> Expression:
        left = self._parse_unary()
        while self._peek().type == TokenType.OP and self._peek().value in ('*', '/'):
            op = self._advance().value
            right = self._parse_unary()
            left = BinaryOp(op, left, right)
        return left

    def _parse_unary(self) -> Expression:
        if self._peek().type == TokenType.OP and self._peek().value == '-':
            self._advance()
            operand = self._parse_primary()
            return UnaryOp('-', operand)
        return self._parse_primary()

    def _parse_primary(self) -> Expression:
        tok = self._peek()

        # Literals
        if tok.type in (TokenType.INT_LIT, TokenType.FLOAT_LIT, TokenType.STR_LIT):
            self._advance()
            return Literal(tok.value)

        if tok.type == TokenType.BOOL_LIT:
            self._advance()
            return Literal(tok.value)

        if tok.type == TokenType.NULL:
            self._advance()
            return Literal(None)

        # Aggregate functions
        if tok.type == TokenType.IDENT and tok.value.upper() in ('COUNT', 'SUM', 'AVG'):
            return self._parse_aggregate()

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        # Column reference
        if tok.type == TokenType.IDENT:
            self._advance()
            return ColumnRef(tok.value)

        raise ParserError(
            f"Unexpected token in expression: {tok.text}", tok.line, tok.column
        )

    def _parse_aggregate(self) -> AggregateExpr:
        func_tok = self._advance()
        func = func_tok.value.upper()
        self._expect(TokenType.LPAREN)
        if self._peek().type == TokenType.STAR:
            self._advance()
            arg = StarExpr()
        else:
            arg = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return AggregateExpr(func, arg)

    # --- Token manipulation helpers ---

    def _peek(self) -> Token:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return self._tokens[-1]  # EOF

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return tok

    def _match(self, type: TokenType) -> bool:
        if self._peek().type == type:
            self._advance()
            return True
        return False

    def _check(self, type: TokenType) -> bool:
        return self._peek().type == type

    def _expect(self, type: TokenType) -> Token:
        if self._peek().type != type:
            tok = self._peek()
            raise ParserError(
                f"Expected {type.value}, got {tok.text}", tok.line, tok.column
            )
        return self._advance()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tinydb/sql/parser.py tests/sql/test_parser.py
git commit -m "feat(sql): implement recursive descent parser"
```

---

## Task 6: Query Planner

**Files:**
- Create: `tinydb/sql/planner.py`
- Create: `tests/sql/test_planner.py`

**Interfaces:**
- Consumes: AST nodes, expressions, `Catalog`, `BufferPool`
- Produces: `Planner` class, `Operator` base class

- [ ] **Step 1: Write the failing test**

```python
# tests/sql/test_planner.py
"""Tests for query planner."""
import pytest
from tinydb.sql.planner import Planner, ScanOperator, FilterOperator, ProjectOperator, SortOperator, LimitOperator, AggregateOperator
from tinydb.sql.parser import Parser
from tinydb.sql.lexer import Lexer
from tinydb.sql.expressions import ColumnRef, Literal, BinaryOp, AggregateExpr, StarExpr
from tinydb.sql.ast import SelectStatement
from tinydb.sql.errors import PlanningError


class TestPlanner:
    def test_simple_select_plan(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT id, name FROM users"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        # Should be: Project → Scan
        assert isinstance(op, ProjectOperator)
        assert isinstance(op.source, ScanOperator)

    def test_select_with_where(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT id FROM users WHERE id = 1"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        # Should be: Project → Filter → Scan
        assert isinstance(op, ProjectOperator)
        assert isinstance(op.source, FilterOperator)
        assert isinstance(op.source.source, ScanOperator)

    def test_select_with_order_by(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT id FROM users ORDER BY id DESC"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        # Should be: Sort → Project → Scan
        assert isinstance(op, SortOperator)

    def test_select_with_limit(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT id FROM users LIMIT 10"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        # Should be: Limit → Project → Scan
        assert isinstance(op, LimitOperator)

    def test_aggregate_plan(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        stmt = Parser().parse(Lexer().tokenize("SELECT COUNT(*) FROM users"))
        planner = Planner(catalog, pool)
        op = planner.plan(stmt)
        # Should be: Aggregate → Scan
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_planner.py -v`
Expected: FAIL with "No module named 'tinydb.sql.planner'"

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/sql/planner.py
"""Query planner: converts AST to operator tree."""
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
)
from tinydb.sql.expressions import (
    Expression, ColumnRef, AggregateExpr, StarExpr, _to_bool,
)
from tinydb.sql.executor import (
    Operator, ScanOperator, FilterOperator, ProjectOperator,
    AggregateOperator, SortOperator, LimitOperator,
)
from tinydb.sql.errors import PlanningError


class Planner:
    """Converts AST statements into operator trees."""

    def __init__(self, catalog, buffer_pool):
        self.catalog = catalog
        self.buffer_pool = buffer_pool

    def plan(self, stmt) -> Operator:
        """Plan a statement and return the root operator."""
        if isinstance(stmt, SelectStatement):
            return self._plan_select(stmt)
        elif isinstance(stmt, (InsertStatement, UpdateStatement, DeleteStatement)):
            # DML statements use DmlOperator
            from tinydb.sql.executor import DmlOperator
            return DmlOperator(stmt, self.catalog, self.buffer_pool)
        elif isinstance(stmt, CreateTableStatement):
            from tinydb.sql.executor import CreateTableOperator
            return CreateTableOperator(stmt, self.catalog)
        elif isinstance(stmt, DropTableStatement):
            from tinydb.sql.executor import DropTableOperator
            return DropTableOperator(stmt, self.catalog)
        else:
            raise PlanningError(f"Unknown statement type: {type(stmt)}")

    def _plan_select(self, stmt: SelectStatement) -> Operator:
        # 1. Scan
        table = self.catalog.get_table(stmt.table)
        op: Operator = ScanOperator(table, self.buffer_pool)

        # 2. Filter (WHERE)
        if stmt.where:
            op = FilterOperator(op, stmt.where)

        # 3. Aggregate or Project
        has_agg = any(isinstance(col, AggregateExpr) for col in stmt.columns)

        if has_agg or stmt.group_by:
            group_keys = stmt.group_by or []
            aggregations = []
            for col in stmt.columns:
                if isinstance(col, AggregateExpr):
                    alias = col.func.lower()
                    if isinstance(col.arg, StarExpr):
                        alias = col.func.lower() + "_*"
                    aggregations.append((alias, col.func, col.arg))
                elif isinstance(col, ColumnRef):
                    aggregations.append((col.name, 'VALUE', col))
                else:
                    aggregations.append((str(col), 'VALUE', col))
            op = AggregateOperator(op, group_keys, aggregations)
        else:
            # Project
            projections = []
            for col in stmt.columns:
                if isinstance(col, StarExpr):
                    projections.append(('*', col))
                elif isinstance(col, ColumnRef):
                    projections.append((col.name, col))
                elif isinstance(col, AggregateExpr):
                    projections.append((col.func.lower(), col))
                else:
                    projections.append((str(col), col))
            op = ProjectOperator(op, projections)

        # 4. Sort (ORDER BY)
        if stmt.order_by:
            op = SortOperator(op, stmt.order_by)

        # 5. Limit + Offset
        if stmt.limit is not None or stmt.offset:
            op = LimitOperator(op, stmt.limit, stmt.offset or 0)

        return op
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_planner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tinydb/sql/planner.py tests/sql/test_planner.py
git commit -m "feat(sql): implement query planner"
```

---

## Task 7: Executor — Scan, Filter, Project

**Files:**
- Create: `tinydb/sql/executor.py`
- Create: `tests/sql/test_executor.py`

**Interfaces:**
- Consumes: `Expression`, `Catalog`, `BufferPool`, AST nodes
- Produces: `Operator`, `ScanOperator`, `FilterOperator`, `ProjectOperator`, `AggregateOperator`, `SortOperator`, `LimitOperator`, `DmlOperator`, `CreateTableOperator`, `DropTableOperator`

- [ ] **Step 1: Write the failing test**

```python
# tests/sql/test_executor.py
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


class TestScanOperator:
    def test_scan_all_rows(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        op = ScanOperator(table, pool)
        rows = list(op)
        assert len(rows) == 3

    def test_scan_empty_table(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        # Create empty table
        from tinydb.types import ColumnDef, DataType
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
        assert rows[0]["total"] == 6  # 1+2+3

    def test_avg(self, catalog_and_pool):
        catalog, pool = catalog_and_pool
        table = catalog.get_table("users")
        scan = ScanOperator(table, pool)
        agg = AggregateOperator(scan, [], [("avg_val", "AVG", ColumnRef("id"))])
        rows = list(agg)
        assert len(rows) == 1
        assert rows[0]["avg_val"] == 2.0  # (1+2+3)/3

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
        assert len(rows) == 3  # 3 distinct names


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_executor.py -v`
Expected: FAIL with "No module named 'tinydb.sql.executor'"

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/sql/executor.py
"""Volcano model executor operators."""
from tinydb.sql.expressions import (
    Expression, ColumnRef, AggregateExpr, StarExpr, _to_bool,
)
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
)
from tinydb.sql.errors import ExecutionError, ConstraintError
from tinydb.sql.result import QueryResult
from tinydb.types import ColumnDef, DataType


class Operator:
    """Base class for all operators (Volcano model)."""

    def __iter__(self):
        return self

    def __next__(self) -> dict:
        raise NotImplementedError


class ScanOperator(Operator):
    """Full table scan operator."""

    def __init__(self, table, buffer_pool):
        self.table = table
        self.buffer_pool = buffer_pool

    def __iter__(self):
        col_names = [col.name for col in self.table.columns]
        for row_id, row_values in self.table.scan(self.buffer_pool):
            yield {"_rowid": row_id, **dict(zip(col_names, row_values))}


class FilterOperator(Operator):
    """WHERE clause filter operator."""

    def __init__(self, source: Operator, condition: Expression):
        self.source = source
        self.condition = condition

    def __iter__(self):
        for row in self.source:
            val = self.condition.evaluate(row)
            if _to_bool(val):
                yield row


class ProjectOperator(Operator):
    """Column projection operator."""

    def __init__(self, source: Operator, columns: list):
        self.source = source
        self.columns = columns  # list[(alias, expression)]

    def __iter__(self):
        for row in self.source:
            result = {}
            for alias, expr in self.columns:
                if alias == '*' and isinstance(expr, StarExpr):
                    # Expand all columns (exclude _rowid)
                    for k, v in row.items():
                        if k != '_rowid':
                            result[k] = v
                else:
                    result[alias] = expr.evaluate(row)
            yield result


class AggregateOperator(Operator):
    """Hash aggregation operator with GROUP BY."""

    def __init__(self, source: Operator,
                 group_keys: list,
                 aggregations: list):
        self.source = source
        self.group_keys = group_keys
        self.aggregations = aggregations  # list[(alias, func, arg_expr)]

    def __iter__(self):
        groups: dict[tuple, list] = {}

        for row in self.source:
            key = tuple(k.evaluate(row) for k in self.group_keys)
            if key not in groups:
                groups[key] = self._init_agg_state()

            state = groups[key]
            for i, (alias, func, arg_expr) in enumerate(self.aggregations):
                if func == 'VALUE':
                    state[i] = row.get(alias)
                else:
                    val = arg_expr.evaluate(row)
                    state[i] = self._accumulate(func, state[i], val)

        for key, state in groups.items():
            result = {}
            if self.group_keys:
                for i, k_exp in enumerate(self.group_keys):
                    if isinstance(k_exp, ColumnRef):
                        result[k_exp.name] = key[i]

            for i, (alias, func, _) in enumerate(self.aggregations):
                if func == 'VALUE':
                    result[alias] = state[i]
                else:
                    result[alias] = self._finalize(func, state[i])

            yield result

    def _init_agg_state(self) -> list:
        return [None] * len(self.aggregations)

    def _accumulate(self, func: str, state: object, val: object) -> object:
        if func == 'COUNT':
            return (state or 0) + 1
        elif func == 'SUM':
            if val is None:
                return state
            return (state or 0) + val
        elif func == 'AVG':
            if state is None:
                state = (0, 0)
            if val is not None:
                return (state[0] + val, state[1] + 1)
            return state
        raise ValueError(f"Unknown aggregate function: {func}")

    def _finalize(self, func: str, state: object) -> object:
        if state is None:
            return None
        if func == 'AVG':
            if state[1] == 0:
                return None
            return state[0] / state[1]
        return state


class SortOperator(Operator):
    """ORDER BY sort operator."""

    def __init__(self, source: Operator, order_keys: list):
        self.source = source
        self.order_keys = order_keys  # list[(expr, ASC|DESC)]

    def __iter__(self):
        rows = list(self.source)
        for expr, direction in reversed(self.order_keys):
            rows.sort(
                key=lambda r, e=expr: (e.evaluate(r) is None, e.evaluate(r) or 0),
                reverse=(direction == 'DESC')
            )
        yield from rows


class LimitOperator(Operator):
    """LIMIT/OFFSET operator."""

    def __init__(self, source: Operator, limit, offset: int):
        self.source = source
        self.limit = limit
        self.offset = offset

    def __iter__(self):
        iterator = iter(self.source)
        for _ in range(self.offset):
            try:
                next(iterator)
            except StopIteration:
                return

        count = 0
        for row in iterator:
            if self.limit is not None and count >= self.limit:
                return
            yield row
            count += 1


class DmlOperator(Operator):
    """DML (INSERT/UPDATE/DELETE) operator."""

    def __init__(self, stmt, catalog, buffer_pool):
        self.stmt = stmt
        self.catalog = catalog
        self.buffer_pool = buffer_pool

    def __iter__(self):
        result = self._execute()
        yield {"_result": result}

    def _execute(self) -> QueryResult:
        if isinstance(self.stmt, InsertStatement):
            return self._execute_insert()
        elif isinstance(self.stmt, UpdateStatement):
            return self._execute_update()
        elif isinstance(self.stmt, DeleteStatement):
            return self._execute_delete()

    def _execute_insert(self) -> QueryResult:
        table = self.catalog.get_table(self.stmt.table)
        col_names = [col.name for col in table.columns]

        for value_exprs in self.stmt.values:
            row_values = [expr.evaluate({}) for expr in value_exprs]
            if self.stmt.columns:
                row_dict = dict(zip(self.stmt.columns, row_values))
                ordered_row = [row_dict.get(cn) for cn in col_names]
            else:
                ordered_row = row_values
            self._check_constraints(table, ordered_row)
            table.insert(self.buffer_pool, ordered_row)

        return QueryResult([], [], len(self.stmt.values))

    def _execute_update(self) -> QueryResult:
        table = self.catalog.get_table(self.stmt.table)
        col_names = [col.name for col in table.columns]
        updated = 0

        for row_id, row_values in table.scan(self.buffer_pool):
            row_dict = dict(zip(col_names, row_values))
            if self.stmt.where is None or _to_bool(self.stmt.where.evaluate(row_dict)):
                new_row = list(row_values)
                for col_name, expr in self.stmt.assignments:
                    col_idx = col_names.index(col_name)
                    new_row[col_idx] = expr.evaluate(row_dict)
                self._check_constraints_update(table, row_id, new_row)
                table.update(self.buffer_pool, row_id, new_row)
                updated += 1

        return QueryResult([], [], updated)

    def _execute_delete(self) -> QueryResult:
        table = self.catalog.get_table(self.stmt.table)
        col_names = [col.name for col in table.columns]
        to_delete = []

        for row_id, row_values in table.scan(self.buffer_pool):
            row_dict = dict(zip(col_names, row_values))
            if self.stmt.where is None or _to_bool(self.stmt.where.evaluate(row_dict)):
                to_delete.append(row_id)

        for row_id in to_delete:
            table.delete(self.buffer_pool, row_id)

        return QueryResult([], [], len(to_delete))

    def _check_constraints(self, table, row) -> None:
        """NOT NULL + UNIQUE/PRIMARY KEY check for INSERT."""
        for i, (val, col) in enumerate(zip(row, table.columns)):
            if not col.nullable and val is None:
                raise ConstraintError(
                    f"NOT NULL constraint violated on column '{col.name}'"
                )
            if col.primary_key or col.unique:
                self._check_unique(table, i, val, exclude_row_id=None)

    def _check_constraints_update(self, table, row_id, new_row) -> None:
        """NOT NULL + UNIQUE/PRIMARY KEY check for UPDATE."""
        for i, (val, col) in enumerate(zip(new_row, table.columns)):
            if not col.nullable and val is None:
                raise ConstraintError(
                    f"NOT NULL constraint violated on column '{col.name}'"
                )
            if col.primary_key or col.unique:
                self._check_unique(table, i, val, exclude_row_id=row_id)

    def _check_unique(self, table, col_idx, value, exclude_row_id) -> None:
        from tinydb.page import RowId
        for existing_id, existing_row in table.scan(self.buffer_pool):
            if exclude_row_id is not None:
                if existing_id.page_id == exclude_row_id.page_id and existing_id.slot_index == exclude_row_id.slot_index:
                    continue
            if existing_row[col_idx] == value:
                col = table.columns[col_idx]
                raise ConstraintError(
                    f"{'PRIMARY KEY' if col.primary_key else 'UNIQUE'} "
                    f"constraint violated on column '{col.name}': "
                    f"value {value!r} already exists"
                )


class CreateTableOperator(Operator):
    """CREATE TABLE operator."""

    def __init__(self, stmt, catalog):
        self.stmt = stmt
        self.catalog = catalog

    def __iter__(self):
        result = self._execute()
        yield {"_result": result}

    def _execute(self) -> QueryResult:
        columns = []
        pk = ""
        for col_def in self.stmt.columns:
            data_type = DataType(col_def.data_type.upper())
            col = ColumnDef(
                name=col_def.name,
                data_type=data_type,
                nullable=col_def.nullable,
                primary_key=col_def.primary_key,
                unique=col_def.unique,
            )
            columns.append(col)
            if col.primary_key:
                pk = col.name

        self.catalog.create_table(self.stmt.table, columns, pk)
        return QueryResult([], [], 0)


class DropTableOperator(Operator):
    """DROP TABLE operator."""

    def __init__(self, stmt, catalog):
        self.stmt = stmt
        self.catalog = catalog

    def __iter__(self):
        result = self._execute()
        yield {"_result": result}

    def _execute(self) -> QueryResult:
        self.catalog.drop_table(self.stmt.table)
        return QueryResult([], [], 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_executor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tinydb/sql/executor.py tests/sql/test_executor.py
git commit -m "feat(sql): implement volcano model executor operators"
```

---

## Task 8: QueryResult + Database Entry Point

**Files:**
- Create: `tinydb/sql/result.py`
- Create: `tinydb/sql/database.py`
- Create: `tests/sql/test_database.py`

**Interfaces:**
- Consumes: All SQL engine modules
- Produces: `QueryResult`, `Database` class

- [ ] **Step 1: Write the failing test**

```python
# tests/sql/test_database.py
"""Tests for Database entry point."""
import pytest
from tinydb.sql.database import Database
from tinydb.sql.result import QueryResult
from tinydb.sql.errors import SQLError


class TestDatabase:
    def test_create_table(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        result = db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        assert isinstance(result, QueryResult)
        assert result.row_count == 0
        db.close()

    def test_insert_and_select(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        result = db.execute("SELECT id, name FROM users")
        assert result.row_count == 1
        assert result.columns == ["id", "name"]
        assert result.rows[0]["id"] == 1
        assert result.rows[0]["name"] == "Alice"
        db.close()

    def test_select_star(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 1
        assert "id" in result.rows[0]
        assert "name" in result.rows[0]
        db.close()

    def test_select_where(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, 'Bob')")
        result = db.execute("SELECT * FROM users WHERE id = 1")
        assert result.row_count == 1
        assert result.rows[0]["name"] == "Alice"
        db.close()

    def test_update(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        result = db.execute("UPDATE users SET name = 'Alice2' WHERE id = 1")
        assert result.row_count == 1
        result = db.execute("SELECT name FROM users WHERE id = 1")
        assert result.rows[0]["name"] == "Alice2"
        db.close()

    def test_delete(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, 'Bob')")
        result = db.execute("DELETE FROM users WHERE id = 1")
        assert result.row_count == 1
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 1
        db.close()

    def test_drop_table(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        result = db.execute("DROP TABLE users")
        assert result.row_count == 0
        db.close()

    def test_count_star(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, 'Bob')")
        result = db.execute("SELECT COUNT(*) FROM users")
        assert result.row_count == 1
        assert result.rows[0]["count_*"] == 2
        db.close()

    def test_order_by(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Charlie')")
        db.execute("INSERT INTO users VALUES (2, 'Alice')")
        db.execute("INSERT INTO users VALUES (3, 'Bob')")
        result = db.execute("SELECT name FROM users ORDER BY name ASC")
        names = [r["name"] for r in result.rows]
        assert names == ["Alice", "Bob", "Charlie"]
        db.close()

    def test_limit(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        for i in range(5):
            db.execute(f"INSERT INTO users VALUES ({i}, 'user_{i}')")
        result = db.execute("SELECT * FROM users LIMIT 3")
        assert result.row_count == 3
        db.close()

    def test_multi_row_insert(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'A'), (2, 'B'), (3, 'C')")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 3
        db.close()

    def test_is_null(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, NULL)")
        result = db.execute("SELECT * FROM users WHERE name IS NULL")
        assert result.row_count == 1
        assert result.rows[0]["id"] == 2
        db.close()

    def test_is_not_null(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, NULL)")
        result = db.execute("SELECT * FROM users WHERE name IS NOT NULL")
        assert result.row_count == 1
        assert result.rows[0]["id"] == 1
        db.close()

    def test_sql_error_propagation(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        with pytest.raises(SQLError):
            db.execute("SELECT * FROM nonexistent")
        db.close()

    def test_context_manager(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
            db.execute("INSERT INTO users VALUES (1, 'Alice')")
            result = db.execute("SELECT * FROM users")
            assert result.row_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_database.py -v`
Expected: FAIL with "No module named 'tinydb.sql.database'"

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/sql/result.py
"""QueryResult return object."""
from dataclasses import dataclass


@dataclass
class QueryResult:
    """Result of a SQL query execution."""
    rows: list[dict]
    columns: list[str]
    row_count: int

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return self.row_count

    def __repr__(self):
        if not self.rows:
            return f"QueryResult(row_count={self.row_count})"
        return f"QueryResult(columns={self.columns}, rows={len(self.rows)})"


# tinydb/sql/database.py
"""Database entry point: assembles all SQL engine modules."""
from tinydb.sql.lexer import Lexer
from tinydb.sql.parser import Parser
from tinydb.sql.planner import Planner
from tinydb.sql.executor import (
    ScanOperator, FilterOperator, ProjectOperator,
    AggregateOperator, SortOperator, LimitOperator,
    DmlOperator, CreateTableOperator, DropTableOperator,
)
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
)
from tinydb.sql.expressions import StarExpr, AggregateExpr, ColumnRef
from tinydb.sql.result import QueryResult
from tinydb.sql.errors import PlanningError
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog


class Database:
    """Main entry point for SQL execution."""

    def __init__(self, path: str):
        self.file_manager = FileManager(path)
        self.file_manager.open()
        self.buffer_pool = BufferPool(self.file_manager, capacity=100)
        self.catalog = Catalog(self.file_manager, self.buffer_pool)
        self.catalog.load()
        self._planner = Planner(self.catalog, self.buffer_pool)

    def execute(self, sql: str) -> QueryResult:
        """Execute a SQL statement and return the result."""
        # 1. Lexer
        tokens = Lexer().tokenize(sql)

        # 2. Parser
        stmt = Parser().parse(tokens)

        # 3. Plan & Execute
        if isinstance(stmt, SelectStatement):
            return self._execute_select(stmt)
        elif isinstance(stmt, InsertStatement):
            return self._execute_dml(stmt)
        elif isinstance(stmt, UpdateStatement):
            return self._execute_dml(stmt)
        elif isinstance(stmt, DeleteStatement):
            return self._execute_dml(stmt)
        elif isinstance(stmt, CreateTableStatement):
            return self._execute_ddl(stmt)
        elif isinstance(stmt, DropTableStatement):
            return self._execute_ddl(stmt)
        else:
            raise PlanningError(f"Unknown statement type: {type(stmt)}")

    def _execute_select(self, stmt: SelectStatement) -> QueryResult:
        operator = self._planner.plan(stmt)
        rows = list(operator)

        # Extract column names
        columns = []
        for col in stmt.columns:
            if isinstance(col, StarExpr):
                table = self.catalog.get_table(stmt.table)
                columns.extend(c.name for c in table.columns)
            elif isinstance(col, ColumnRef):
                columns.append(col.name)
            elif isinstance(col, AggregateExpr):
                if isinstance(col.arg, StarExpr):
                    columns.append(col.func.lower() + "_*")
                else:
                    columns.append(col.func.lower())
            else:
                columns.append(str(col))

        return QueryResult(rows, columns, len(rows))

    def _execute_dml(self, stmt) -> QueryResult:
        operator = self._planner.plan(stmt)
        for row in operator:
            return row["_result"]
        return QueryResult([], [], 0)

    def _execute_ddl(self, stmt) -> QueryResult:
        operator = self._planner.plan(stmt)
        for row in operator:
            return row["_result"]
        return QueryResult([], [], 0)

    def close(self):
        """Close the database."""
        self.catalog.save()
        self.file_manager.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tinydb/sql/result.py tinydb/sql/database.py tests/sql/test_database.py
git commit -m "feat(sql): add Database entry point and QueryResult"
```

---

## Task 9: Constraint Tests

**Files:**
- Create: `tests/sql/test_constraints.py`

**Interfaces:**
- Consumes: `Database`, `ConstraintError`

- [ ] **Step 1: Write the failing test**

```python
# tests/sql/test_constraints.py
"""Tests for constraint enforcement."""
import pytest
from tinydb.sql.database import Database
from tinydb.sql.errors import ConstraintError


class TestNotNullConstraint:
    def test_not_null_violation(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        with pytest.raises(ConstraintError, match="NOT NULL"):
            db.execute("INSERT INTO users VALUES (1, NULL)")
        db.close()

    def test_not_null_valid(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 1
        db.close()


class TestPrimaryKeyConstraint:
    def test_primary_key_duplicate(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        with pytest.raises(ConstraintError, match="PRIMARY KEY"):
            db.execute("INSERT INTO users VALUES (1, 'Bob')")
        db.close()

    def test_primary_key_unique(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO users VALUES (1, 'Alice')")
        db.execute("INSERT INTO users VALUES (2, 'Bob')")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 2
        db.close()


class TestUniqueConstraint:
    def test_unique_violation(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)")
        db.execute("INSERT INTO users VALUES (1, 'a@b.com')")
        with pytest.raises(ConstraintError, match="UNIQUE"):
            db.execute("INSERT INTO users VALUES (2, 'a@b.com')")
        db.close()

    def test_unique_valid(self, tmp_db_path):
        db = Database(str(tmp_db_path))
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)")
        db.execute("INSERT INTO users VALUES (1, 'a@b.com')")
        db.execute("INSERT INTO users VALUES (2, 'c@d.com')")
        result = db.execute("SELECT * FROM users")
        assert result.row_count == 2
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_constraints.py -v`
Expected: FAIL (constraint checks not yet implemented)

- [ ] **Step 3: Verify implementation exists**

The constraint checking is already implemented in `DmlOperator._check_constraints` and `_check_constraints_update` in `tinydb/sql/executor.py`. Run the tests to verify they pass.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_constraints.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tests/sql/test_constraints.py
git commit -m "feat(sql): add constraint enforcement tests"
```

---

## Task 10: Integration Tests

**Files:**
- Create: `tests/sql/test_integration.py`

**Interfaces:**
- Consumes: All SQL engine modules

- [ ] **Step 1: Write the failing test**

```python
# tests/sql/test_integration.py
"""End-to-end integration tests for SQL engine."""
import pytest
from tinydb.sql.database import Database
from tinydb.sql.result import QueryResult
from tinydb.sql.errors import SQLError, ConstraintError


class TestCRUDLifecycle:
    def test_full_crud(self, tmp_db_path):
        """CREATE → INSERT → SELECT → UPDATE → DELETE."""
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
            db.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
            db.execute("INSERT INTO users VALUES (2, 'Bob', 25)")

            result = db.execute("SELECT * FROM users ORDER BY id")
            assert result.row_count == 2

            db.execute("UPDATE users SET age = 31 WHERE id = 1")
            result = db.execute("SELECT age FROM users WHERE id = 1")
            assert result.rows[0]["age"] == 31

            db.execute("DELETE FROM users WHERE id = 2")
            result = db.execute("SELECT * FROM users")
            assert result.row_count == 1


class TestComplexQueries:
    def test_where_with_and_or(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, a INTEGER, b INTEGER)")
            db.execute("INSERT INTO t VALUES (1, 10, 20)")
            db.execute("INSERT INTO t VALUES (2, 10, 30)")
            db.execute("INSERT INTO t VALUES (3, 20, 20)")

            result = db.execute("SELECT * FROM t WHERE a = 10 AND b = 20")
            assert result.row_count == 1
            assert result.rows[0]["id"] == 1

    def test_group_by_with_count(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount FLOAT)")
            db.execute("INSERT INTO orders VALUES (1, 1, 10.0)")
            db.execute("INSERT INTO orders VALUES (2, 1, 20.0)")
            db.execute("INSERT INTO orders VALUES (3, 2, 15.0)")

            result = db.execute("SELECT user_id, COUNT(*) FROM orders GROUP BY user_id ORDER BY user_id")
            assert result.row_count == 2

    def test_sum_and_avg(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE scores (id INTEGER PRIMARY KEY, score FLOAT)")
            db.execute("INSERT INTO scores VALUES (1, 80.0)")
            db.execute("INSERT INTO scores VALUES (2, 90.0)")
            db.execute("INSERT INTO scores VALUES (3, 100.0)")

            result = db.execute("SELECT SUM(score) FROM scores")
            assert result.rows[0]["sum"] == 270.0

            result = db.execute("SELECT AVG(score) FROM scores")
            assert result.rows[0]["avg"] == 90.0


class TestEdgeCases:
    def test_empty_table_select(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE empty (id INTEGER PRIMARY KEY)")
            result = db.execute("SELECT * FROM empty")
            assert result.row_count == 0
            assert result.rows == []

    def test_limit_beyond_count(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            db.execute("INSERT INTO t VALUES (1)")
            result = db.execute("SELECT * FROM t LIMIT 100")
            assert result.row_count == 1

    def test_offset_beyond_count(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            db.execute("INSERT INTO t VALUES (1)")
            result = db.execute("SELECT * FROM t OFFSET 100")
            assert result.row_count == 0

    def test_multi_row_insert_three_rows(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
            db.execute("INSERT INTO t VALUES (1, 'A'), (2, 'B'), (3, 'C')")
            result = db.execute("SELECT * FROM t ORDER BY id")
            assert result.row_count == 3
            assert result.rows[0]["name"] == "A"
            assert result.rows[2]["name"] == "C"


class TestErrorHandling:
    def test_syntax_error(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            with pytest.raises(SQLError):
                db.execute("SELLECT id FROM users")

    def test_table_not_found(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            with pytest.raises(SQLError):
                db.execute("SELECT * FROM nonexistent")

    def test_duplicate_table(self, tmp_db_path):
        with Database(str(tmp_db_path)) as db:
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            with pytest.raises(SQLError):
                db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tests/sql/test_integration.py
git commit -m "feat(sql): add end-to-end integration tests"
```

---

## Task 11: Update Package Exports

**Files:**
- Modify: `tinydb/sql/__init__.py`

**Interfaces:**
- Produces: Clean public API exports

- [ ] **Step 1: Update package init**

```python
# tinydb/sql/__init__.py
"""tinydb SQL engine package."""
from tinydb.sql.database import Database
from tinydb.sql.result import QueryResult
from tinydb.sql.errors import (
    SQLError,
    LexerError,
    ParserError,
    PlanningError,
    ExecutionError,
    ConstraintError,
)

__all__ = [
    "Database",
    "QueryResult",
    "SQLError",
    "LexerError",
    "ParserError",
    "PlanningError",
    "ExecutionError",
    "ConstraintError",
]
```

- [ ] **Step 2: Run all tests**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/ -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tinydb/sql/__init__.py
git commit -m "feat(sql): update package exports"
```

---

## Task 12: conftest Fixtures for SQL Tests

**Files:**
- Create: `tests/sql/conftest.py`

**Interfaces:**
- Produces: `catalog_and_pool` fixture

- [ ] **Step 1: Write the conftest**

```python
# tests/sql/conftest.py
"""Shared fixtures for SQL engine tests."""
import tempfile
from pathlib import Path
import pytest
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.types import ColumnDef, DataType


@pytest.fixture
def tmp_db_path():
    """Provide a temporary database file path."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "test.db"


@pytest.fixture
def catalog_and_pool(tmp_db_path):
    """Provide a Catalog with a pre-built 'users' table containing 3 rows."""
    db_path = str(tmp_db_path)
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    cat = Catalog(fm, pool)
    cat.load()

    # Create users table
    cat.create_table("users", [
        ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
        ColumnDef(name="name", data_type=DataType.TEXT),
        ColumnDef(name="age", data_type=DataType.INTEGER),
    ], pk="id")

    # Insert sample data
    tbl = cat.get_table("users")
    tbl.insert(pool, [1, "Alice", 30])
    tbl.insert(pool, [2, "Bob", 25])
    tbl.insert(pool, [3, "Charlie", 35])

    yield cat, pool
    fm.close()
```

- [ ] **Step 2: Run all tests**

Run: `cd /home/lz/projects/tinydb_opencode && python -m pytest tests/sql/ -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd /home/lz/projects/tinydb_opencode
git add tests/sql/conftest.py
git commit -m "feat(sql): add shared test fixtures"
```
