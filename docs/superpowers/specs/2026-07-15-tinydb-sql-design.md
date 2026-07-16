---
comet_change: tinydb-sql
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-16-tinydb-sql
status: final
---

# tinydb-sql 技术设计文档

> 创建日期: 2026-07-15
> 对应 Change: tinydb-sql
> 上游 proposal: openspec/changes/tinydb-sql/proposal.md
> 上游 specs: openspec/changes/tinydb-sql/specs/

---

## 1. Context

### 1.1 项目背景

tinydb-sql 是 tinydb 数据库的 SQL 引擎层，负责将 SQL 字符串解析为可执行的查询计划，通过存储引擎操作数据。它是连接用户接口（SQL）与底层存储（tinydb-storage）的中间层。

### 1.2 依赖关系

```
                     ┌─────────────────────────────────┐
                     │     Database.execute(sql)       │
                     └───────────────┬─────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────┐
                     │       SQL Engine            │
                                                             │
  ┌────────┐  ┌────────┐  ┌─────────┐  ┌──────────────────┐
  │ Lexer  │→ │ Parser │→ │ Planner │→ │   Executor       │
  │        │  │        │  │         │  │ (Volcano Model)  │
  └────────┘  └────────┘  └─────────┘  └────────┬─────────┘
                                                │
┌───────────────────────────────────────────────┴─────────────┐
                     │       Storage Engine        │
                                                             │
  ┌──────────┐  ┌─────────┐  ┌──────────────┐  ┌─────────┐
  │ Catalog  │  │  Table  │  │  BufferPool  │  │  File   │
  └──────────┘  └─────────┘  └──────────────┘  └─────────┘
└─────────────────────────────────────────────────────────────┘
```

### 1.3 设计原则

- **教学优先**: 每个处理阶段独立模块化，清晰的数据结构流转
- **零外部依赖**: 仅使用 Python 3.10+ 标准库（除了已有的 tinydb 存储模块）
- **经典模型**: 复用数据库教科书中经过验证的设计（递归下降解析、火山模型执行）

---

## 2. Architecture

### 2.1 模块总览

```
SQL String
    │
    ▼
┌─────────┐    tokens     ┌─────────┐    AST      ┌─────────┐
│  Lexer  │──────────────→│ Parser  │────────────→│ Planner │
└─────────┘               └─────────┘             └────┬────┘
                                                       │
                                                operator tree
                                                       │
                                                       ▼
┌──────────────┐    rows     ┌─────────────────────────────────┐
│ QueryResult  │←────────────│           Executor              │
└──────────────┘             │  Limit → Sort → Agg → Proj →   │
                             │  Filter → Scan(Table.scan())    │
                             └─────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| Lexer | `sql/lexer.py` | 词法分析：SQL 字符串 → Token 列表 |
| Parser | `sql/parser.py` | 语法分析：Token 列表 → AST 节点 |
| Expressions | `sql/expressions.py` | 表达式树定义与 `evaluate(row)` 求值 |
| Planner | `sql/planner.py` | 查询计划：AST → 物理算子树 |
| Executor | `sql/executor.py` | 火山模型算子实现与迭代执行 |
| Result | `sql/result.py` | QueryResult 返回对象 |
| Errors | `sql/errors.py` | SQL 异常体系 |
| Database | `sql/database.py` | `Database.execute()` 入口，组装各模块 |

### 2.3 数据流

```
1. Database.execute(sql)
2.   → Lexer.tokenize(sql) → Token[]
3.   → Parser.parse(tokens) → Statement (AST)
4.   → Planner.plan(statement) → Operator (root of tree)
5.   → Executor.execute(operator) → Iterator[dict]
6.   → 收集结果 → QueryResult
```

---

## 3. Lexer Design

### 3.1 Token 类型

```python
class TokenType(Enum):
    # 关键字
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
    INTEGER = "INTEGER"      # 数据类型
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    ASC = "ASC"
    DESC = "DESC"
    GROUP = "GROUP"
    AS = "AS"
    
    # 字面量
    INT_LIT = "INT_LIT"
    FLOAT_LIT = "FLOAT_LIT"
    STR_LIT = "STR_LIT"
    BOOL_LIT = "BOOL_LIT"
    IDENT = "IDENT"          # 标识符（表名/列名）
    
    # 运算符
    OP = "OP"                # =, !=, <>, <, >, <=, >=, +, -, *, /
    
    # 分隔符
    COMMA = "COMMA"          # ,
    LPAREN = "LPAREN"        # (
    RPAREN = "RPAREN"        # )
    SEMICOLON = "SEMICOLON"  # ;
    STAR = "STAR"            # *
    
    EOF = "EOF"
```

### 3.2 Token 数据结构

```python
@dataclass
class Token:
    type: TokenType
    value: object           # 字面量的实际值，关键字为字符串
    line: int               # 行号（用于错误报告）
    column: int             # 列号
    offset: int             # 字符偏移量
    text: str               # 原始文本（用于错误报告）
```

### 3.3 关键字识别

使用字典在 IDENT 之后检查是否为保留字：

```python
_KEYWORDS: dict[str, TokenType] = {
    "SELECT": TokenType.SELECT,
    "FROM": TokenType.FROM,
    # ... 所有关键字
}

def _is_keyword(text: str) -> TokenType | None:
    return _KEYWORDS.get(text.upper())
```

### 3.4 字面量解析

| 类型 | 规则 | 示例 |
|------|------|------|
| 整数 | 连续数字，可选负号 | `42`, `-7` |
| 浮点数 | 数字+`.`+数字 | `3.14` |
| 字符串 | 单引号包裹 | `'hello'` |
| 布尔值 | TRUE/FALSE 关键字 | `TRUE`, `FALSE` |

### 3.5 扫描算法

```python
class Lexer:
    def tokenize(self, sql: str) -> list[Token]:
        tokens = []
        self._pos = 0
        self._line = 1
        self._col = 1
        
        while self._pos < len(sql):
            self._skip_whitespace()
            if self._pos >= len(sql):
                break
            
            ch = sql[self._pos]
            
            # 单字符运算符/分隔符
            if ch == ',': tokens.append(self._make_token(TokenType.COMMA, ','))
            elif ch == '(': tokens.append(self._make_token(TokenType.LPAREN, '('))
            elif ch == ')': tokens.append(self._make_token(TokenType.RPAREN, ')'))
            elif ch == ';': tokens.append(self._make_token(TokenType.SEMICOLON, ';'))
            elif ch == '*': tokens.append(self._make_token(TokenType.STAR, '*'))
            elif ch in '+-': tokens.append(self._make_op(ch))
            elif ch == '!': tokens.append(self._scan_not_equal())
            
            # 多字符运算符
            elif ch == '=': tokens.append(self._make_op('='))
            elif ch == '<': tokens.append(self._scan_lt())   # <, <=, <>
            elif ch == '>': tokens.append(self._scan_gt())   # >=
            
            # 字面量
            elif ch == "'": tokens.append(self._scan_string())
            elif ch.isdigit(): tokens.append(self._scan_number())
            elif ch.isalpha() or ch == '_': tokens.append(self._scan_identifier())
            
            else:
                raise LexerError(f"Unexpected character '{ch}'", self._line, self._col)
        
        tokens.append(Token(TokenType.EOF, None, self._line, self._col, self._pos, ""))
        return tokens
```

---

## 4. Parser Design

### 4.1 AST 节点类型

```python
# 语句节点
@dataclass
class SelectStatement:
    columns: list[Expression]      # 列表达式列表
    table: str                     # 表名
    where: Expression | None = None
    order_by: list[tuple[Expression, str]] | None = None  # [(expr, ASC|DESC)]
    limit: int | None = None
    offset: int | None = None
    group_by: list[Expression] | None = None

@dataclass
class InsertStatement:
    table: str
    columns: list[str] | None      # None 表示不指定列
    values: list[list[Expression]] # 支持多行 VALUES

@dataclass
class UpdateStatement:
    table: str
    assignments: list[tuple[str, Expression]]  # [(列名, 表达式)]
    where: Expression | None = None

@dataclass
class DeleteStatement:
    table: str
    where: Expression | None = None

@dataclass
class CreateTableStatement:
    table: str
    columns: list[ColumnDef]

@dataclass
class DropTableStatement:
    table: str

# 语句联合类型
Statement = SelectStatement | InsertStatement | UpdateStatement | DeleteStatement | CreateTableStatement | DropTableStatement
```

### 4.2 表达式节点

```python
class Expression:
    """表达式基类"""
    def evaluate(self, row: dict) -> object:
        raise NotImplementedError

@dataclass
class ColumnRef(Expression):
    name: str
    table: str | None = None  # 可选的表名前缀（未来 JOIN 用）
    
    def evaluate(self, row: dict) -> object:
        if self.table and self.table in row:
            return row[self.table].get(self.name)
        return row.get(self.name)

@dataclass
class Literal(Expression):
    value: object
    data_type: DataType | None = None
    
    def evaluate(self, row: dict) -> object:
        return self.value

@dataclass
class BinaryOp(Expression):
    op: str          # '+', '-', '*', '/', '=', '!=', '<', '>', '<=', '>=', 'AND', 'OR'
    left: Expression
    right: Expression
    
    def evaluate(self, row: dict) -> object:
        left_val = self.left.evaluate(row)
        right_val = self.right.evaluate(row)
        
        if self.op == 'AND': return _to_bool(left_val) and _to_bool(right_val)
        if self.op == 'OR': return _to_bool(left_val) or _to_bool(right_val)
        if self.op == '=': return _compare_eq(left_val, right_val)
        if self.op == '!=' or self.op == '<>': return not _compare_eq(left_val, right_val)
        if self.op == '<': return _compare_lt(left_val, right_val)
        if self.op == '>': return _compare_gt(left_val, right_val)
        if self.op == '<=': return _compare_le(left_val, right_val)
        if self.op == '>=': return _compare_ge(left_val, right_val)
        if self.op == '+': return left_val + right_val
        if self.op == '-': return left_val - right_val
        if self.op == '*': return left_val * right_val
        if self.op == '/':
            if right_val == 0:
                raise ExecutionError("Division by zero")
            return left_val / right_val
        
        raise ExecutionError(f"Unknown operator: {self.op}")

@dataclass
class UnaryOp(Expression):
    op: str          # 'NOT', '-'
    operand: Expression
    
    def evaluate(self, row: dict) -> object:
        val = self.operand.evaluate(row)
        if self.op == 'NOT': return not _to_bool(val)
        if self.op == '-': return -val
        raise ExecutionError(f"Unknown unary operator: {self.op}")

@dataclass
class AggregateExpr(Expression):
    func: str        # 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'
    arg: Expression
    distinct: bool = False
    
    def evaluate(self, row: dict) -> object:
        # Aggregate 在表达式树中不代表最终值，由 AggregateOperator 处理
        # 这里仅用于 AST 结构完整性
        raise NotImplementedError("AggregateExpr requires AggregateOperator")
```

### 4.3 递归下降解析方法

```python
class Parser:
    def parse(self, tokens: list[Token]) -> Statement:
        stmt = self._parse_statement()
        self._expect(TokenType.EOF)
        return stmt
    
    def _parse_statement(self) -> Statement:
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
            raise ParserError(f"Unexpected token: {tok.text}", tok.line, tok.column)
    
    def _parse_select(self) -> SelectStatement:
        self._expect(TokenType.SELECT)
        columns = self._parse_column_list()
        self._expect(TokenType.FROM)
        table = self._expect(TokenType.IDENT).value
        where = self._parse_where() if self._match(TokenType.WHERE) else None
        group_by = self._parse_group_by() if self._match2(TokenType.GROUP, TokenType.BY) else None
        order_by = self._parse_order_by() if self._match2(TokenType.ORDER, TokenType.BY) else None
        limit = self._parse_limit() if self._match(TokenType.LIMIT) else None
        offset = self._parse_offset() if self._match(TokenType.OFFSET) else None
        return SelectStatement(columns, table, where, order_by, limit, offset, group_by)
    
    def _parse_insert(self) -> InsertStatement:
        self._expect(TokenType.INSERT)
        self._expect(TokenType.INTO)
        table = self._expect(TokenType.IDENT).value
        columns = None
        if self._match(TokenType.LPAREN):
            columns = [self._expect(TokenType.IDENT).value for _ in self._parse_list()]
            self._expect(TokenType.RPAREN)
        self._expect(TokenType.VALUES)
        values = self._parse_value_lists()
        return InsertStatement(table, columns, values)
    
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
    
    def _parse_drop(self) -> DropTableStatement:
        self._expect(TokenType.DROP)
        self._expect(TokenType.TABLE)
        table = self._expect(TokenType.IDENT).value
        return DropTableStatement(table)
```

### 4.4 表达式优先级处理

使用分层递归下降，每个优先级一个方法：

```python
def _parse_expression(self) -> Expression:
    """OR 优先级最低"""
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
    return self._parse_comparison()

def _parse_comparison(self) -> Expression:
    left = self._parse_additive()
    comp_ops = {
        TokenType.OP: None,  # =, !=, <>, <, >, <=, >=
    }
    while self._peek().type == TokenType.OP and self._peek().value in ('=', '!=', '<>', '<', '>', '<=', '>='):
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
    
    # 字面量
    if tok.type in (TokenType.INT_LIT, TokenType.FLOAT_LIT, TokenType.STR_LIT, TokenType.BOOL_LIT):
        self._advance()
        return Literal(tok.value)
    
    if tok.type == TokenType.NULL:
        self._advance()
        return Literal(None)
    
    # 聚合函数
    if tok.type == TokenType.IDENT and tok.value.upper() in ('COUNT', 'SUM', 'AVG', 'MIN', 'MAX'):
        return self._parse_aggregate()
    
    # 括号表达式
    if tok.type == TokenType.LPAREN:
        self._advance()
        expr = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return expr
    
    # 列引用
    if tok.type == TokenType.IDENT:
        self._advance()
        return ColumnRef(tok.value)
    
    raise ParserError(f"Unexpected token in expression: {tok.text}", tok.line, tok.column)
```

---

## 5. Expression Evaluation

### 5.1 求值模型

每个表达式节点实现 `evaluate(row)` 方法，`row` 是一个 `dict[str, object]`（列名 → 值）。

### 5.2 比较语义

| 情况 | 行为 |
|------|------|
| 任意操作数为 NULL | 返回 NULL（视为 False）|
| 同类型比较 | 直接比较 |
| INTEGER vs FLOAT | 隐式提升为 FLOAT |
| BOOLEAN vs 数值 | 不隐式转换，返回类型错误 |

### 5.3 辅助函数

```python
def _to_bool(val: object) -> bool:
    """将值转为布尔。NULL → False。"""
    if val is None:
        return False
    return bool(val)

def _compare_eq(left: object, right: object) -> bool:
    if left is None or right is None:
        return False
    return left == right

def _compare_lt(left: object, right: object) -> bool:
    if left is None or right is None:
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left < right
    if isinstance(left, str) and isinstance(right, str):
        return left < right
    raise ExecutionError(f"Cannot compare {type(left)} with {type(right)}")
```

### 5.4 NULL 处理

NULL 遵循 SQL 三值逻辑的简化版：
- `NULL = anything` → False（不是 NULL）
- `NULL AND x` → False（因为 NULL 视为 False）
- `NULL OR x` → 取决于 x
- `NOT NULL` → True（因为 NOT False）

> 注：完整 SQL 三值逻辑用 `IS NULL` / `IS NOT NULL` 处理。本 change 暂不实现 `IS NULL`，后续可扩展。

---

## 6. Query Planner

### 6.1 算子树节点

```python
class Operator:
    """算子基类（火山模型）"""
    def __iter__(self):
        return self
    
    def __next__(self) -> dict:
        raise NotImplementedError

class ScanOperator(Operator):
    def __init__(self, table: Table, buffer_pool: BufferPool):
        self.table = table
        self.buffer_pool = buffer_pool
    
    def __iter__(self):
        for row_id, row_values in self.table.scan(self.buffer_pool):
            yield dict(zip([col.name for col in self.table.columns], row_values))

class FilterOperator(Operator):
    def __init__(self, source: Operator, condition: Expression):
        self.source = source
        self.condition = condition
    
    def __iter__(self):
        for row in self.source:
            val = self.condition.evaluate(row)
            if _to_bool(val):
                yield row

class ProjectOperator(Operator):
    def __init__(self, source: Operator, columns: list[tuple[str, Expression]]):
        """columns: [(alias, expression), ...]"""
        self.source = source
        self.columns = columns
    
    def __iter__(self):
        for row in self.source:
            yield {alias: expr.evaluate(row) for alias, expr in self.columns}

class AggregateOperator(Operator):
    def __init__(self, source: Operator, 
                 group_keys: list[Expression],
                 aggregations: list[tuple[str, str, Expression]]):
        """aggregations: [(alias, func, arg_expr), ...]"""
        self.source = source
        self.group_keys = group_keys
        self.aggregations = aggregations
    
    def __iter__(self):
        # 哈希聚合
        groups: dict[tuple, dict] = {}
        
        for row in self.source:
            key = tuple(k.evaluate(row) for k in self.group_keys)
            if key not in groups:
                groups[key] = self._init_agg_state()
            
            state = groups[key]
            for i, (alias, func, arg_expr) in enumerate(self.aggregations):
                val = arg_expr.evaluate(row)
                state[i] = self._accumulate(func, state[i], val)
        
        for key, state in groups.items():
            result = {}
            if self.group_keys:
                for i, k in enumerate(self.group_keys):
                    result[f"_group_{i}"] = key[i]
                # 用 group by 列名作为 key
                for i, k_exp in enumerate(self.group_keys):
                    if isinstance(k_exp, ColumnRef):
                        result[k_exp.name] = key[i]
            
            for i, (alias, func, _) in enumerate(self.aggregations):
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
            # 存储 (sum, count) 元组
            if state is None:
                state = (0, 0)
            if val is not None:
                return (state[0] + val, state[1] + 1)
            return state
        elif func == 'MIN':
            if val is None:
                return state
            if state is None or val < state:
                return val
            return state
        elif func == 'MAX':
            if val is None:
                return state
            if state is None or val > state:
                return val
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
    def __init__(self, source: Operator, 
                 order_keys: list[tuple[Expression, str]]):
        """order_keys: [(expr, ASC|DESC), ...]"""
        self.source = source
        self.order_keys = order_keys
    
    def __iter__(self):
        rows = list(self.source)
        for expr, direction in reversed(self.order_keys):
            rows.sort(
                key=lambda r, e=expr: (e.evaluate(r) is None, e.evaluate(r)),
                reverse=(direction == 'DESC')
            )
        yield from rows

class LimitOperator(Operator):
    def __init__(self, source: Operator, limit: int | None, offset: int):
        self.source = source
        self.limit = limit
        self.offset = offset
    
    def __iter__(self):
        iterator = iter(self.source)
        # Skip offset
        for _ in range(self.offset):
            try:
                next(iterator)
            except StopIteration:
                return
        
        # Yield limit rows
        count = 0
        for row in iterator:
            if self.limit is not None and count >= self.limit:
                return
            yield row
            count += 1
```

### 6.2 Planner 实现

```python
class Planner:
    def __init__(self, catalog: Catalog, buffer_pool: BufferPool):
        self.catalog = catalog
        self.buffer_pool = buffer_pool
    
    def plan(self, stmt: Statement) -> Operator:
        if isinstance(stmt, SelectStatement):
            return self._plan_select(stmt)
        elif isinstance(stmt, CreateTableStatement):
            return self._plan_create_table(stmt)
        elif isinstance(stmt, DropTableStatement):
            return self._plan_drop_table(stmt)
        else:
            # INSERT/UPDATE/DELETE 是直接操作用 DML executor
            return DmlOperator(stmt, self.catalog, self.buffer_pool)
    
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
                    aggregations.append((col.func.lower(), col.func, col.arg))
                elif isinstance(col, ColumnRef) and not has_agg:
                    # 非聚合列必须有 GROUP BY
                    aggregations.append((col.name, 'VALUE', col))
                else:
                    aggregations.append((col.name, 'VALUE', col))
            op = AggregateOperator(op, group_keys, aggregations)
        else:
            # Project
            projections = []
            for col in stmt.columns:
                if isinstance(col, StarExpr):
                    projections.append(('*', col))
                else:
                    alias = col.name if isinstance(col, ColumnRef) else col.name
                    projections.append((alias, col))
            op = ProjectOperator(op, projections)
        
        # 4. Sort (ORDER BY)
        if stmt.order_by:
            op = SortOperator(op, stmt.order_by)
        
        # 5. Limit + Offset
        if stmt.limit is not None or stmt.offset:
            op = LimitOperator(op, stmt.limit, stmt.offset or 0)
        
        return op
```

---

## 7. Result

### 7.1 QueryResult

```python
@dataclass
class QueryResult:
    rows: list[dict]           # 行数据，每行是 {列名: 值} 的字典
    columns: list[str]         # 列名列表（保持 SELECT 顺序）
    row_count: int             # 返回行数（SELECT）或影响行数（DML）
    
    def __iter__(self):
        return iter(self.rows)
    
    def __len__(self):
        return self.row_count
    
    def __repr__(self):
        if not self.rows:
            return f"QueryResult(row_count={self.row_count})"
        return f"QueryResult(columns={self.columns}, rows={len(self.rows)})"
```

### 7.2 返回值约定

| 语句类型 | rows | columns | row_count |
|----------|------|---------|-----------|
| SELECT | 查询结果 | SELECT 列名 | 返回行数 |
| INSERT | [] | [] | 1（成功）或 0 |
| UPDATE | [] | [] | 更新行数 |
| DELETE | [] | [] | 删除行数 |
| CREATE TABLE | [] | [] | 0 |
| DROP TABLE | [] | [] | 0 |

---

## 8. DDL Execution

### 8.1 CREATE TABLE

```python
class CreateTableExecutor:
    def execute(self, stmt: CreateTableStatement) -> QueryResult:
        # 将 AST ColumnDef 转为存储引擎 ColumnDef
        columns = []
        pk = ""
        for col_def in stmt.columns:
            data_type = DataType(col_def['data_type'].upper())
            col = ColumnDef(
                name=col_def['name'],
                data_type=data_type,
                nullable=not col_def.get('not_null', False),
                primary_key=col_def.get('primary_key', False),
                unique=col_def.get('unique', False),
            )
            columns.append(col)
            if col.primary_key:
                pk = col.name
        
        self.catalog.create_table(stmt.table, columns, pk)
        return QueryResult([], [], 0)
```

### 8.2 DROP TABLE

```python
class DropTableExecutor:
    def execute(self, stmt: DropTableStatement) -> QueryResult:
        self.catalog.drop_table(stmt.table)
        return QueryResult([], [], 0)
```

---

## 9. DML Execution

### 9.1 INSERT

```python
class InsertExecutor:
    def execute(self, stmt: InsertStatement) -> QueryResult:
        table = self.catalog.get_table(stmt.table)
        
        for value_exprs in stmt.values:
            # 求值表达式
            row_values = [expr.evaluate({}) for expr in value_exprs]
            
            # 如果指定了列，按列顺序组装
            if stmt.columns:
                row_dict = dict(zip(stmt.columns, row_values))
                # 按表结构顺序排列
                ordered_row = [row_dict.get(col.name) for col in table.columns]
            else:
                ordered_row = row_values
            
            # 约束检查
            self._check_constraints(table, ordered_row)
            
            # 执行插入
            table.insert(self.buffer_pool, ordered_row)
        
        return QueryResult([], [], len(stmt.values))
    
    def _check_constraints(self, table: Table, row: list) -> None:
        """NOT NULL 预检查 + PRIMARY KEY/UNIQUE 扫描检查"""
        for i, (val, col) in enumerate(zip(row, table.columns)):
            # NOT NULL
            if not col.nullable and val is None:
                raise ConstraintError(
                    f"NOT NULL constraint violated on column '{col.name}'"
                )
            
            # PRIMARY KEY / UNIQUE — 扫描检查
            if col.primary_key or col.unique:
                for _, existing_row in table.scan(self.buffer_pool):
                    if existing_row[i] == val:
                        raise ConstraintError(
                            f"{'PRIMARY KEY' if col.primary_key else 'UNIQUE'} "
                            f"constraint violated on column '{col.name}': "
                            f"value {val!r} already exists"
                        )
```

### 9.2 SELECT

```python
class SelectExecutor:
    def execute(self, stmt: SelectStatement) -> QueryResult:
        operator = self.planner.plan(stmt)
        rows = list(operator)
        
        # 提取列名
        columns = []
        for col in stmt.columns:
            if isinstance(col, StarExpr):
                # 展开为表的所有列
                table = self.catalog.get_table(stmt.table)
                columns.extend(c.name for c in table.columns)
            elif isinstance(col, ColumnRef):
                columns.append(col.name)
            elif isinstance(col, AggregateExpr):
                columns.append(col.func.lower())
            else:
                columns.append(col.name)
        
        return QueryResult(rows, columns, len(rows))
```

### 9.3 UPDATE

```python
class UpdateExecutor:
    def execute(self, stmt: UpdateStatement) -> QueryResult:
        table = self.catalog.get_table(stmt.table)
        
        # 扫描匹配行
        scan_op = ScanOperator(table, self.buffer_pool)
        if stmt.where:
            scan_op = FilterOperator(scan_op, stmt.where)
        
        updated = 0
        for row in scan_op:
            # 找到对应的 RowId（需要 ScanOperator 也返回 RowId）
            # 简化：重新扫描定位
            for row_id, row_values in table.scan(self.buffer_pool):
                row_dict = dict(zip([c.name for c in table.columns], row_values))
                if stmt.where is None or _to_bool(stmt.where.evaluate(row_dict)):
                    # 应用 SET
                    new_row = row_values.copy()
                    for col_name, expr in stmt.assignments:
                        col_idx = next(
                            i for i, c in enumerate(table.columns) if c.name == col_name
                        )
                        new_row[col_idx] = expr.evaluate(row_dict)
                    
                    # 约束检查
                    self._check_constraints(table, new_row)
                    
                    # 执行更新
                    table.update(self.buffer_pool, row_id, new_row)
                    updated += 1
        
        return QueryResult([], [], updated)
```

### 9.4 DELETE

```python
class DeleteExecutor:
    def execute(self, stmt: DeleteStatement) -> QueryResult:
        table = self.catalog.get_table(stmt.table)
        
        # 收集要删除的 RowId
        to_delete = []
        for row_id, row_values in table.scan(self.buffer_pool):
            row_dict = dict(zip([c.name for c in table.columns], row_values))
            if stmt.where is None or _to_bool(stmt.where.evaluate(row_dict)):
                to_delete.append(row_id)
        
        # 执行删除
        for row_id in to_delete:
            table.delete(self.buffer_pool, row_id)
        
        return QueryResult([], [], len(to_delete))
```

---

## 10. Constraint Enforcement

### 10.1 约束检查时机

| 约束 | 检查时机 | 实现方式 |
|------|----------|----------|
| NOT NULL | INSERT/UPDATE 前 | 直接检查值是否为 None |
| PRIMARY KEY | INSERT/UPDATE 前 | 全表扫描检查唯一性 |
| UNIQUE | INSERT/UPDATE 前 | 全表扫描检查唯一性 |
| 类型检查 | INSERT/UPDATE 时 | 复用 `types.convert_value()` |

### 10.2 约束检查实现

约束检查嵌入 DML 执行路径，在调用 `Table.insert()` / `Table.update()` 之前执行。

```python
class ConstraintChecker:
    def __init__(self, table: Table, buffer_pool: BufferPool):
        self.table = table
        self.buffer_pool = buffer_pool
    
    def check_insert(self, row: list) -> None:
        """插入前检查所有约束"""
        for i, (val, col) in enumerate(zip(row, self.table.columns)):
            # NOT NULL
            if not col.nullable and val is None:
                raise ConstraintError(
                    f"NOT NULL constraint violated on column '{col.name}'"
                )
            
            # PRIMARY KEY / UNIQUE
            if col.primary_key or col.unique:
                self._check_unique(i, val)
    
    def check_update(self, row_id: RowId, new_row: list) -> None:
        """更新前检查（排除当前行自身）"""
        for i, (val, col) in enumerate(zip(new_row, self.table.columns)):
            if not col.nullable and val is None:
                raise ConstraintError(
                    f"NOT NULL constraint violated on column '{col.name}'"
                )
            
            if col.primary_key or col.unique:
                for existing_id, existing_row in self.table.scan(self.buffer_pool):
                    if existing_id == row_id:
                        continue  # 跳过自身
                    if existing_row[i] == val:
                        raise ConstraintError(
                            f"{'PRIMARY KEY' if col.primary_key else 'UNIQUE'} "
                            f"constraint violated on column '{col.name}'"
                        )
    
    def _check_unique(self, col_idx: int, value: object) -> None:
        for _, row in self.table.scan(self.buffer_pool):
            if row[col_idx] == value:
                col = self.table.columns[col_idx]
                raise ConstraintError(
                    f"{'PRIMARY KEY' if col.primary_key else 'UNIQUE'} "
                    f"constraint violated on column '{col.name}': "
                    f"value {value!r} already exists"
                )
```

---

## 11. Error Handling

### 11.1 异常体系

```python
class SQLError(Exception):
    """SQL 引擎所有异常的基类"""
    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.line = line
        self.column = column
        super().__init__(f"[{line}:{column}] {message}" if line else message)

class LexerError(SQLError):
    """词法分析错误"""
    pass

class ParserError(SQLError):
    """语法分析错误"""
    pass

class PlanningError(SQLError):
    """查询计划错误"""
    pass

class ExecutionError(SQLError):
    """执行时错误"""
    pass

class ConstraintError(SQLError):
    """约束违反错误"""
    pass
```

### 11.2 错误报告策略

- **Fail-fast**: 遇到第一个错误立即停止，不尝试恢复
- **位置信息**: 所有错误包含行号、列号、字符偏移
- **上下文**: 错误消息包含出错的 token 文本或 SQL 片段
- **存储异常透传**: `TableExistsError`、`TableNotFoundError`、`SchemaMismatchError` 等存储引擎异常直接透传给调用者

---

## 12. Database Entry Point

### 12.1 Database 类

```python
class Database:
    def __init__(self, path: str):
        self.file_manager = FileManager()
        self.file_manager.open(path)
        self.buffer_pool = BufferPool(capacity=100)
        self.catalog = Catalog(self.file_manager, self.buffer_pool)
        self.catalog.load()
        self._planner = Planner(self.catalog, self.buffer_pool)
    
    def execute(self, sql: str) -> QueryResult:
        """执行 SQL 语句并返回结果"""
        # 1. Lexer
        tokens = Lexer().tokenize(sql)
        
        # 2. Parser
        stmt = Parser().parse(tokens)
        
        # 3. Plan & Execute
        if isinstance(stmt, SelectStatement):
            return SelectExecutor(self._planner).execute(stmt)
        elif isinstance(stmt, InsertStatement):
            return InsertExecutor(self.catalog, self.buffer_pool).execute(stmt)
        elif isinstance(stmt, UpdateStatement):
            return UpdateExecutor(self.catalog, self.buffer_pool).execute(stmt)
        elif isinstance(stmt, DeleteStatement):
            return DeleteExecutor(self.catalog, self.buffer_pool).execute(stmt)
        elif isinstance(stmt, CreateTableStatement):
            return CreateTableExecutor(self.catalog).execute(stmt)
        elif isinstance(stmt, DropTableStatement):
            return DropTableExecutor(self.catalog).execute(stmt)
        else:
            raise PlanningError(f"Unknown statement type: {type(stmt)}")
    
    def close(self):
        self.catalog.save()
        self.file_manager.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
```

---

## 13. Integration with Storage Engine

### 13.1 依赖接口

| 存储引擎 API | SQL 引擎使用方式 |
|-------------|-----------------|
| `Catalog.create_table(name, columns, pk)` | CREATE TABLE |
| `Catalog.drop_table(name)` | DROP TABLE |
| `Catalog.get_table(name) → Table` | 所有 DML 获取表对象 |
| `Catalog.list_tables()` | 元数据查询（未来） |
| `Table.scan(buffer_pool)` | ScanOperator 全表扫描 |
| `Table.insert(buffer_pool, row)` | INSERT |
| `Table.update(buffer_pool, row_id, row)` | UPDATE |
| `Table.delete(buffer_pool, row_id)` | DELETE |
| `Table.get(buffer_pool, row_id)` | 约束检查（可选） |

### 13.2 数据格式

- SQL 引擎内部使用 `dict[str, object]` 表示行（列名 → 值）
- 存储引擎使用 `list[object]` 表示行（按列顺序）
- 转换发生在 ScanOperator（list → dict）和 DML executor（dict → list）

---

## 14. Testing Strategy

### 14.1 单元测试

| 模块 | 测试文件 | 覆盖内容 |
|------|----------|----------|
| Lexer | `test_lexer.py` | 关键字、字面量、运算符、标识符、空白跳过、错误字符 |
| Parser | `test_parser.py` | 各语句类型解析、表达式优先级、错误恢复 |
| Expressions | `test_expressions.py` | 算术/比较/逻辑运算、NULL 处理、类型转换 |
| Planner | `test_planner.py` | AST→算子树映射、聚合查询计划 |
| Executor | `test_executor.py` | 各算子独立功能、火山模型迭代 |
| Constraints | `test_constraints.py` | NOT NULL/PRIMARY KEY/UNIQUE 检查 |

### 14.2 集成测试

| 场景 | 验证 |
|------|------|
| CRUD 全流程 | CREATE → INSERT → SELECT → UPDATE → DELETE |
| 约束违反 | 重复主键、NOT NULL 违反、UNIQUE 违反 |
| 复杂查询 | WHERE + ORDER BY + LIMIT + GROUP BY |
| 多行插入 | INSERT INTO ... VALUES (...), (...), (...) |
| 空表查询 | SELECT 空表返回空结果 |
| NULL 处理 | NULL 比较语义 |

### 14.3 测试框架

- **pytest**: 主要测试框架
- **tmp_path**: 临时数据库文件
- **fixture**: 预置表结构和测试数据

---

## 15. Risks & Mitigations

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 全表扫描性能差 | 高 | 中 | 后续 change 引入 B-tree 索引 |
| UNIQUE 检查 O(n) | 高 | 中 | 索引 change 后使用索引 |
| 哈希聚合内存爆炸 | 低 | 高 | 教学场景数据集小，暂不处理 |
| SQL 语法覆盖不全 | 中 | 低 | 先支持最小语法集，后续扩展 |
| 表达式类型错误 | 中 | 中 | 运行时类型检查 + 清晰错误信息 |
| UPDATE 定位 RowId | 中 | 低 | 当前实现重新扫描定位，正确性优先 |

---

## 16. Open Questions

- [ ] `IS NULL` / `IS NOT NULL` 语法是否需要在本 change 实现？（当前 NULL 比较用 `=` 返回 False）
- [ ] `COUNT(*)` 是否需要特殊处理？（当前 COUNT 对表达式求值，`*` 需要特殊字面量）
- [ ] 多行 INSERT (`VALUES (...), (...), (...)`) 是否需要支持？（tasks.md 未明确）
- [ ] `MIN`/`MAX` 聚合函数是否需要支持？（executor spec 只提到 COUNT/SUM/AVG）
- [ ] 标识符是否需要支持引号包裹（如 `"table name"`）？

---

## 确认的扩展决策

### SQL 特性范围: 适度扩展

| 特性 | 状态 |
|------|------|
| IS NULL / IS NOT NULL | ✅ 支持 |
| COUNT(*) | ✅ 支持（* 作为特殊字面量） |
| 多行 VALUES (...),(...) | ✅ 支持 |
| MIN / MAX | ❌ 不在本 change scope |
| 引号标识符 | ❌ 不在本 change scope |
