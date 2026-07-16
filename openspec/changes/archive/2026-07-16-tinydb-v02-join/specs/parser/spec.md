# parser Specification

## ADDED Requirements

### Requirement: 解析多表 FROM 子句
The system SHALL parse a FROM clause containing a main table reference followed by zero or more JOIN clauses, producing a SelectStatement with a list of JoinClause nodes.

#### Scenario: 解析单表 FROM 子句
- **WHEN** 输入 tokens 对应 "FROM users u"
- **THEN** 返回 SelectStatement with from_table=TableRef(name="users", alias="u") and empty joins list

#### Scenario: 解析带 INNER JOIN 的 FROM 子句
- **WHEN** 输入 tokens 对应 "FROM users u INNER JOIN orders o ON u.id = o.user_id"
- **THEN** 返回 SelectStatement with from_table=TableRef("users","u") and one JoinClause(INNER, TableRef("orders","o"), on_condition=u.id=o.user_id)

#### Scenario: 解析带 LEFT OUTER JOIN 的 FROM 子句
- **WHEN** 输入 tokens 对应 "FROM users u LEFT OUTER JOIN orders o ON u.id = o.user_id"
- **THEN** 返回 SelectStatement with one JoinClause(LEFT, TableRef("orders","o"), on_condition=u.id=o.user_id)

#### Scenario: 解析带 CROSS JOIN 的 FROM 子句
- **WHEN** 输入 tokens 对应 "FROM users u CROSS JOIN orders o"
- **THEN** 返回 SelectStatement with one JoinClause(CROSS, TableRef("orders","o"), on_condition=None)

#### Scenario: 解析带 NATURAL JOIN 的 FROM 子句
- **WHEN** 输入 tokens 对应 "FROM users u NATURAL JOIN orders o"
- **THEN** 返回 SelectStatement with one JoinClause(NATURAL, TableRef("orders","o"), on_condition=None)

#### Scenario: 解析多表 JOIN 链
- **WHEN** 输入 tokens 对应 "FROM a JOIN b ON a.id = b.a_id JOIN c ON b.id = c.b_id"
- **THEN** 返回 SelectStatement with two JoinClause entries for b and c

### Requirement: 解析带 USING 的 JOIN 子句
The system SHALL parse JOIN ... USING (column_list) syntax, capturing the USING column list in the JoinClause.

#### Scenario: 解析 USING 单列为连接条件
- **WHEN** 输入 tokens 对应 "FROM users u JOIN orders o USING (user_id)"
- **THEN** 返回 JoinClause with using_columns=["user_id"]

#### Scenario: 解析 USING 多列为连接条件
- **WHEN** 输入 tokens 对应 "FROM t1 JOIN t2 USING (a, b)"
- **THEN** 返回 JoinClause with using_columns=["a", "b"]

### Requirement: 解析带表限定的列引用
The system SHALL parse dot-separated column references (e.g., `u.name`) as ColumnRef nodes with a table qualifier field set.

#### Scenario: 解析带别名的列引用
- **WHEN** 输入 tokens 对应 "u.name"
- **THEN** 返回 ColumnRef(name="name", table="u")

#### Scenario: 解析不带别名的列引用
- **WHEN** 输入 tokens 对应 "name"
- **THEN** 返回 ColumnRef(name="name", table=None)

### Requirement: 解析表别名
The system SHALL parse optional AS aliases for table references in FROM and JOIN clauses, including bare aliases (without AS keyword).

#### Scenario: 解析带 AS 的表别名
- **WHEN** 输入 "users AS u"
- **THEN** 返回 TableRef(name="users", alias="u")

#### Scenario: 解析不带 AS 的表别名
- **WHEN** 输入 "users u"
- **THEN** 返回 TableRef(name="users", alias="u")

#### Scenario: 解析不带别名的表引用
- **WHEN** 输入 "users"
- **THEN** 返回 TableRef(name="users", alias=None)
