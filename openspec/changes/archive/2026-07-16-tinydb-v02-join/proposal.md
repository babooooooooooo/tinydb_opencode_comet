# Proposal: 多表 JOIN 查询

## 摘要

为 tinydb v0.2 实现多表 JOIN 查询能力。在现有 v0.1 单表 SQL 引擎基础上，扩展 AST、Lexer、Parser、Planner 和 Executor，支持全部 JOIN 类型（INNER、LEFT、RIGHT、FULL OUTER、CROSS、NATURAL、SELF）和三种执行算法（Nested Loop Join、Hash Join、Sort-Merge Join）。

## 背景

v0.1 仅支持单表查询。实际使用中，多表关联查询是关系型数据库的核心能力。本 change 在 v0.1 架构上扩展 JOIN，保持与现有 Volcano 模型执行器、shadow paging 事务的兼容性。

## 范围

### 包含

- 7 种 JOIN 类型：INNER、LEFT、RIGHT、FULL OUTER、CROSS、NATURAL、SELF
- 3 种执行算法：Nested Loop Join、Hash Join、Sort-Merge Join
- 基于代价的算法选择（JoinPlanner）
- 列引用限定名支持（`table.column` 语法）
- 表别名支持

### 不包含

- 并发控制（由 tinydb-v02-concurrency 负责）
- CLI 增强（由 tinydb-v02-cli 负责）
- 查询优化器（仅做基于规则的选择，不做代价模型优化）
- 子查询中的 JOIN

## 影响文件

| 文件 | 变更类型 |
|------|---------|
| `tinydb/sql/ast.py` | 扩展：新增 TableRef、JoinClause；修改 SelectStatement |
| `tinydb/sql/lexer.py` | 扩展：新增 JOIN 相关 token |
| `tinydb/sql/parser.py` | 扩展：FROM 子句解析多表 JOIN |
| `tinydb/sql/planner.py` | 扩展：新增 JoinPlanner |
| `tinydb/sql/executor.py` | 扩展：新增 3 种 JoinOperator |
| `tinydb/sql/expressions.py` | 扩展：ColumnRef 支持 table 限定 |
| `tinydb/sql/database.py` | 最小改动：列名解析适配 |
| `tests/` | 新增：JOIN 测试用例 |

## 依赖

无新依赖（纯标准库实现）。

## 风险

- AST 变更可能影响现有序列化/反序列化逻辑（当前无此逻辑，低风险）
- 多表列名解析需要处理歧义（同名列需报错）
- 与并发控制 change 合并时，database.py 可能有冲突（最小化改动降低风险）
