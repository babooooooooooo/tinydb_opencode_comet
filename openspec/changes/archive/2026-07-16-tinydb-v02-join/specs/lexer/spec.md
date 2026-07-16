# lexer Specification

## ADDED Requirements

### Requirement: 词L分析器识别 JOIN 关键字
The system SHALL recognize JOIN-related keywords: JOIN, INNER, LEFT, RIGHT, FULL, OUTER, CROSS, NATURAL, ON, USING.

#### Scenario: 识别 JOIN 关键字
- **WHEN** 输入字符串 "JOIN"
- **THEN** 词L分析器返回 Token(KEYWORD, "JOIN")

#### Scenario: 识别 INNER 关键字
- **WHEN** 输入字符串 "INNER"
- **THEN** 词L分析器返回 Token(KEYWORD, "INNER")

#### Scenario: 识别 LEFT 关键字
- **WHEN** 输入字符串 "LEFT"
- **THEN** 词L分析器返回 Token(KEYWORD, "LEFT")

#### Scenario: 识别 RIGHT 关键字
- **WHEN** 输入字符串 "RIGHT"
- **THEN** 词L分析器返回 Token(KEYWORD, "RIGHT")

#### Scenario: 识别 FULL 关键字
- **WHEN** 输入字符串 "FULL"
- **THEN** 词L分析器返回 Token(KEYWORD, "FULL")

#### Scenario: 识别 OUTER 关键字
- **WHEN** 输入字符串 "OUTER"
- **THEN** 词L分析器返回 Token(KEYWORD, "OUTER")

#### Scenario: 识别 CROSS 关键字
- **WHEN** 输入字符串 "CROSS"
- **THEN** 词L分析器返回 Token(KEYWORD, "CROSS")

#### Scenario: 识别 NATURAL 关键字
- **WHEN** 输入字符串 "NATURAL"
- **THEN** 词L分析器返回 Token(KEYWORD, "NATURAL")

#### Scenario: 识别 ON 关键字
- **WHEN** 输入字符串 "ON"
- **THEN** 词L分析器返回 Token(KEYWORD, "ON")

#### Scenario: 识别 USING 关键字
- **WHEN** 输入字符串 "USING"
- **THEN** 词L分析器返回 Token(KEYWORD, "USING")

### Requirement: 词L分析器识别点号分隔的带限定符标识符
The system SHALL recognize dot-separated identifiers (e.g., `table.column`) as a column reference with table qualifier, consisting of IDENT DOT IDENT sequences.

#### Scenario: 识别带表限定的列名
- **WHEN** 输入 "users.name"
- **THEN** 词L分析器返回三个 tokens: Token(IDENT, "users"), Token(OP, "."), Token(IDENT, "name") 供 parser 组装为 ColumnRef(name="name", table="users")
