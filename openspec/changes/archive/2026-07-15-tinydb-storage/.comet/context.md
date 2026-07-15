# Comet Design Handoff

- Change: tinydb-storage
- Phase: design
- Mode: compact
- Context hash: e006a63ec2de7262b86769d281da76a21fa7ea63555f0c5c974b5b70381c010e

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/tinydb-storage/proposal.md

- Source: openspec/changes/tinydb-storage/proposal.md
- Lines: 1-30
- SHA256: ff56710287c8f484538ac8e99d08df479115ffbd7d8dc79c7b71175164bd3538

```md
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

```

## openspec/changes/tinydb-storage/design.md

- Source: openspec/changes/tinydb-storage/design.md
- Lines: 1-108
- SHA256: ad02ffa439b3cb94f24369f0d126b5a555098de3a06c33f442d4cdf75b3255ce

[TRUNCATED]

```md
## Context

作为 tinydb 项目的底层存储引擎，需要为上层提供可靠的数据持久化能力。本模块是三层中的第一层，所有上层模块（SQL 执行器、B-tree 索引、事务管理器）都通过本模块的 API 读写数据。

当前状态：无现有实现，从零开始。

教学优先原则：代码结构清晰、模块边界分明、关键概念有注释说明。

## Goals / Non-Goals

**Goals:**
- 提供类型安全的值表示与列定义
- 实现页式存储管理，支持固定大小页（默认 4KB）
- 实现 LRU 缓冲池，缓存热数据页
- 实现单文件格式持久化，含文件头元数据
- 提供行记录的序列化/反序列化接口

**Non-Goals:**
- 并发安全（后续 change 处理）
- 页压缩或加密
- 分布式存储
- 跨文件/分片存储

## Decisions

### D1: 类型系统采用 Python dataclass + Enum

| 方案 | 优点 | 缺点 |
|------|------|------|
| Python dataclass + Enum | 类型安全、IDE 友好、教学清晰 | 有一定运行时开销 |
| 纯 dict | 灵活 | 无类型保障、Bug 率高 |
| 第三方库（如 attrs） | 功能丰富 | 额外依赖 |

选择 dataclass + Enum：零依赖、教学清晰、类型检查友好。

支持的类型：`INTEGER`（int）、`FLOAT`（float）、`TEXT`（str）、`BOOLEAN`（bool）。

### D2: 页大小固定 4KB

| 方案 | 优点 | 缺点 |
|------|------|------|
| 固定 4KB | 实现简单、与操作系统页对齐 | 无法适配特殊场景 |
| 可配置 | 灵活 | 增加复杂度 |

选择固定 4KB：教学实现不需要灵活性，且与 OS 内存页对齐有性能优势。

### D3: 缓冲池采用 LRU 策略

| 方案 | 优点 | 缺点 |
|------|------|------|
| LRU | 实现简单、局部性好 | 顺序扫描会污染 |
| LFU | 频率友好 | 实现复杂 |
| Clock | 近似 LRU、开销更低 | 教学不直观 |

选择 LLRU：经典教学选择，代码简洁易理解。

### D4: 文件格式布局

```
┌─────────────────────────────────────────┐
│  File Header (Page 0)                   │
│  ├─ magic: "TINYDB\0" (8 bytes)        │
│  ├─ version: uint32                     │
│  ├─ page_size: uint32                   │
│  ├─ page_count: uint32                  │
│  ├─ free_list_head: uint32              │
│  ├─ table_catalog_root: uint32          │
│  └─ checksum: uint64                    │
├─────────────────────────────────────────┤
│  Table Catalog (Page 1+)                │
│  └─ 表元数据（列定义、索引根页等）       │
├─────────────────────────────────────────┤
│  Data Pages (Page N+)                   │
│  └─ 用户数据（行记录）                   │
├─────────────────────────────────────────┤
│  Index Pages                            │
│  └─ B-tree 节点（后续 change）           │
└─────────────────────────────────────────┘
```


```

Full source: openspec/changes/tinydb-storage/design.md

## openspec/changes/tinydb-storage/tasks.md

- Source: openspec/changes/tinydb-storage/tasks.md
- Lines: 1-50
- SHA256: aa86722930b5cce630d89688b73e00c775538efebdfadbef49f54c5cfd7f82d2

```md
## 1. Setup

- [ ] 1.1 创建项目骨架（pyproject.toml、包结构、__init__.py）
- [ ] 1.2 配置 pytest 测试环境
- [ ] 1.3 定义项目constants（页大小 4096、magic bytes、版本号）

## 2. Type System

- [ ] 2.1 实现 DataType 枚举（INTEGER、FLOAT、TEXT、BOOLEAN）
- [ ] 2.2 实现 ColumnDef 数据类（name、type、nullable、constraints）
- [ ] 2.3 实现类型检查与隐式转换逻辑（validate/convert）
- [ ] 2.4 实现 Value 包装类（含 None/NULL 表示）
- [ ] 2.5 编写 type-system 单元测试

## 3. File Format

- [ ] 3.1 实现 FileHeader 结构（magic、version、page_size 等）
- [ ] 3.2 实现 serialize/deserialize 方法
- [ ] 3.3 实现 Database.open(path) — 创建新库/打开已有库
- [ ] 3.4 实现 Database.close() — 刷盘并关闭文件
- [ ] 3.5 实现完整性校验（checksum 验证）
- [ ] 3.6 编写 file-format 单元测试

## 4. Page Storage

- [ ] 4.1 实现 Page 类（page_id、data、dirty 标志）
- [ ] 4.2 实现 PageAllocator（空闲链表管理）
- [ ] 4.3 实现 read_page / write_page 基本操作
- [ ] 4.4 编写 page-storage 单元测试

## 5. Buffer Pool

- [ ] 5.1 实现 LRU 缓存数据结构（OrderedDict 或双向链表+哈希表）
- [ ] 5.2 实现 BufferPool.get_page(page_id) — 缓存命中/缺页处理
- [ ] 5.3 实现 BufferPool.flush() — 脏页刷盘
- [ ] 5.4 实现 pin/unpin 接口
- [ ] 5.5 编写 buffer-pool 单元测试

## 6. Row Format

- [ ] 6.1 实现 NULL 位图编码/解码
- [ ] 6.2 实现行序列化（serialize_row）
- [ ] 6.3 实现行反序列化（deserialize_row）
- [ ] 6.4 编写 row-format 单元测试

## 7. Integration

- [ ] 7.1 集成所有模块，实现端到端读写
- [ ] 7.2 编写集成测试（创建表、插入行、读取行）
- [ ] 7.3 编写 README 文档说明模块 API

```

## openspec/changes/tinydb-storage/specs/buffer-pool/spec.md

- Source: openspec/changes/tinydb-storage/specs/buffer-pool/spec.md
- Lines: 1-42
- SHA256: ff801171d18b15734e61ad9ebc76fd892ee4e5af9f93c5171ad70befc6fc3563

```md
## ADDED Requirements

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

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-storage/specs/file-format/spec.md

- Source: openspec/changes/tinydb-storage/specs/file-format/spec.md
- Lines: 1-45
- SHA256: 7a6788bdc2ac255c6c8df649a3a0b4d59745b5cf55a8cd1b42437170a8317cec

```md
## ADDED Requirements

### Requirement: 文件格式标识
The system SHALL use a magic bytes "TINYDB\0" at the start of the database file for format identification.

#### Scenario: 打开有效的 .db 文件
- **WHEN** 文件以 "TINYDB\0" 开头
- **THEN** 系统识别为有效的 tinydb 数据库文件

#### Scenario: 打开无效文件
- **WHEN** 文件不以 "TINYDB\0" 开头
- **THEN** 系统拒绝并返回格式错误

### Requirement: 文件头元数据
The system SHALL store page_size, page_count, free_list_head, and version in the file header (Page 0).

#### Scenario: 创建新数据库
- **WHEN** 首次创建 .db 文件
- **THEN** 系统写入正确的文件头元数据，page_count 初始为 1

#### Scenario: 读取元数据
- **WHEN** 打开已有数据库
- **THEN** 系统从 Page 0 读取 page_size、page_count 等元数据

### Requirement: 数据库打开与关闭
The system SHALL provide open(path) and close() methods for database lifecycle management.

#### Scenario: 打开不存在文件
- **WHEN** open() 调用时文件不存在
- **THEN** 系统创建新的空数据库文件

#### Scenario: 关闭时刷盘
- **WHEN** close() 调用
- **THEN** 系统将所有脏页刷盘后再关闭文件句柄

### Requirement: 完整性检查
The system SHALL verify file integrity on open using checksum.

#### Scenario: 文件损坏检测
- **WHEN** 文件 checksum 不匹配
- **THEN** 系统报告文件损坏错误

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-storage/specs/page-storage/spec.md

- Source: openspec/changes/tinydb-storage/specs/page-storage/spec.md
- Lines: 1-45
- SHA256: b421bb4df769eccf28040736ea54cc0701c0199b41f09dc03f9b37027934bffc

```md
## ADDED Requirements

### Requirement: 页大小固定 4KB
The system SHALL use a fixed page size of 4096 bytes.

#### Scenario: 创建新页
- **WHEN** 分配一个新页
- **THEN** 该页恰好占用 4096 字节空间

### Requirement: 页分配与回收
The system SHALL maintain a free list to track available pages and support allocation/deallocation.

#### Scenario: 分配新页
- **WHEN** 空闲链表非空时请求新页
- **THEN** 系统从空闲链表头部取出一页并返回其页号

#### Scenario: 无空闲页时分配
- **WHEN** 空闲链表为空时请求新页
- **THEN** 系统追加新页到文件末尾并返回新页号

#### Scenario: 回收页
- **WHEN** 删除数据导致某页空闲
- **THEN** 系统将该页加入空闲链表头部

### Requirement: Page 基本结构
The system SHALL provide a Page class with page_id, data buffer, and dirty flag.

#### Scenario: 读取页
- **WHEN** 请求读取页号为 N 的页
- **THEN** 系统返回包含该页数据的 Page 对象

#### Scenario: 写入页
- **WHEN** 修改页数据后标记为 dirty
- **THEN** 系统维护 dirty 标志用于后续刷盘

### Requirement: 页读写接口
The system SHALL provide read_page(page_id) and write_page(page_id, data) operations.

#### Scenario: 读取不存在的页
- **WHEN** 请求读取超出文件范围的页号
- **THEN** 系统返回错误

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-storage/specs/row-format/spec.md

- Source: openspec/changes/tinydb-storage/specs/row-format/spec.md
- Lines: 1-45
- SHA256: 97f7d57d153ecaa30956819e014ffd50f4b88e7846e48ff36e9e9137d4ca0be1

```md
## ADDED Requirements

### Requirement: 行序列化
The system SHALL serialize a row (list of values) into bytes using length-prefixed encoding for variable-length types.

#### Scenario: 序列化含 NULL 的行
- **WHEN** 行中某些列为 NULL
- **THEN** 系统使用 NULL 位图标记，不写入实际值

#### Scenario: 序列化全类型行
- **WHEN** 行包含 INT、FLOAT、TEXT、BOOL 各一列
- **THEN** 系统正确序列化每个类型到字节流

### Requirement: 行反序列化
The system SHALL deserialize bytes back into a row (list of values) given a column definition.

#### Scenario: 反序列化有效数据
- **WHEN** 给定的字节流是某行序列化的结果
- **THEN** 系统还原出原始值列表（含正确的 NULL）

#### Scenario: 反序列化空行
- **WHEN** 字节流为空
- **THEN** 系统返回空列表

### Requirement: 变长字段编码
The system SHALL encode variable-length TEXT using a 4-byte length prefix followed by UTF-8 bytes.

#### Scenario: 编码中文文本
- **WHEN** 列值为 UTF-8 中文字符串
- **THEN** 系统正确编码长度并写入字节

### Requirement: NULL 位图
The system SHALL use a bitmap (1 bit per column) to indicate NULL values in the row header.

#### Scenario: 8 列中位图为 1 字节
- **WHEN** 行定义为 8 列
- **THEN** NULL 位图占用 1 字节

#### Scenario: 12 列位图为 2 字节
- **WHEN** 行定义为 12 列
- **THEN** NULL 位图占用 2 字节

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-storage/specs/type-system/spec.md

- Source: openspec/changes/tinydb-storage/specs/type-system/spec.md
- Lines: 1-41
- SHA256: c44d5aae1a347e57bcc1d6050aedee7589530fb6d5ce6bff1cb4ce20547d8b58

```md
## ADDED Requirements

### Requirement: 类型系统支持四种基本数据类型
The system SHALL support INTEGER, FLOAT, TEXT, and BOOLEAN data types with proper type checking.

#### Scenario: 创建整数列
- **WHEN** 定义列类型为 INTEGER
- **THEN** 系统接受 int 值，拒绝非 int 值并返回 TypeError

#### Scenario: 创建文本列
- **WHEN** 定义列类型为 TEXT
- **THEN** 系统接受 str 值，拒绝非 str 值并返回 TypeError

### Requirement: 类型检查在运行时执行
The system SHALL validate values against column types at write time (INSERT/UPDATE).

#### Scenario: 插入整数到浮点列
- **WHEN** 向 FLOAT 列插入 INTEGER 值
- **THEN** 系统隐式转换为 FLOAT 类型成功

#### Scenario: 插入字符串到整数列
- **WHEN** 向 INTEGER 列插入 TEXT 值
- **THEN** 系统拒绝并返回类型不匹配错误

### Requirement: NULL 值表示
The system SHALL support NULL values through a NULL sentinel in the type system.

#### Scenario: 查询含 NULL 的行
- **WHEN** 某行某列值为 NULL
- **THEN** 系统正确返回 NULL 而非空字符串或 0

### Requirement: ColumnDef 定义
The system SHALL provide a ColumnDef structure containing name, type, nullable, and constraints.

#### Scenario: 定义 NOT NULL 列
- **WHEN** 创建 ColumnDef 时设置 nullable=False
- **THEN** 系统拒绝向该列插入 NULL 值

## MODIFIED Requirements

（无）

```
