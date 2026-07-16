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

#### Scenario: 聚合函数生成计划
- **WHEN** 输入 "SELECT COUNT(*) FROM users"
- **THEN** 生成 Plan = Aggregate(COUNT(*), Scan(users))

## MODIFIED Requirements

（无）
