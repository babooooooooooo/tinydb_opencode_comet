# executor Specification

## Purpose
TBD - created by archiving change tinydb-sql. Update Purpose after archive.
## Requirements
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

