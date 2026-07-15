# Comet Design Handoff

- Change: tinydb-sql
- Phase: design
- Mode: compact
- Context hash: a1552d94405082679013efc38f4081284f07a86202cc33df807d90c6be7f0b34

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/tinydb-sql/proposal.md

- Source: openspec/changes/tinydb-sql/proposal.md
- Lines: 1-37
- SHA256: 506d7cfa0f1c2a318dcb39328d05a21c1019b50734e83bcf965470f4815b1862

```md
## Why

tinydb 需要一个 SQL 引擎将用户输入的 SQL 字符串解析为可执行的查询计划，并通过存储引擎操作数据。这是连接用户接口与底层存储的中间层，使数据库具备声明式查询能力。依赖 `tinydb-storage` 提供的存储 API。

## What Changes

- 新增 SQL 词法分析器：将 SQL 字符串拆分为 token 序列
- 新增 SQL 语法分析器：将 token 序列解析为抽象语法树（AST）
- 新增查询计划器：将 AST 转为物理执行计划
- 新增执行引擎：实现 Scan、Filter、Project、Aggregate、Sort、Limit 算子
- 新增 DDL 执行：CREATE TABLE、DROP TABLE
- 新增 DML 执行：INSERT、SELECT、UPDATE、DELETE
- 新增 WHERE 条件求值（AND/OR 复合条件）
- 新增列约束执行：PRIMARY KEY、NOT NULL、UNIQUE

## Capabilities

### New Capabilities
- `lexer`: SQL 词法分析器，将 SQL 字符串转为 token 流（关键字、标识符、字面量、运算符、分隔符）
- `parser`: SQL 语法分析器，将 token 流转为 AST（PostgreSQL 风格语法）
- `planner`: 查询计划器，将 AST 转为物理执行计划（选择扫描策略）
- `executor`: 查询执行引擎，实现火山模型算子（Scan/Filter/Project/Aggregate/Sort/Limit）
- `ddl`: DDL 语句执行（CREATE TABLE 含列约束定义、DROP TABLE）
- `dml`: DML 语句执行（INSERT/SELECT/UPDATE/DELETE + WHERE）
- `expressions`: 表达式求值器（算术运算、比较运算、逻辑运算 AND/OR/NOT）
- `constraints`: 列约束检查（PRIMARY KEY 唯一性、NOT NULL、UNIQUE）

### Modified Capabilities

（无）

## Impact

- 新增包 `tinydb/sql/`（lexer.py、parser.py、planner.py、executor.py）
- 依赖 `tinydb-storage` 的存储 API（Page、BufferPool、TableManager）
- 为 `tinydb-index-txn` 提供基础执行框架
- 用户通过 `tinydb.Database.execute(sql)` 接口使用

```

## openspec/changes/tinydb-sql/design.md

- Source: openspec/changes/tinydb-sql/design.md
- Lines: 1-91
- SHA256: 3aa25146c3739a465b3672e1073c0b1dddccded398a471d7b46c985deb259557

[TRUNCATED]

```md
## Context

SQL 引擎是 tinydb 的核心中间层，接收 SQL 字符串，解析为 AST，生成执行计划，通过存储引擎读写数据。本模块依赖 `tinydb-storage` 的缓冲池、页管理、行格式 API。

教学优先原则：每个处理阶段（词法→语法→计划→执行）独立模块化，有清晰的数据结构流转。

## Goals / Non-Goals

**Goals:**
- PostgreSQL 风格 SQL 语法支持（DDL + DML + 条件表达式）
- 清晰的词法→语法→计划→执行流水线
- 火山模型执行引擎（迭代器模式）
- WHERE 条件求值支持 AND/OR/NOT
- ORDER BY + LIMIT + OFFSET 支持
- 聚合函数 COUNT/SUM/AVG + GROUP BY
- 列约束在 DML 时强制执行

**Non-Goals:**
- 子查询、JOIN、窗口函数
- 查询优化器（无基于代价的优化）
- 预编译/参数化查询
- 多表操作

## Decisions

### D1: 词L分析器采用手写递归下降

| 方案 | 优点 | 缺点 |
|------|------|------|
| 手写递归下降 | 清晰可控、错误信息好、教学友好 | 代码量稍大 |
| PLY/ANTLR | 自动生成 | 额外依赖、不透明 |

选择手写：零依赖、教学清晰、错误定位精确。

### D2: 语法分析器采用递归下降

每个 SQL 语句类型对应一个解析方法：
```
parse_select() → parse_where() → parse_order_by() → parse_limit()
```

### D3: 执行引擎采用火山模型（Iterator Model）

```
┌─────────────┐
│   Limit     │
├─────────────┤
│   Sort      │
├─────────────┤
│  Aggregate  │
├─────────────┤
│   Project   │
├─────────────┤
│   Filter    │
├─────────────┤
│   Scan      │  ← 全表扫描，从存储引擎逐行读取
└─────────────┘
```

每个算子实现 `__iter__()` 和 `__next__()`，向上游拉取数据。教学上这是最经典的执行模型。

### D4: WHERE 条件采用表达式树求值

```
        AND
       /   \
     >       =
    / \     / \
   age 25  name 'Alice'
```

每个节点是一个表达式对象，对一行数据求值返回 bool。

### D5: GROUP BY 采用内存哈希聚合

遍历时以 GROUP BY 列为 key 构建哈希表，聚合函数累加。简单但不支持超大数据集（教学足够）。

### D6: 约束检查嵌入 DML 执行路径

- PRIMARY KEY / UNIQUE：INSERT/UPDATE 时检查列值是否已存在

```

Full source: openspec/changes/tinydb-sql/design.md

## openspec/changes/tinydb-sql/tasks.md

- Source: openspec/changes/tinydb-sql/tasks.md
- Lines: 1-77
- SHA256: 47f98274c2bb0e6173b33ad6b7e604ba90549a2fb419e845cc90cdfa2c8b7577

```md
## 1. Lexer

- [ ] 1.1 定义 Token 类型和 TokenType 枚举（关键字、字面量、运算符、分隔符、标识符）
- [ ] 1.2 实现 Lexer 类：逐个字符扫描，生成 token 列表
- [ ] 1.3 实现关键字识别（SELECT, FROM, WHERE 等）
- [ ] 1.4 实现字面量识别（整数、浮点数、字符串、布尔值、NULL）
- [ ] 1.5 实现运算符识别（=, !=, <>, <, >, <=, >=, +, -, *, /）
- [ ] 1.6 实现标识符识别（字母/下划线开头）
- [ ] 1.7 编写 lexer 单元测试

## 2. Parser

- [ ] 2.1 定义 AST 节点类型（SelectStatement, InsertStatement, UpdateStatement 等）
- [ ] 2.2 实现 Parser 类：递归下降解析
- [ ] 2.3 实现 parse_select 方法（列、FROM、WHERE、ORDER BY、LIMIT、OFFSET）
- [ ] 2.4 实现 parse_insert 方法
- [ ] 2.5 实现 parse_update 方法
- [ ] 2.6 实现 parse_delete 方法
- [ ] 2.7 实现 parse_create_table 方法（含列约束）
- [ ] 2.8 实现 parse_drop_table 方法
- [ ] 2.9 实现 parse_where 表达式解析（AND/OR/NOT 优先级）
- [ ] 2.10 实现 parse_expression（比较、算术）
- [ ] 2.11 编写 parser 单元测试

## 3. Expressions

- [ ] 3.1 定义 Expression 基类和子类（ColumnRef, Literal, BinaryOp, UnaryOp）
- [ ] 3.2 实现表达式求值方法 evaluate(row)
- [ ] 3.3 实现逻辑运算（AND, OR, NOT）
- [ ] 3.4 实现比较运算（=, !=, <, >, <=, >=）
- [ ] 3.5 实现算术运算（+, -, *, /）
- [ ] 3.6 编写 expressions 单元测试

## 4. Planner

- [ ] 4.1 定义 PlanNode 基类和子类
- [ ] 4.2 实现 Planner 类：将 AST 转换为执行计划树
- [ ] 4.3 实现 SELECT 计划生成（选择扫描策略）
- [ ] 4.4 实现聚合查询计划生成
- [ ] 4.5 编写 planner 单元测试

## 5. Executor

- [ ] 5.1 定义 Operator 基类（next() 接口）
- [ ] 5.2 实现 ScanOperator：全表扫描，从存储引擎逐行读取
- [ ] 5.3 实现 FilterOperator：应用 WHERE 条件
- [ ] 5.4 实现 ProjectOperator：选择列
- [ ] 5.5 实现 AggregateOperator：COUNT/SUM/AVG + GROUP BY
- [ ] 5.6 实现 SortOperator：内存排序
- [ ] 5.7 实现 LimitOperator：LIMIT/OFFSET
- [ ] 5.8 编写 executor 单元测试

## 6. DDL

- [ ] 6.1 实现 CreateTableExecutor：调用存储引擎创建表
- [ ] 6.2 实现 DropTableExecutor：调用存储引擎删除表
- [ ] 6.3 编写 ddl 单元测试

## 7. DML

- [ ] 7.1 实现 InsertExecutor：插入行
- [ ] 7.2 实现 SelectExecutor：查询并返回结果
- [ ] 7.3 实现 UpdateExecutor：更新行
- [ ] 7.4 实现 DeleteExecutor：删除行
- [ ] 7.5 编写 dml 单元测试

## 8. Constraints

- [ ] 8.1 实现约束检查模块（调用存储引擎检查唯一性）
- [ ] 8.2 在 DML 执行路径嵌入约束检查
- [ ] 8.3 编写约束测试

## 9. Integration

- [ ] 9.1 实现 Database.execute(sql) 入口方法
- [ ] 9.2 编写端到端集成测试
- [ ] 9.3 编写 SQL 基准测试脚本

```

## openspec/changes/tinydb-sql/specs/constraints/spec.md

- Source: openspec/changes/tinydb-sql/specs/constraints/spec.md
- Lines: 1-33
- SHA256: 4bcd312293b003efb18d5afe2dcc247953e937c74ec6a5911d8cec063d811cab

```md
## ADDED Requirements

### Requirement: PRIMARY KEY 约束检查
The system SHALL enforce PRIMARY KEY uniqueness on INSERT and UPDATE operations.

#### Scenario: 插入重复主键
- **WHEN** 插入 id=1 但 id=1 已存在
- **THEN** 操作被拒绝，返回唯一性违反错误

### Requirement: NOT NULL 约束检查
The system SHALL reject NULL values for NOT NULL columns on INSERT and UPDATE.

#### Scenario: 插入 NULL 到 NOT NULL 列
- **WHEN** 向 NOT NULL 列插入 NULL 值
- **THEN** 操作被拒绝

### Requirement: UNIQUE 约束检查
The system SHALL enforce UNIQUE constraint across all rows for the specified column.

#### Scenario: 插入重复 UNIQUE 值
- **WHEN** 向 UNIQUE 列插入已存在的值
- **THEN** 操作被拒绝

### Requirement: 类型检查
The system SHALL reject values that do not match the column's data type.

#### Scenario: 类型不匹配
- **WHEN** 向 INTEGER 列插入 TEXT 值
- **THEN** 操作被拒绝

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-sql/specs/ddl/spec.md

- Source: openspec/changes/tinydb-sql/specs/ddl/spec.md
- Lines: 1-19
- SHA256: 566a0d9657c63fcfdd440504ba33e1a6d13efdaea0c41d2620b9bcc9338fc9bb

```md
## ADDED Requirements

### Requirement: 执行 CREATE TABLE
The system SHALL create a new table with the specified columns and constraints via the storage engine.

#### Scenario: 创建含约束的表
- **WHEN** 执行 CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)
- **THEN** 存储引擎中注册表定义，可后续 INSERT 数据

### Requirement: 执行 DROP TABLE
The system SHALL remove a table and all its data via the storage engine.

#### Scenario: 删除表
- **WHEN** 执行 DROP TABLE users
- **THEN** 表及其所有数据被移除，后续查询该表返回错误

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-sql/specs/dml/spec.md

- Source: openspec/changes/tinydb-sql/specs/dml/spec.md
- Lines: 1-41
- SHA256: c6d4948963f5ded9e0a25b5d104d03fdabf3e03e422db6398a27a217231fce1c

```md
## ADDED Requirements

### Requirement: 执行 INSERT 插入数据
The system SHALL insert a row into the specified table, respecting column constraints.

#### Scenario: 正常插入
- **WHEN** 执行 INSERT INTO users (name, age) VALUES ('Alice', 30)
- **THEN** 表新增一行数据

#### Scenario: 违反 NOT NULL
- **WHEN** 向 NOT NULL 列插入 NULL
- **THEN** 系统拒绝并返回约束违反错误

#### Scenario: 违反主键唯一性
- **WHEN** 插入与已有行主键相同的行
- **THEN** 系统拒绝并返回约束违反错误

### Requirement: 执行 SELECT 查询
The system SHALL execute SELECT queries and return result rows.

#### Scenario: 条件查询
- **WHEN** 执行 SELECT name FROM users WHERE age > 25
- **THEN** 返回所有 age > 25 的行的 name 列

### Requirement: 执行 UPDATE 更新数据
The system SHALL update rows matching the WHERE condition.

#### Scenario: 条件更新
- **WHEN** 执行 UPDATE users SET age = 31 WHERE name = 'Alice'
- **THEN** name='Alice' 的行 age 更新为 31

### Requirement: 执行 DELETE 删除数据
The system SHALL delete rows matching the WHERE condition.

#### Scenario: 条件删除
- **WHEN** 执行 DELETE FROM users WHERE age < 18
- **THEN** 所有 age < 18 的行被删除

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-sql/specs/executor/spec.md

- Source: openspec/changes/tinydb-sql/specs/executor/spec.md
- Lines: 1-51
- SHA256: 2733884eddd99926cf6be21e12a0b3898460e450446c503ae67be69865d00abc

```md
## ADDED Requirements

### Requirement: Scan 算子
The system SHALL provide a Scan operator that reads all rows from a table using the storage engine.

#### Scenario: 全表扫描
- **WHEN** Scan 算子作用于 users 表
- **THEN** 迭代返回表中所有行

### Requirement: Filter 算子
The system SHALL provide a Filter operator that applies a WHERE condition to each row.

#### Scenario: 条件过滤
- **WHEN** Filter 算子条件为 age > 25，输入包含 age=20 和 age=30 的行
- **THEN** 仅返回 age=30 的行

### Requirement: Project 算子
The system SHALL provide a Project operator that selects specific columns.

#### Scenario: 列选择
- **WHEN** Project 算子指定列 [name, age]，输入含 [id, name, age] 的行
- **THEN** 仅返回 [name, age] 列的行

### Requirement: Aggregate 算子
The system SHALL provide an Aggregate operator supporting COUNT, SUM, AVG with optional GROUP BY.

#### Scenario: COUNT 聚合
- **WHEN** Aggregate 算子执行 SELECT COUNT(*) FROM users
- **THEN** 返回一行一列，值为总行数

#### Scenario: GROUP BY 聚合
- **WHEN** 执行 SELECT dept, AVG(salary) FROM employees GROUP BY dept
- **THEN** 返回每个 dept 一行的平均工资

### Requirement: Sort 算子
The system SHALL provide a Sort operator supporting ORDER BY with ASC/DESC.

#### Scenario: 升序排序
- **WHEN** Sort 算子按 age ASC 排序
- **THEN** 返回按 age 升序排列的行

### Requirement: Limit 算子
The system SHALL provide a Limit operator supporting LIMIT and OFFSET.

#### Scenario: LIMIT 分页
- **WHEN** Limit 算子 limit=10 offset=20
- **THEN** 跳过前 20 行，返回接下来的 10 行

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-sql/specs/expressions/spec.md

- Source: openspec/changes/tinydb-sql/specs/expressions/spec.md
- Lines: 1-26
- SHA256: d25a0673f61c5cd25145af39473c2c28ef6d02a3dc94ec89057e853593bf98b3

```md
## ADDED Requirements

### Requirement: 算术表达式求值
The system SHALL evaluate arithmetic expressions (+, -, *, /) on column values and literals.

### Requirement: 比较表达式求值
The system SHALL evaluate comparison expressions (=, !=, <>, <, >, <=, >=) and return boolean results.

#### Scenario: 列与字面量比较
- **WHEN** 表达式 age > 25，行数据 age=30
- **THEN** 返回 True

### Requirement: 逻辑表达式求值
The system SHALL evaluate AND, OR, NOT expressions with correct precedence.

#### Scenario: 复合条件
- **WHEN** 表达式 age > 25 AND name = 'Alice'，行数据 age=30, name='Bob'
- **THEN** 返回 False

#### Scenario: OR 条件
- **WHEN** 表达式 age > 25 OR name = 'Alice'，行数据 age=30, name='Bob'
- **THEN** 返回 True

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-sql/specs/lexer/spec.md

- Source: openspec/changes/tinydb-sql/specs/lexer/spec.md
- Lines: 1-44
- SHA256: 0c3164a39ad5370466ef58618f9623899220e339857427eccfcdc7542b6d1d1b

```md
## ADDED Requirements

### Requirement: 词L分析器识别 SQL 关键字
The system SHALL recognize SQL keywords including SELECT, FROM, WHERE, INSERT, INTO, VALUES, UPDATE, SET, DELETE, CREATE, TABLE, DROP, ORDER, BY, LIMIT, OFFSET, AND, OR, NOT, NULL, PRIMARY, KEY, UNIQUE, INTEGER, FLOAT, TEXT, BOOLEAN, PRIMARY KEY, NOT NULL.

#### Scenario: 识别 SELECT 关键字
- **WHEN** 输入字符串 "SELECT"
- **THEN** 词L分析器返回 Token(KEYWORD, "SELECT")

### Requirement: 词L分析器识别字面量
The system SHALL recognize integer literals, float literals, string literals (single-quoted), and boolean literals (TRUE/FALSE).

#### Scenario: 识别整数
- **WHEN** 输入 "42"
- **THEN** 返回 Token(INT_LIT, 42)

#### Scenario: 识别字符串
- **WHEN** 输入 "'hello'"
- **THEN** 返回 Token(STR_LIT, "hello")

### Requirement: 词L分析器识别运算符
The system SHALL recognize =, !=, <>, <, >, <=, >=, +, -, *, /, and parentheses.

#### Scenario: 识别不等于运算符
- **WHEN** 输入 "!="
- **THEN** 返回 Token(OP, "!=")

### Requirement: 词L分析器识别标识符
The system SHALL recognize identifiers (table names, column names) following PostgreSQL naming rules.

#### Scenario: 识别表名
- **WHEN** 输入 "users"
- **THEN** 返回 Token(IDENT, "users")

### Requirement: 词L分析器跳过空白字符
The system SHALL skip spaces, tabs, and newlines.

#### Scenario: 跳过空格
- **WHEN** 输入 "SELECT  *"
- **THEN** 返回 Token(KEYWORD, "SELECT") 后接 Token(OP, "*")

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-sql/specs/parser/spec.md

- Source: openspec/changes/tinydb-sql/specs/parser/spec.md
- Lines: 1-57
- SHA256: fde9e97bfcb4397bc3cec44ac36ddfb465c66e3e19ecb403334f800b3eaa8bf1

```md
## ADDED Requirements

### Requirement: 解析 SELECT 语句
The system SHALL parse SELECT statements with columns, FROM, WHERE, ORDER BY, LIMIT, OFFSET clauses.

#### Scenario: 解析简单查询
- **WHEN** 输入 tokens 对应 "SELECT name, age FROM users"
- **THEN** 返回 SelectStatement(columns=[name, age], table=users) 的 AST

#### Scenario: 解析含 WHERE 的查询
- **WHEN** 输入 "SELECT * FROM users WHERE age > 25"
- **THEN** 返回的 AST 包含 Filter 节点，条件为 age > 25

### Requirement: 解析 INSERT 语句
The system SHALL parse INSERT INTO ... VALUES (...) statements.

#### Scenario: 解析 INSERT
- **WHEN** 输入 "INSERT INTO users (name, age) VALUES ('Alice', 30)"
- **THEN** 返回 InsertStatement(table=users, columns=[name, age], values=['Alice', 30]) 的 AST

### Requirement: 解析 UPDATE 语句
The system SHALL parse UPDATE ... SET ... WHERE ... statements.

#### Scenario: 解析 UPDATE
- **WHEN** 输入 "UPDATE users SET age = 31 WHERE name = 'Alice'"
- **THEN** 返回 UpdateStatement(table=users, sets={age: 31}, condition=name='Alice') 的 AST

### Requirement: 解析 DELETE 语句
The system SHALL parse DELETE FROM ... WHERE ... statements.

### Requirement: 解析 CREATE TABLE 语句
The system SHALL parse CREATE TABLE with column definitions and constraints (PRIMARY KEY, NOT NULL, UNIQUE).

#### Scenario: 解析建表
- **WHEN** 输入 "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
- **THEN** 返回 CreateTableStatement 包含两列定义及各自约束

### Requirement: 解析 DROP TABLE 语句
The system SHALL parse DROP TABLE statements.

### Requirement: 解析 WHERE 复合条件
The system SHALL handle AND, OR, NOT with correct precedence (NOT > AND > OR).

#### Scenario: 解析复合条件
- **WHEN** 输入 "WHERE age > 25 AND name = 'Alice'"
- **THEN** 返回 BinaryOp(AND, >, =) 的表达式树

### Requirement: 语法错误报告
The system SHALL provide clear error messages with position information on syntax errors.

#### Scenario: 缺少 FROM
- **WHEN** 输入 "SELECT name"
- **THEN** 报告 "Expected FROM at position X"

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-sql/specs/planner/spec.md

- Source: openspec/changes/tinydb-sql/specs/planner/spec.md
- Lines: 1-22
- SHA256: e80ca99cc4efed4cadeb2dbf74f44d83e3c183b50192deff743730e9bde27343

```md
## ADDED Requirements

### Requirement: 计划器生成执行计划
The system SHALL convert an AST into a physical execution plan (operator tree).

#### Scenario: SELECT 生成计划
- **WHEN** AST 为 SELECT name FROM users WHERE age > 25
- **THEN** 生成 Plan = Project([name], Filter(age>25, Scan(users)))

### Requirement: 计划器选择全表扫描策略
The system SHALL default to full table scan when no index is available.

#### Scenario: 无索引表查询
- **WHEN** 查询无索引的表
- **THEN** 计划器选择 Scan 算子进行全表扫描

### Requirement: 处理聚合查询计划
The system SHALL generate an Aggregate operator node for queries with aggregate functions.

## MODIFIED Requirements

（无）

```
