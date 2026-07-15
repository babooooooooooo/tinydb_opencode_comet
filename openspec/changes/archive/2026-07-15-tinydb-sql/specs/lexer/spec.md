## ADDED Requirements

### Requirement: 词L分析器识别 SQL 关键字
The system SHALL recognize SQL keywords including SELECT, FROM, WHERE, INSERT, INTO, VALUES, UPDATE, SET, DELETE, CREATE, TABLE, DROP, ORDER, BY, LIMIT, OFFSET, AND, OR, NOT, NULL, PRIMARY, KEY, UNIQUE, INTEGER, FLOAT, TEXT, BOOLEAN, PRIMARY KEY, NOT NULL.

#### Scenario: 识别 SELECT 关键字
- **WHEN** 输入字符串 "SELECT"
- **THEN** 词L分析器返回 Token(KEYWORD, "SELECT")

### Requirement: 词L分析器识别字面量
The system SHALL recognize integer literals, float literals, string literals (single-quoted), and boolean literals (TRUE/FALSE).

#### Scenario: 识别整数
- **WHEN** 输入 "42"
- **THEN** 返回 Token(INT_LIT, 42)

#### Scenario: 识别字符串
- **WHEN** 输入 "'hello'"
- **THEN** 返回 Token(STR_LIT, "hello")

### Requirement: 词L分析器识别运算符
The system SHALL recognize =, !=, <>, <, >, <=, >=, +, -, *, /, and parentheses.

#### Scenario: 识别不等于运算符
- **WHEN** 输入 "!="
- **THEN** 返回 Token(OP, "!=")

### Requirement: 词L分析器识别标识符
The system SHALL recognize identifiers (table names, column names) following PostgreSQL naming rules.

#### Scenario: 识别表名
- **WHEN** 输入 "users"
- **THEN** 返回 Token(IDENT, "users")

### Requirement: 词L分析器跳过空白字符
The system SHALL skip spaces, tabs, and newlines.

#### Scenario: 跳过空格
- **WHEN** 输入 "SELECT  *"
- **THEN** 返回 Token(KEYWORD, "SELECT") 后接 Token(OP, "*")

## MODIFIED Requirements

（无）
