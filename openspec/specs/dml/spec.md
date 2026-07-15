# dml Specification

## Purpose
TBD - created by archiving change tinydb-sql. Update Purpose after archive.
## Requirements
### Requirement: 执行 INSERT 插入数据
The system SHALL insert a row into the specified table, respecting column constraints.

#### Scenario: 正常插入
- **WHEN** 执行 INSERT INTO users (name, age) VALUES ('Alice', 30)
- **THEN** 表新增一行数据

#### Scenario: 违反 NOT NULL
- **WHEN** 向 NOT NULL 列插入 NULL
- **THEN** 系统拒绝并返回约束违反错误

#### Scenario: 违反主键唯一性
- **WHEN** 插入与已有行主键相同的行
- **THEN** 系统拒绝并返回约束违反错误

### Requirement: 执行 SELECT 查询
The system SHALL execute SELECT queries and return result rows.

#### Scenario: 条件查询
- **WHEN** 执行 SELECT name FROM users WHERE age > 25
- **THEN** 返回所有 age > 25 的行的 name 列

### Requirement: 执行 UPDATE 更新数据
The system SHALL update rows matching the WHERE condition.

#### Scenario: 条件更新
- **WHEN** 执行 UPDATE users SET age = 31 WHERE name = 'Alice'
- **THEN** name='Alice' 的行 age 更新为 31

### Requirement: 执行 DELETE 删除数据
The system SHALL delete rows matching the WHERE condition.

#### Scenario: 条件删除
- **WHEN** 执行 DELETE FROM users WHERE age < 18
- **THEN** 所有 age < 18 的行被删除

