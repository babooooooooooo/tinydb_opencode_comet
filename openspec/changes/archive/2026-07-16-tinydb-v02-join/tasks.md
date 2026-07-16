# Tasks: 多表 JOIN 查询

## Phase 1: AST 与 Lexer 扩展

- [x] 1.1 修改 `tinydb/sql/ast.py`：新增 `TableRef`、`JoinClause` 节点
- [x] 1.2 修改 `tinydb/sql/ast.py`：修改 `SelectStatement`，`table` → `from_table`，新增 `joins` 字段
- [x] 1.3 修改 `tinydb/sql/ast.py`：修改 `ColumnRef`，新增 `table` 字段
- [x] 1.4 修改 `tinydb/sql/lexer.py`：新增 JOIN 相关 TokenType（JOIN, INNER, LEFT, RIGHT, FULL, OUTER, CROSS, NATURAL, ON, USING）
- [x] 1.5 修改 `tinydb/sql/lexer.py`：新增关键词映射

## Phase 2: Parser 扩展

- [x] 2.1 实现 `_parse_table_ref()` 方法（解析表名 + 可选别名）
- [x] 2.2 实现 `_parse_join_clauses()` 方法（循环解析 JOIN 子句）
- [x] 2.3 实现 `_parse_join_clause()` 方法（解析单条 JOIN）
- [x] 2.4 实现 `_is_join_keyword()` 辅助方法
- [x] 2.5 修改 `_parse_select()` 集成 FROM 多表解析
- [x] 2.6 修改 `_parse_primary()` 支持 `table.column` 限定列名解析

## Phase 3: Planner 扩展

- [x] 3.1 实现 `JoinPlanner` 类（plan_joins 入口方法）
- [x] 3.2 实现 `_choose_algorithm()` 算法选择逻辑
- [x] 3.3 实现 `_build_scan()` 构建 ScanOperator
- [x] 3.4 实现 `_build_join_operator()` 根据算法构建对应 JoinOperator
- [x] 3.5 实现 NATURAL JOIN 同名列自动匹配
- [x] 3.6 实现列名解析（alias → table → column index）
- [x] 3.7 修改 `Planner._plan_select()` 集成 JoinPlanner

## Phase 4: Executor 扩展

- [x] 4.1 实现 `NestedLoopJoinOperator`（支持 INNER/LEFT/RIGHT/FULL/CROSS）
- [x] 4.2 实现 `HashJoinOperator`（支持 INNER/LEFT/RIGHT/FULL 等值连接）
- [x] 4.3 实现 `SortMergeJoinOperator`（支持 INNER/LEFT/RIGHT/FULL 等值连接）
- [x] 4.4 实现行合并逻辑（`_combine_rows`、`_combine_with_nulls`）
- [x] 4.5 实现列名冲突处理（同名列加别名前缀）
- [x] 4.6 实现连接键提取（`_extract_key`）

## Phase 5: Database 入口适配

- [x] 5.1 修改 `tinydb/sql/database.py`：适配 `SelectStatement.from_table` 类型变更
- [x] 5.2 修改 `_execute_select()` 列名解析逻辑（支持限定名）
- [x] 5.3 修改 `_execute_select()` 列展示名生成（处理冲突）

## Phase 6: 测试

- [x] 6.1 编写 AST/Parser 单元测试（每种 JOIN 类型解析正确性）
- [x] 6.2 编写 Executor 单元测试（每种算法 × 每种 JOIN 类型）
- [x] 6.3 编写边界测试（NULL、空表、自连接、列名冲突）
- [x] 6.4 编写正确性测试（与 SQLite 结果对比）
- [x] 6.5 编写集成测试（端到端 SQL 执行）
- [x] 6.6 运行全量回归测试（确保 v0.1 用例不退化）

## Phase 7: 收尾

- [x] 7.1 运行 lint 和 typecheck
- [x] 7.2 更新 CLAUDE.md（如有新命令或架构变更）
- [x] 7.3 清理临时代码和调试日志
