## ADDED Requirements

### Requirement: 创建索引
The system SHALL support creating a B-tree index on a table column via CREATE INDEX.

#### Scenario: 创建单列索引
- **WHEN** 执行 CREATE INDEX idx_age ON users (age)
- **THEN** 在 age 列上创建 B-tree 索引

### Requirement: 列出表索引
The system SHALL maintain metadata about all indexes associated with each table.

#### Scenario: 查看索引元数据
- **WHEN** 查询某表的索引信息
- **THEN** 返回所有索引名称和对应列

### Requirement: 删除索引
The system SHALL support dropping an index via DROP INDEX.

#### Scenario: 删除索引
- **WHEN** 执行 DROP INDEX idx_age
- **THEN** 索引被删除，后续查询不再使用该索引

## MODIFIED Requirements

（无）
