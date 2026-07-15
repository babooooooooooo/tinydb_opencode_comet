## Why

tinydb 项目需要一个底层存储引擎，负责数据在内存中的表示、页式管理、缓冲池和磁盘持久化。这是整个数据库的基础层，所有上层功能（SQL 解析、索引、事务）都依赖它。

## What Changes

- 新增类型系统：INT、FLOAT、TEXT、BOOL 的值表示与类型检查
- 新增页式存储引擎：固定大小页（默认 4KB）的分配、读写、回收
- 新增缓冲池（Buffer Pool）：页缓存与 LRU 淘汰策略
- 新增文件持久化：单 `.db` 文件格式（文件头 + 页表 + 数据）
- 新增行存储格式：变长记录的序列化/反序列化

## Capabilities

### New Capabilities
- `type-system`: INT/FLOAT/TEXT/BOOL 类型定义、值表示、类型检查、隐式转换规则
- `page-storage`: 页结构定义、页分配器、空闲页管理、文件读写
- `buffer-pool`: 页缓存、LRU 淘汰、脏页刷盘、固定/释放接口
- `file-format`: 数据库文件格式、文件头元数据、完整性检查
- `row-format`: 行记录序列化/反序列化、变长字段编码、NULL 位图

### Modified Capabilities

（无）

## Impact

- 新增包 `tinydb/storage/`，零外部依赖
- 新增文件格式 `.db`（自定义二进制格式）
- 为 `tinydb-sql`（表管理）和 `tinydb-index-txn`（B-tree 页管理）提供基础存储 API
