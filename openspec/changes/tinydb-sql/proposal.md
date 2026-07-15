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
