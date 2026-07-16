# join Specification

## ADDED Requirements

### Requirement: INNER JOIN
The system SHALL support INNER JOIN ... ON ... that returns only rows where the join condition is satisfied in both tables.

#### Scenario: Basic INNER JOIN
- **WHEN** executing `SELECT u.name, o.amount FROM users u INNER JOIN orders o ON u.id = o.user_id`
- **THEN** returns only users who have at least one order, with matched user-name and order-amount pairs

#### Scenario: INNER JOIN with no matches
- **WHEN** the ON condition matches no rows between the two tables
- **THEN** returns an empty result set

### Requirement: LEFT OUTER JOIN
The system SHALL support LEFT [OUTER] JOIN ... ON ... that returns all rows from the left table and matched rows from the right table, with NULLs for non-matching right rows.

#### Scenario: LEFT JOIN with unmatched left rows
- **WHEN** executing `SELECT u.name, o.amount FROM users u LEFT JOIN orders o ON u.id = o.user_id`
- **THEN** returns all users; users without orders have NULL in the amount column

### Requirement: RIGHT OUTER JOIN
The system SHALL support RIGHT [OUTER] JOIN ... ON ... that returns all rows from the right table and matched rows from the left table, with NULLs for non-matching left rows.

#### Scenario: RIGHT JOIN with unmatched right rows
- **WHEN** executing `SELECT u.name, o.amount FROM users u RIGHT JOIN orders o ON u.id = o.user_id`
- **THEN** returns all orders; orders without a matching user have NULL in the name column

### Requirement: FULL OUTER JOIN
The system SHALL support FULL [OUTER] JOIN ... ON ... that returns all rows from both tables, with NULLs for non-matching sides.

#### Scenario: FULL JOIN returns all rows from both sides
- **WHEN** executing `SELECT u.name, o.amount FROM users u FULL OUTER JOIN orders o ON u.id = o.user_id`
- **THEN** returns all users and all orders; unmatched rows from either side have NULLs for the other side's columns

### Requirement: CROSS JOIN
The system SHALL support CROSS JOIN that produces the Cartesian product of both tables without requiring an ON condition.

#### Scenario: CROSS JOIN produces Cartesian product
- **WHEN** executing `SELECT u.name, p.product FROM users u CROSS JOIN products p`
- **THEN** returns every combination of user rows and product rows (count = users_count * products_count)

### Requirement: NATURAL JOIN
The system SHALL support NATURAL JOIN that automatically matches columns with the same name in both tables as the join condition.

#### Scenario: NATURAL JOIN matches same-named columns
- **WHEN** executing `SELECT * FROM users u NATURAL JOIN orders o` and both tables have an `id` column
- **THEN** joins on the `id` column automatically without requiring an explicit ON clause

### Requirement: SELF JOIN
The system SHALL support SELF JOIN where a table is joined with itself using different aliases.

#### Scenario: SELF JOIN with aliases
- **WHEN** executing `SELECT e.name, m.name FROM employees e JOIN employees m ON e.manager_id = m.id`
- **THEN** returns each employee name paired with their manager's manager name

### Requirement: Nested Loop Join Algorithm
The system SHALL implement a Nested Loop Join algorithm that iterates over the left table and for each row scans the right table to find matches.

#### Scenario: Nested Loop on small datasets
- **WHEN** the optimizer chooses Nested Loop Join for small tables
- **THEN** correctly returns all matching rows by brute-force scanning the right table for each left row

### Requirement: Hash Join Algorithm
The system SHALL implement a Hash Join algorithm that builds a hash table from the right table and probes it with left table rows, supporting only equality conditions.

#### Scenario: Hash Join on large equi-join
- **WHEN** the optimizer chooses Hash Join for a large table with an equality condition `ON a.id = b.id`
- **THEN** builds a hash table from the right table and probes with left rows, returning all matches

### Requirement: Sort-Merge Join Algorithm
The system SHALL implement a Sort-Merge Join algorithm that sorts both tables on the join key and then merges them.

#### Scenario: Sort-Merge on pre-sorted data
- **WHEN** the optimizer chooses Sort-Merge Join for tables already sorted on the join key
- **THEN** performs a merge pass to find matching rows efficiently in a single scan
