# Code Review Fixes

## Motivation

Code review identified multiple issues affecting correctness, maintainability, and simplicity. This change consolidates the high-priority fixes.

## Goals

1. Fix UPDATE statement indentation bug (NameError)
2. Eliminate 175+ lines of duplicated code across three JOIN operators
3. Remove fragile string-matching heuristic in `_is_complex_select`
4. Clean up dead code and redundant assignments
5. Unify expression evaluation in `_eval_where`

## Scope

- `tinydb/sql/executor.py` — JOIN deduplication, DmlOperator indentation fix, dead code cleanup
- `tinydb/database.py` — unify execution path, remove string-matching routing
- No new features, architecture changes, or API changes
