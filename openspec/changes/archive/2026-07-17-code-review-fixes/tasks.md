# Tasks

## Phase 1: Correctness Fixes (CRITICAL)

- [x] T1: Fix DmlOperator._execute_update indentation bug
- [x] T2: Extract _JoinBase class to eliminate JOIN operator code duplication
- [x] T3: Clean up duplicate `result = {}` assignments

## Phase 2: Simplification & Unification (HIGH)

- [x] T4: Remove `_is_complex_select` string matching, route all SELECT through SQL engine
- [x] T5: Remove unused regex-based query methods from database.py

## Phase 3: Cleanup (MEDIUM)

- [x] T6: Add constants for AggregateOperator function names
- [x] T7: Ensure all tests pass
