# Design: 多表 JOIN 查询

## 1. 概述

本设计在 tinydb v0.1 单表查询引擎基础上扩展多表 JOIN 能力。整体架构遵循现有 Volcano 模型，新增的 JoinOperator 可嵌套在 Filter/Project 之下，保持执行器风格一致。

## 2. AST 扩展

### 2.1 新增节点

```python
@dataclass
class TableRef:
    """表引用（含可选别名）"""
    name: str
    alias: str | None = None


@dataclass
class JoinClause:
    """JOIN 子句"""
    join_type: str                              # INNER, LEFT, RIGHT, FULL, CROSS, NATURAL
    right_table: TableRef                       # 右表引用
    on_condition: Expression | None = None      # CROSS JOIN 为 None
    using_columns: list[str] | None = None     # NATURAL/USING 使用
```

### 2.2 修改 SelectStatement

```python
@dataclass
class SelectStatement:
    columns: list
    from_table: TableRef               # 原 table: str → TableRef
    joins: list[JoinClause] = field(default_factory=list)
    where: Expression | None = None
    order_by: list | None = None
    limit: int | None = None
    offset: int | None = None
    group_by: list | None = None
```

### 2.3 修改 ColumnRef

```python
@dataclass
class ColumnRef(Expression):
    name: str
    table: str | None = None    # 表别名限定，如 u.name → table="u"

    def evaluate(self, row: dict) -> object:
        return row.get(self.name)
```

## 3. Lexer 扩展

新增 TokenType 枚举值：

```python
# JOIN keywords
JOIN = "JOIN"
INNER = "INNER"
LEFT = "LEFT"
RIGHT = "RIGHT"
FULL = "FULL"
OUTER = "OUTER"
CROSS = "CROSS"
NATURAL = "NATURAL"
ON = "ON"
USING = "USING"
```

新增关键词映射：

```python
_KEYWORDS |= {
    "JOIN": TokenType.JOIN,
    "INNER": TokenType.INNER,
    "LEFT": TokenType.LEFT,
    "RIGHT": TokenType.RIGHT,
    "FULL": TokenType.FULL,
    "OUTER": TokenType.OUTER,
    "CROSS": TokenType.CROSS,
    "NATURAL": TokenType.NATURAL,
    "ON": TokenType.ON,
    "USING": TokenType.USING,
}
```

## 4. Parser 扩展

### 4.1 FROM 子句解析

```
FROM table_name [AS] alias
     { JOIN_CLAUSE }*

JOIN_CLAUSE := [INNER|LEFT [OUTER]|RIGHT [OUTER]|FULL [OUTER]|CROSS|NATURAL]
               JOIN table_ref
               { ON expression | USING (column_list) }
```

### 4.2 解析流程

1. 解析主表 `table_name [AS alias]` → `TableRef`
2. 循环检测 JOIN 关键字
3. 根据 JOIN 类型解析右表和条件：
   - `CROSS JOIN table_ref` (无 ON/USING)
   - `NATURAL JOIN table_ref` (无条件，后续 Planner 自动匹配列)
   - `[INNER|LEFT|RIGHT|FULL] JOIN table_ref ON expr`
   - `[INNER|LEFT|RIGHT|FULL] JOIN table_ref USING (cols)`
4. 解析 `table_ref` 时支持 `schema.table` 形式（lexer 已支持点号分隔的 IDENT）

### 4.3 列引用解析

解析 `u.name` 形式的限定列名时，将 IDENT + DOT + IDENT 序列识别为带表限定的 ColumnRef。

### 4.4 Parser 方法签名变更

```python
def _parse_select(self) -> SelectStatement:
    self._expect(TokenType.SELECT)
    columns = self._parse_select_columns()
    self._expect(TokenType.FROM)
    from_table = self._parse_table_ref()              # 新增
    joins = self._parse_join_clauses()                # 新增
    where = ...
    ...
    return SelectStatement(columns, from_table, joins, where, ...)

def _parse_table_ref(self) -> TableRef:               # 新增
    name = self._expect(TokenType.IDENT).value
    alias = None
    if self._match(TokenType.AS) or (self._check(TokenType.IDENT) and not self._is_join_keyword()):
        alias = self._expect(TokenType.IDENT).value
    return TableRef(name, alias)

def _parse_join_clauses(self) -> list[JoinClause]:    # 新增
    joins = []
    while self._is_join_keyword():
        joins.append(self._parse_join_clause())
    return joins
```

## 5. Planner 扩展

### 5.1 JoinPlanner

新增 `JoinPlanner` 类，负责将 JOIN AST 转换为 JoinOperator 树。

```python
class JoinPlanner:
    def __init__(self, catalog, buffer_pool):
        self.catalog = catalog
        self.buffer_pool = buffer_pool

    def plan_joins(self, from_table, joins, where) -> Operator:
        """生成 JOIN operator 树"""
        # 1. 构建左表 ScanOperator
        left = self._build_scan(from_table)

        # 2. 逐层构建 JOIN
        for join in joins:
            right = self._build_scan(join.right_table)
            algorithm = self._choose_algorithm(join, left, right)
            left = self._build_join_operator(algorithm, left, right, join)

        return left

    def _choose_algorithm(self, join, left, right) -> str:
        """基于规则选择算法"""
        if join.join_type == "CROSS":
            return "nested_loop"
        if self._is_natural_or_using(join) and self._is_large_table(right):
            return "hash"
        if self._has_index_on_join_key(join, right):
            return "index_nested_loop"
        if self._is_sorted_or_needs_sort(left, right, join):
            return "sort_merge"
        return "nested_loop"  # 默认
```

### 5.2 代价估算参数

| 参数 | 来源 |
|------|------|
| 表行数 | `catalog.get_stats(table).row_count` |
| 可用索引 | `catalog.get_indexes(table)` |
| 内存限制 | 默认 1MB（哈希表最大内存） |

### 5.3 阈值

- "大表" = 右表行数 > 1000 或右表数据量 > 内存限制 / 平均行大小
- 达到大表阈值时优先选择 Hash Join 或 Sort-Merge Join

### 5.4 Planner 集成

修改 `Planner._plan_select()`：

```python
def _plan_select(self, stmt: SelectStatement) -> Operator:
    join_planner = JoinPlanner(self.catalog, self.buffer_pool)
    op = join_planner.plan_joins(stmt.from_table, stmt.joins, stmt.where)

    if stmt.where:
        op = FilterOperator(op, stmt.where)

    # ... 后续 Project/Aggregate/Sort/Limit 不变
```

## 6. Executor 扩展

### 6.1 接口设计

所有 JoinOperator 遵循 Volcano 模型（`__iter__`/`__next__`），输入输出均为行字典流。

JOIN 结果的列命名规则：
- 若列有别名限定（`u.name`），输出列名为 `name`（去除限定）
- 同名列冲突时，通过表别名前缀区分（`u_name`, `o_name`）

### 6.2 NestedLoopJoinOperator

```python
class NestedLoopJoinOperator(Operator):
    """外循环遍历左表，内循环扫描右表，过滤 ON 条件"""

    def __init__(self, left: Operator, right: Operator,
                 join_type: str, on_condition: Expression | None,
                 right_table: TableRef):
        self.left = left
        self.right = right
        self.join_type = join_type
        self.on_condition = on_condition
        self.right_table = right_table

    def __iter__(self):
        for left_row in self.left:
            matched = False
            for right_row in self.right:
                combined = self._combine_rows(left_row, right_row)
                if self.on_condition is None or _to_bool(self.on_condition.evaluate(combined)):
                    matched = True
                    yield combined
            # LEFT/FULL JOIN: 左表行未匹配时输出 NULL 补行
            if not matched and self.join_type in ("LEFT", "FULL"):
                yield self._combine_with_nulls(left_row, None)
        # RIGHT/FULL JOIN: 处理右表未匹配行
        if self.join_type in ("RIGHT", "FULL"):
            self._yield_unmatched_right()
```

### 6.3 HashJoinOperator

```python
class HashJoinOperator(Operator):
    """构建阶段：扫描右表建哈希表；探测阶段：遍历左表查表"""

    def __init__(self, left: Operator, right: Operator,
                 join_type: str, on_condition: Expression):
        self.left = left
        self.right = right
        self.join_type = join_type
        self.on_condition = on_condition

    def __iter__(self):
        # 构建阶段：按连接键哈希分组右表
        hash_table: dict = {}
        for right_row in self.right:
            key = self._extract_key(right_row)
            hash_table.setdefault(key, []).append(right_row)

        # 探测阶段
        for left_row in self.left:
            key = self._extract_key(left_row)
            if key in hash_table:
                for right_row in hash_table[key]:
                    yield self._combine_rows(left_row, right_row)
```

限制：仅支持等值连接条件（`=` 运算符）。

### 6.4 SortMergeJoinOperator

```python
class SortMergeJoinOperator(Operator):
    """两表按连接键排序后归并"""

    def __init__(self, left: Operator, right: Operator,
                 join_type: str, on_condition: Expression):
        self.left = left
        self.right = right
        self.join_type = join_type
        self.on_condition = on_condition

    def __iter__(self):
        left_sorted = sorted(self.left, key=lambda r: self._extract_key(r))
        right_sorted = sorted(self.right, key=lambda r: self._extract_key(r))

        i, j = 0, 0
        while i < len(left_sorted) and j < len(right_sorted):
            l_key = self._extract_key(left_sorted[i])
            r_key = self._extract_key(right_sorted[j])
            if l_key == r_key:
                # 处理相等情况（可能有多个匹配）
                yield from self._merge_equals(left_sorted, right_sorted, i, j)
                ...
            elif l_key < r_key:
                i += 1
            else:
                j += 1
```

## 7. 列引用处理

### 7.1 解析阶段

Parser 将 `u.name` 解析为 `ColumnRef(name="name", table="u")`。

### 7.2 计划阶段

JoinPlanner 在生成计划时负责列名解析：
1. 建立 `{alias → actual_table_name}` 映射
2. 建立 `{table_name → {column_name → index}}` 映射
3. 解析 ON 条件中的列引用，确定连接键对应的物理列位置

### 7.3 执行阶段

JoinOperator 输出行时，列名冲突处理规则：
- 如果两个表有同名列（除连接键外），输出时使用 `{alias}_{colname}` 格式
- 连接键列只保留一份（INNER JOIN）或两份保留原名（OUTER JOIN）

## 8. NATURAL JOIN 实现

NATURAL JOIN 在 Parser 阶段无条件生成 JoinClause，Planner 阶段：
1. 从 catalog 获取两表的列信息
2. 自动匹配同名列作为连接键
3. 生成等值条件（多个同名列则 AND 连接）
4. 选择 Hash Join 或 Nested Loop Join 执行

## 9. 测试策略

### 9.1 单元测试

- 每种 JOIN 类型 × 每种算法（约 15 组合）
- NULL 值处理（NULL ≠ NULL，不匹配）
- 空表 JOIN
- 自连接（SELF JOIN）
- 多表 3+ JOIN 链

### 9.2 正确性测试

- 与 SQLite 结果对比（构造相同数据集，比较输出）

### 9.3 边界测试

- 笛卡尔积极大数据量
- 连接键全部相同
- 连接键全部不同
- 列名冲突

### 9.4 性能冒烟测试

- 大数据集（>10000 行）验证 Hash Join 优于 Nested Loop

## 10. 兼容性

- 单表查询不经过 JOIN 路径，行为不变
- `SelectStatement` 的 `from_table` 类型变更（str → TableRef），需同步修改所有引用处
- 无新外部依赖
