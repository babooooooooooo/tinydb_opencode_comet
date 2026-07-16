# buffer-pool Specification

## Purpose
Provides an LRU buffer pool for caching pages in memory, with dirty page tracking, pin/unpin for active page protection, and integration with the LockManager and MVCC for concurrent transaction support.

## Requirements

### Requirement: LRU 缓冲池
The system SHALL implement a buffer pool with LRU eviction policy, default capacity of 100 pages.

#### Scenario: 缓冲池未满
- **WHEN** 请求一页且缓冲池未满
- **THEN** 系统加载该页到缓冲池并返回，不触发淘汰

#### Scenario: 缓冲池已满时加载新页
- **WHEN** 请求一页且缓冲池已满
- **THEN** 系统淘汰最久未使用的页并加载新页

#### Scenario: 访问已缓存的页
- **WHEN** 请求已在缓冲池中的页
- **THEN** 系统直接返回并将该页标记为最近使用

### Requirement: 脏页管理
The system SHALL track dirty pages and provide a flush operation to write dirty pages to disk.

#### Scenario: 脏页刷盘
- **WHEN** 调用 flush 操作
- **THEN** 所有脏页写入磁盘并清除 dirty 标志

#### Scenario: 淘汰脏页
- **WHEN** LRU 淘汰选中了一个脏页
- **THEN** 系统先将其刷盘再淘汰

### Requirement: 页固定（Pin/Unpin）
The system SHALL support pinning pages to prevent eviction during active use.

#### Scenario: 固定页不被淘汰
- **WHEN** 某页被 pin 住且 LRU 需要淘汰
- **THEN** 系统跳过该页选择其他页淘汰

#### Scenario: 解固定后恢复正常
- **WHEN** unpin 一个页后缓冲池已满
- **THEN** 该页恢复为可淘汰状态

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
