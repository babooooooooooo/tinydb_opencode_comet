# buffer-pool Specification

## Purpose
TBD - created by archiving change tinydb-storage. Update Purpose after archive.
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

