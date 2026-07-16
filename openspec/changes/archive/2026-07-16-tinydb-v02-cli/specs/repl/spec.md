# repl Specification

## ADDED Requirements

### Requirement: Integrated Syntax Highlighter
The REPL SHALL integrate the `SQLHighlighter` component so that all SQL input and output in the REPL session is displayed with syntax coloring.

#### Scenario: Highlight SQL in REPL session
- **WHEN** the user runs the REPL and enters a SQL statement
- **THEN** the statement is highlighted before execution using the SQLHighlighter

---

### Requirement: Integrated Auto-Completer
The REPL SHALL integrate the `SQLCompleter` component and register it with readline so that TAB keypresses trigger context-aware completion.

#### Scenario: TAB completion in REPL
- **WHEN** the user types a partial keyword and presses TAB in the REPL
- **THEN** readline invokes the SQLCompleter to produce candidate completions

---

### Requirement: Meta-Commands for CLI Enhancements
The REPL SHALL dispatch dot-prefixed meta-commands to the `CommandHandler`, supporting `.explain`, `.import`, `.dump`, and `.timing` in addition to existing commands (`.exit`, `.quit`, `.tables`, `.schema`, `.help`).

#### Scenario: Dispatch .explain command
- **WHEN** the user inputs ".explain SELECT * FROM users"
- **THEN** the REPL routes the command to CommandHandler and displays the formatted plan

#### Scenario: Dispatch .import command
- **WHEN** the user inputs ".import users data.csv"
- **THEN** the REPL routes the command to CommandHandler and displays the import result

---

### Requirement: Multi-Line Enhancement
The REPL SHALL use an improved multi-line input strategy that checks bracket balance and semicolon termination before executing, displaying a `.. ` continuation prompt for incomplete statements.

#### Scenario: Continuation prompt for incomplete input
- **WHEN** the user enters a line with unclosed parentheses but no semicolon
- **THEN** the REPL displays ".. " and waits for additional input lines

#### Scenario: Execute complete multi-line statement
- **WHEN** the user's accumulated input has balanced brackets and ends with ";"
- **THEN** the REPL executes the full statement as a single SQL command

---

### Requirement: Query Timing Integration
The REPLACE SHALL respect the `.timing` toggle so that when timing is enabled, each SQL execution result is followed by the elapsed execution time.

#### Scenario: Display timing after execution
- **WHEN** `.timing on` has been set and the user executes a SQL statement
- **THEN** the REPL prints the result followed by "Time: X.XX ms"
