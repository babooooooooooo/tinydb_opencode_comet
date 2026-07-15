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
