# constraints Specification

## Purpose
TBD - created by archiving change tinydb-sql. Update Purpose after archive.
## Requirements
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

