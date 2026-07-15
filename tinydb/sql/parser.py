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
        self._tokens: list = []
        self._pos: int = 0

    def parse(self, tokens: list) -> object:
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

    def _parse_select_columns(self) -> list:
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

    def _parse_value_lists(self) -> list:
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

    def _parse_column_definitions(self) -> list:
        columns = []
        while self._peek().type == TokenType.IDENT:
            name = self._advance().value
            data_type_tok = self._advance()
            data_type = data_type_tok.value.upper()
            nullable = True
            primary_key = False
            unique = False
            not_null = False
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

    def _parse_group_by(self) -> list:
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
        self._expect_eq()
        expr = self._parse_expression()
        assignments.append((col, expr))
        while self._match(TokenType.COMMA):
            col = self._expect(TokenType.IDENT).value
            self._expect_eq()
            expr = self._parse_expression()
            assignments.append((col, expr))
        return assignments

    def _expect_eq(self) -> None:
        """Expect '=' operator token."""
        tok = self._peek()
        if tok.type == TokenType.OP and tok.value == '=':
            self._advance()
            return
        raise ParserError(
            f"Expected '=', got '{tok.text}'", tok.line, tok.column
        )

    def _parse_expression_list(self) -> list:
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
        if self._peek().type == TokenType.IDENT and self._peek().value.upper() == 'IS':
            self._advance()
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
        while True:
            if self._peek().type == TokenType.OP and self._peek().value == '/':
                op = self._advance().value
                right = self._parse_unary()
                left = BinaryOp(op, left, right)
            elif self._peek().type == TokenType.STAR:
                self._advance()
                right = self._parse_unary()
                left = BinaryOp('*', left, right)
            else:
                break
        return left

    def _parse_unary(self) -> Expression:
        if self._peek().type == TokenType.OP and self._peek().value == '-':
            self._advance()
            operand = self._parse_primary()
            return UnaryOp('-', operand)
        return self._parse_primary()

    def _parse_primary(self) -> Expression:
        tok = self._peek()

        if tok.type in (TokenType.INT_LIT, TokenType.FLOAT_LIT, TokenType.STR_LIT):
            self._advance()
            return Literal(tok.value)

        if tok.type == TokenType.BOOL_LIT:
            self._advance()
            return Literal(tok.value)

        if tok.type == TokenType.NULL:
            self._advance()
            return Literal(None)

        if tok.type == TokenType.IDENT and tok.value.upper() in ('COUNT', 'SUM', 'AVG'):
            return self._parse_aggregate()

        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

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
        return self._tokens[-1]

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
