# planner Specification

## ADDED Requirements

### Requirement: JoinPlanner 生成 JOIN 执行计划
The system SHALL provide a JoinPlanner that converts a FROM table reference and list of JoinClause nodes into a tree of physical JoinOperator nodes.

#### Scenario: 无 JOIN 的查询生成 Scan 计划
- **WHEN** plan_joins receives a TableRef with empty joins list
- **THEN** returns a ScanOperator for the specified table

#### Scenario: 单个 INNER JOIN 生成 JOIN 计划
- **WHEN** plan_joins receives two tables with one INNER JoinClause
- **THEN** returns a JoinOperator tree with left=ScanOperator(left_table), right=ScanOperator(right_table)

#### Scenario: 多个 JOIN 生成嵌套计划
- **WHEN** plan_joins receives three tables with two JoinClause entries
- **THEN** returns a left-deep tree of JoinOperators

### Requirement: JoinPlanner 基于规则选择算法
The system SHALL select the join algorithm based on the following rules: CROSS JOIN uses Nested Loop; NATURAL/USING with large right table uses Hash Join; right table has index on join key uses Index Nested Loop; both sides sorted uses Sort-Merge; defaults to Nested Loop.

#### Scenario: CROSS JOIN 选择 Nested Loop
- **WHEN** join_type is "CROSS"
- **THEN** algorithm selection returns "nested_loop"

#### Scenario: 大表等值连接选择 Hash Join
- **WHEN** join_type is "INNER" with ON condition and right table row_count > 1000
- **THEN** algorithm selection returns "hash"

#### Scenario: 有索引时选择 Index Nested Loop
- **WHEN** join condition references an indexed column on the right table
- **THEN** algorithm selection returns "index_nested_loop"

#### Scenario: 已排序数据选择 Sort-Merge Join
- **WHEN** both inputs are already sorted on the join key
- **THEN** algorithm selection returns "sort_merge"

#### Scenario: 默认选择 Nested Loop Join
- **WHEN** none of the special conditions apply
- **THEN** algorithm selection returns "nested_loop"

### Requirement: JoinPlanner 集成到主计划流程
The system SHALL modify the main Planner to use JoinPlanner for generating the scan/join subtree, then apply Filter, Aggregate, Project, Sort, and Limit operators on top.

#### Scenario: SELECT with WHERE after JOIN
- **WHEN** AST contains joins and a WHERE clause
- **THEN** the plan tree places FilterOperator above the JoinOperator tree
