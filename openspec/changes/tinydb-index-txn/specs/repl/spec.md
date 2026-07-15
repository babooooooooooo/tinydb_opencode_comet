## ADDED Requirements

### Requirement: REPL 交互循环
The system SHALL provide an interactive REPL that accepts SQL input and displays results.

#### Scenario: 执行查询
- **WHEN** 用户在 REPL 输入 "SELECT * FROM users;"
- **THEN** 执行查询并以表格形式展示结果

### Requirement: 多行 SQL 输入
The system SHALL support multi-line SQL statements terminated by semicolon.

#### Scenario: 多行输入
- **WHEN** 用户输入多行后以分号结束
- **THEN** 系统合并多行作为一条 SQL 执行

### Requirement: 元命令支持
The system SHALL support REPL meta-commands:
- `.exit` or `.quit` — 退出 REPL
- `.tables` — 列出所有表
- `.schema <table>` — 显示表结构

#### Scenario: 查看表列表
- **WHEN** 用户输入 ".tables"
- **THEN** 显示数据库中所有表名

### Requirement: 错误提示
The system SHALL display errors (syntax errors, constraint violations) in a user-friendly format.

#### Scenario: 语法错误
- **WHEN** 输入无效 SQL
- **THEN** 显示错误信息，不崩溃

### Requirement: 历史记录
The system SHALL support command history navigation (up/down arrow).

#### Scenario: 调出历史命令
- **WHEN** 用户按上箭头
- **THEN** 显示上一条输入的 SQL

## MODIFIED Requirements

（无）
