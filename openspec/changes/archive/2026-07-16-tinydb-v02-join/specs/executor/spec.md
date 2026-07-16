# executor Specification

## ADDED Requirements

### Requirement: NestedLoopJoinOperator
The system SHALL provide a NestedLoopJoinOperator that iterates each row from the left input and for each row scans the entire right input, yielding combined rows that satisfy the ON condition. For LEFT/FULL JOIN, unmatched left rows are yielded with NULL right columns. For RIGHT/FULL JOIN, unmatched right rows are yielded with NULL left columns.

#### Scenario: INNER JOIN via Nested Loop
- **WHEN** NestedLoopJoinOperator with join_type="INNER" and a valid ON condition receives left and right inputs
- **THEN** yields only combined rows where the ON condition evaluates to True

#### Scenario: LEFT JOIN fills NULLs for unmatched left rows
- **WHEN** NestedLoopJoinOperator with join_type="LEFT" receives a left row that matches no right row
- **THEN** yields the left row combined with NULL values for all right columns

#### Scenario: RIGHT JOIN fills NULLs for unmatched right rows
- **WHEN** NestedLoopJoinOperator with join_type="RIGHT" receives a right row that matches no left row
- **THEN** yields the right row combined with NULL values for all left columns

#### Scenario: CROSS JOIN has no ON condition
- **WHEN** NestedLoopJoinOperator with join_type="CROSS" and on_condition=None receives inputs
- **THEN** yields the Cartesian product of left and right inputs

### Requirement: HashJoinOperator
The system SHALL provide a HashJoinOperator that builds a hash table from the right input keyed on the join column, then probes the hash table with each left input row. It supports only equality join conditions.

#### Scenario: Hash Join returns matching rows
- **WHEN** HashJoinOperator with an equality ON condition receives left and right inputs
- **THEN** yields all combined rows where left.key == right.key

#### Scenario: Hash Join with no matches
- **WHEN** HashJoinOperator receives inputs where no keys match
- **THEN** yields no rows

### Requirement: SortMergeJoinOperator
The system SHALL provide a SortMergeJoinOperator that sorts both inputs on the join key and performs a merge pass to find matching rows. It supports equality join conditions and handles duplicate keys.

#### Scenario: Sort-Merge Join returns sorted matching rows
- **WHEN** SortMergeJoinOperator with an equality ON condition receives left and right inputs
- **THEN** yields all combined rows where left.key == right.key, with output sorted by the join key

#### Scenario: Sort-Merge Join handles duplicate keys
- **WHEN** SortMergeJoinOperator receives inputs where the join key has duplicate values on either side
- **THEN** yields the Cartesian product of matching duplicate groups

### Requirement: JoinOperator 列名冲突处理
The system SHALL handle column name conflicts when combining rows from two tables: if both tables have the same column name (excluding the join key in INNER JOIN), the output uses `{alias}_{column}` format to disambiguate.

#### Scenario: 同名列冲突时加别名前缀
- **WHEN** both left and right tables have a column named "name" and the join is not an equi-join on "name"
- **THEN** the output row contains "u_name" and "o_name" (using table aliases) instead of duplicate "name" keys

#### Scenario: 连接键列在 INNER JOIN 中只保留一份
- **WHEN** the join condition is `ON a.id = b.id` in an INNER JOIN
- **THEN** the output row contains a single "id" column
