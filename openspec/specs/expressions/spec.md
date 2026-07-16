# expressions Specification

## Purpose
TBD - created by archiving change tinydb-sql. Update Purpose after archive.
## Requirements
### Requirement: 算术表达式求值
The system SHALL evaluate arithmetic expressions (+, -, *, /) on column values and literals.

#### Scenario: 列与字面量算术运算
- **WHEN** 表达式 salary * 1.1，行数据 salary=5000
- **THEN** 返回 5500

### Requirement: 比较表达式求值
The system SHALL evaluate comparison expressions (=, !=, <>, <, >, <=, >=) and return boolean results.

#### Scenario: 列与字面量比较
- **WHEN** 表达式 age > 25，行数据 age=30
- **THEN** 返回 True

### Requirement: 逻辑表达式求值
The system SHALL evaluate AND, OR, NOT expressions with correct precedence.

#### Scenario: 复合条件
- **WHEN** 表达式 age > 25 AND name = 'Alice'，行数据 age=30, name='Bob'
- **THEN** 返回 False

#### Scenario: OR 条件
- **WHEN** 表达式 age > 25 OR name = 'Alice'，行数据 age=30, name='Bob'
- **THEN** 返回 True

