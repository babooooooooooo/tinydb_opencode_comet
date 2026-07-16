# transaction Specification

## ADDED Requirements

### Requirement: Multi-Transaction Dictionary
The system SHALL support multiple concurrent active transactions via a transaction dictionary mapping txn_id to Transaction objects, replacing the single `_active_txn` variable.

#### Scenario: Multiple transactions begin concurrently
- **WHEN** two transactions begin simultaneously
- **THEN** each receives a unique txn_id and is stored in the active transactions dictionary

#### Scenario: Transaction is removed from dictionary after commit
- **WHEN** a transaction commits
- **THEN** its entry is removed from the active transactions dictionary

### Requirement: Transaction Begin API
The system SHALL provide a `begin()` method that creates a new transaction, assigns a unique txn_id, captures the initial snapshot, and adds it to the active transactions dictionary.

#### Scenario: Begin a new transaction
- **WHEN** `begin()` is called
- **THEN** a new transaction with a unique txn_id is created, a snapshot is captured, and it is added to the active dictionary

### Requirement: Transaction Commit API
The system SHALL provide a `commit(txn_id)` method that finalizes a transaction's changes, releases all locks held by the transaction, and removes it from the active transactions dictionary.

#### Scenario: Commit a transaction
- **WHEN** `commit(txn_id)` is called for an active transaction
- **THEN** all changes are persisted, all locks are released, and the transaction is removed from the active dictionary

### Requirement: Transaction Rollback API
The system SHALL provide a `rollback(txn_id)` method that undoes all changes made by the transaction, releases all locks, and removes the transaction from the active transactions dictionary.

#### Scenario: Rollback a transaction
- **WHEN** `rollback(txn_id)` is called for an active transaction
- **THEN** all changes are undone, all locks are released, and the transaction is removed from the active dictionary

### Requirement: Per-Transaction Snapshot
The system SHALL capture a snapshot at transaction begin time that records the set of active transaction txn_ids for MVCC visibility checks throughout the transaction's lifetime.

#### Scenario: Snapshot captures active transactions at begin time
- **WHEN** transaction T2 begins while T1 is active
- **THEN** T2's snapshot includes T1 in its active set, and T2 sees T1's committed changes made after T2's begin
