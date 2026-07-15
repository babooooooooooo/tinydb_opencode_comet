## ADDED Requirements

### Requirement: 解析 SELECT 语句
The system SHALL parse SELECT statements with columns, FROM, WHERE, ORDER BY, LIMIT, OFFSET clauses.

#### Scenario: 解析简单查询
- **WHEN** 输入 tokens 对应 "SELECT name, age FROM users"
- **THEN** 返回 SelectStatement(columns=[name, age], table=users) 的 AST

#### Scenario: 解析含 WHERE 的查询
- **WHEN** 输入 "SELECT * FROM users WHERE age > 25"
- **THEN** 返回的 AST 包含 Filter 节点，条件为 age > 25

### Requirement: 解析 INSERT 语句
The system SHALL parse INSERT INTO ... VALUES (...) statements.

#### Scenario: 解析 INSERT
- **WHEN** 输入 "INSERT INTO users (name, age) VALUES ('Alice', 30)"
- **THEN** 返回 InsertStatement(table=users, columns=[name, age], values=['Alice', 30]) 的 AST

### Requirement: 解析 UPDATE 语句
The system SHALL parse UPDATE ... SET ... WHERE ... statements.

#### Scenario: 解析 UPDATE
- **WHEN** 输入 "UPDATE users SET age = 31 WHERE name = 'Alice'"
- **THEN** 返回 UpdateStatement(table=users, sets={age: 31}, condition=name='Alice') 的 AST

### Requirement: 解析 DELETE 语句
The system SHALL parse DELETE FROM ... WHERE ... statements.

### Requirement: 解析 CREATE TABLE 语句
The system SHALL parse CREATE TABLE with column definitions and constraints (PRIMARY KEY, NOT NULL, UNIQUE).

#### Scenario: 解析建表
- **WHEN** 输入 "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
- **THEN** 返回 CreateTableStatement 包含两列定义及各自约束

### Requirement: 解析 DROP TABLE 语句
The system SHALL parse DROP TABLE statements.

### Requirement: 解析 WHERE 复合条件
The system SHALL handle AND, OR, NOT with correct precedence (NOT > AND > OR).

#### Scenario: 解析复合条件
- **WHEN** 输入 "WHERE age > 25 AND name = 'Alice'"
- **THEN** 返回 BinaryOp(AND, >, =) 的表达式树

### Requirement: 语法错误报告
The system SHALL provide clear error messages with position information on syntax errors.

#### Scenario: 缺少 FROM
- **WHEN** 输入 "SELECT name"
- **THEN** 报告 "Expected FROM at position X"

## MODIFIED Requirements

（无）
