# concurrency-control Specification

## Purpose
Provides concurrency control mechanisms including lock management (shared/exclusive locks, lock compatibility, upgrades, timeouts), MVCC version chains with snapshot visibility, deadlock detection via wait-for graph, and configurable isolation levels to support multiple concurrent transactions.

## Requirements

### Requirement: LockManager Shared/Exclusive Locks
The system SHALL provide a LockManager that supports Shared (S) and Exclusive (X) locks at page granularity. S locks allow concurrent reads; X locks allow exclusive writes.

#### Scenario: Shared lock allows concurrent reads
- **WHEN** transaction T1 acquires a Shared lock on page P
- **AND** transaction T2 requests a Shared lock on page P
- **THEN** T2 is granted the lock immediately

#### Scenario: Exclusive lock blocks other transactions
- **WHEN** transaction T1 acquires an Exclusive lock on page P
- **AND** transaction T2 requests any lock on page P
- **THEN** T2 waits until T1 releases the lock

### Requirement: Lock Compatibility Matrix
The system SHALL enforce the following lock compatibility matrix: S-S compatible, S-X incompatible, X-S incompatible, X-X incompatible.

#### Scenario: Incompatible lock request waits
- **WHEN** transaction T1 holds an Exclusive lock on page P
- **AND** transaction T2 requests a Shared lock on page P
- **THEN** T2's request is queued and not granted until T1 releases

### Requirement: Lock Timeout
The system SHALL enforce a configurable timeout (default 5 seconds) for lock acquisition. If a lock cannot be acquired within the timeout, the requesting transaction is aborted.

#### Scenario: Lock acquisition times out
- **WHEN** transaction T1 holds an Exclusive lock on page P
- **AND** transaction T2 waits for a lock on page P for more than 5 seconds
- **THEN** T2 is aborted with a timeout error

### Requirement: Shared-to-Exclusive Lock Upgrade
The system SHALL support upgrading a Shared lock to an Exclusive lock (S→X upgrade) for a transaction that already holds a Shared lock on the page.

#### Scenario: Upgrade succeeds when no other Shared locks exist
- **WHEN** transaction T1 holds a Shared lock on page P and no other transaction holds a lock on P
- **AND** T1 requests an upgrade to Exclusive on page P
- **THEN** the upgrade is granted immediately

#### Scenario: Upgrade blocks when other Shared locks exist
- **WHEN** transaction T1 holds a Shared lock on page P
- **AND** transaction T2 also holds a Shared lock on page P
- **AND** T1 requests an upgrade to Exclusive on page P
- **THEN** T1 waits until T2 releases its Shared lock

### Requirement: MVCC Version Chain
The system SHALL maintain a version chain per page, ordered by creator txn_id in descending order. Each version records the creating txn_id and the deleting txn_id (or None if not deleted).

#### Scenario: New version is prepended to chain
- **WHEN** transaction T2 writes to page P that already has a version created by T1
- **THEN** the new version created by T2 is placed at the head of the version chain

### Requirement: MVCC Snapshot Visibility
The system SHALL determine version visibility using a snapshot: a version is visible if its creator txn_id is in the snapshot's active transactions AND its deleter txn_id is NOT in the snapshot's active transactions.

#### Scenario: Transaction sees committed data from earlier transactions
- **WHEN** transaction T2 starts with snapshot containing active txn_ids = {T1}
- **AND** page P has a version created by T1 with no deleter
- **THEN** T2 sees the version created by T1

#### Scenario: Transaction does not see uncommitted data
- **WHEN** transaction T2 starts with snapshot containing active txn_ids = {T1}
- **AND** transaction T3 (not in snapshot) has created a new version of page P
- **THEN** T2 does not see the version created by T3

### Requirement: MVCC Garbage Collection
The system SHALL provide a GC operation that removes versions not referenced by any active transaction's snapshot (i.e., versions whose creator has committed and no active transaction can see them).

#### Scenario: Old versions are collected
- **WHEN** garbage collection runs
- **AND** a version's creator txn_id has committed
- **AND** no active transaction's snapshot includes the creator txn_id in its active set
- **THEN** the version is removed from the chain

### Requirement: Deadlock Detection via Wait-For Graph
The system SHALL maintain a wait-for graph where edges represent "transaction A waits for transaction B". The system SHALL detect cycles in this graph each time a lock wait edge is added.

#### Scenario: Deadlock cycle is detected
- **WHEN** transaction T1 waits for a lock held by T2
- **AND** transaction T2 waits for a lock held by T1
- **THEN** a cycle [T1, T2] is detected and one transaction is aborted

### Requirement: Deadlock Victim Selection
When a deadlock cycle is detected, the system SHALL select the youngest transaction (the one with the latest start time) as the victim to abort, minimizing rollback cost.

#### Scenario: Youngest transaction is chosen as victim
- **WHEN** a deadlock cycle involves transactions T1 (started at time 100) and T2 (started at time 200)
- **THEN** T2 is selected as the victim and aborted

### Requirement: Isolation Levels
The system SHALL support four isolation levels: READ UNCOMMITTED, READ COMMITTED, READ REPEATABLE (default), and SERIALIZABLE. The default isolation level SHALL be REPEATABLE READ.

#### Scenario: Default isolation level is REPEATABLE READ
- **WHEN** a transaction begins without specifying an isolation level
- **THEN** it operates at REPEATABLE READ

#### Scenario: Serializable isolation uses two-phase locking
- **WHEN** a transaction operates at SERIALIZABLE isolation level
- **THEN** it acquires all locks before executing and holds them until commit or rollback

### Requirement: Multi-Transaction Support
The system SHALL support multiple concurrent transactions, each with its own snapshot, lock set, and isolation level settings.

#### Scenario: Multiple transactions execute concurrently
- **WHEN** transaction T1 and transaction T2 begin simultaneously
- **THEN** each receives a unique txn_id, its own snapshot, and independent lock management
