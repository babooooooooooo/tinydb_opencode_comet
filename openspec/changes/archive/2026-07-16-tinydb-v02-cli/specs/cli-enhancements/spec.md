# cli-enhancements Specification

## ADDED Requirements

### Requirement: Syntax Highlighting
The system SHALL provide SQL syntax highlighting in the REPL using the `pygments` library, coloring keywords blue, strings green, numbers yellow, and comments gray. When `pygments` is unavailable, the system SHALL gracefully degrade by displaying uncolored text without raising errors.

#### Scenario: Highlighting with pygments available
- **WHEN** the user enters valid SQL in the REPL
- **THEN** the displayed input is colored with ANSI escape codes matching the color scheme

#### Scenario: Graceful degradation without pygments
- **WHEN** `pygments` is not installed and the user enters SQL
- **THEN** the REPL displays the raw string without color and does not crash

---

### Requirement: Auto-Completion
The system SHALL provide context-aware TAB completion for SQL keywords, table names, and column names. At line start or after `;`, keywords are prioritized. After `FROM`, `JOIN`, `INTO`, or `UPDATE`, table names are completed. After `SELECT` or `.`, column names are completed.

#### Scenario: Keyword completion at line start
- **WHEN** the user types "SEL" and presses TAB
- **THEN** the input completes to "SELECT"

#### Scenario: Table name completion after FROM
- **WHEN** the user types "SELECT * FROM " and presses TAB
- **THEN** a list of available table names is shown as completion candidates

#### Scenario: Column name completion after SELECT
- **WHEN** the user types "SELECT " and presses TAB
- **THEN** a list of column names for the default table is shown as completion candidates

---

### Requirement: .explain Command
The system SHALL support a `.explain <SQL>` command that displays the execution plan as a formatted tree using box-drawing characters, showing operators such as Project, Filter, Scan, and Join.

#### Scenario: Explain a SELECT query
- **WHEN** the user inputs ".explain SELECT name FROM users WHERE id > 10"
- **THEN** a formatted execution plan tree is displayed showing Project, Filter, and Scan nodes

---

### Requirement: .import Command
The system SHALL support a `.import <table> <filepath>` command that imports data from CSV or JSON files into the specified table. CSV files use the first row as column names. JSON files use an array of objects format. The import is wrapped in a transaction, and the command reports the number of rows imported.

#### Scenario: Import CSV file
- **WHEN** the user inputs ".import users data/users.csv"
- **THEN** the CSV is parsed, rows are inserted into the `users` table, and a row count message is displayed

#### Scenario: Import JSON file
- **WHEN** the user inputs ".import orders data/orders.json"
- **THEN** the JSON array is parsed, objects are inserted into the `orders` table, and a row count message is displayed

---

### Requirement: .dump Command
The system SHALL support a `.dump <table> [filepath]` command that exports all rows from the specified table. When no filepath is given, output goes to stdout. The format matches the `.import` structure (CSV/JSON).

#### Scenario: Dump to stdout
- **WHEN** the user inputs ".dump users"
- **THEN** the full contents of the `users` table are displayed on stdout in CSV format

#### Scenario: Dump to file
- **WHEN** the user inputs ".dump users /tmp/users_export.csv"
- **THEN** the full contents of the `users` table are written to the specified file

---

### Requirement: .timing Command
The system SHALL support a `.timing on|off` command that toggles query execution timing display. When enabled, each SQL statement is followed by a `Time: X.XX ms` line measured with nanosecond precision.

#### Scenario: Enable timing
- **WHEN** the user inputs ".timing on" and then executes a SQL statement
- **THEN** the result is followed by a line showing the elapsed time in milliseconds

#### Scenario: Disable timing
- **WHEN** the user inputs ".timing off"
- **THEN** subsequent SQL statements no longer display timing information

---

### Requirement: Multi-Line Editing
The system SHALL support multi-line SQL editing with bracket matching and a continuation prompt (`.. `). A statement is considered complete when all brackets (`()`, `[]`, `{}`) are balanced and the text ends with a semicolon.

#### Scenario: Incomplete statement with unclosed bracket
- **WHEN** the user inserts "SELECT * FROM (" without a closing bracket or semicolon
- **THEN** the REPL shows the continuation prompt and waits for more input

#### Scenario: Statement completion with balanced brackets
- **WHEN** the user completes the input with a closing bracket and semicolon
- **THEN** the full multi-line statement is executed

---

### Requirement: Emacs Keybindings
The system SHALL support standard Emacs readline keybindings: Ctrl-A (beginning of line), Ctrl-E (end of line), Ctrl-W (delete word backward), Ctrl-K (kill to end of line), and Ctrl-U (kill entire line).

#### Scenario: Move to beginning of line
- **WHEN** the user presses Ctrl-A during input
- **THEN** the cursor moves to the beginning of the current line

#### Scenario: Kill to end of line
- **WHEN** the user presses Ctrl-K during input
- **THEN** all text after the cursor is deleted and available for yanking
