# buffer-pool Specification

## ADDED Requirements

### Requirement: Page Latch Integration
The buffer pool SHALL integrate with the LockManager so that pinning a page acquires the appropriate lock (Shared or Exclusive) and unpinning releases it.

#### Scenario: Pin acquires lock
- **WHEN** a transaction pins a page in Shared mode
- **THEN** the LockManager acquires a Shared lock on that page for the transaction

#### Scenario: Unpin releases lock
- **WHEN** a transaction unpins a page
- **THEN** the LockManager releases the corresponding lock on that page

### Requirement: MVCC Version Routing on Page Access
The buffer pool SHALL route read requests through MVCC visibility checks, returning the correct version of a page based on the requesting transaction's snapshot rather than always returning the latest version.

#### Scenario: Read returns visible version
- **WHEN** transaction T1 requests a page where a newer version exists but was created by an active transaction not in T1's snapshot
- **THEN** T1 receives the older visible version of the page

#### Scenario: Read returns latest committed version
- **WHEN** transaction T1 requests a page where the latest version was committed before T1 began
- **THEN** T1 receives the latest version of the page
