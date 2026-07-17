# Design: Code Review Fixes

## 核心思路

最小改动、最大收益。每个修复独立可验证。

### 1. 提取 `_JoinBase` 基类

三个 JOIN 算子（NestedLoopJoinOperator、HashJoinOperator、SortMergeJoinOperator）共享：
- `_combine_rows` — 合并两行并处理列名冲突
- `_combine_with_nulls` — 外侧补 NULL
- `_extract_left_key_from_row` / `_extract_right_key_from_row` — 提取 join key

提取为 `_JoinBase(Operator)` 基类，三个算子继承并只保留各自 `__iter__` 中的算法差异。

### 2. 修复 DmlOperator 缩进

`_execute_update` 中 `self._check_constraints_update` 和 `table.update` 应在 `if` 内部。

### 3. 统一执行路径

将 `database.py` 的 regex-based `_exec_select`/`_exec_update`/`_exec_delete` 路由到 SQL 引擎。所有 SELECT 都走 `_exec_sql_select`。移除 `_is_complex_select`。

### 4. 清理死代码

- `result = {}` 重复赋值（HashJoin + SortMergeJoin）
- IndexScanOperator 暂不修复（需要 planner 集成，范围扩大）
- `AggregateOperator` 的 stringly-typed 改为常量
