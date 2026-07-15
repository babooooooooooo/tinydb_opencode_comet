---
comet_change: tinydb-storage
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-15-tinydb-storage
status: final
---

# tinydb-storage 技术设计文档

> 创建日期: 2026-07-15
> 对应 Change: tinydb-storage
> 上游 proposal: openspec/changes/tinydb-storage/proposal.md
> 上游 specs: openspec/changes/tinydb-storage/specs/

---

## 1. Context

### 1.1 项目背景

tinydb 是一个从零构建的 Python 嵌入式关系型数据库，以**教学优先**的方式深入理解数据库核心原理。`tinydb-storage` 是三层架构中的底层——存储引擎，负责所有数据的内存表示、页式管理、缓冲池和磁盘持久化。

### 1.2 上层依赖

本模块是以下 change 的基础依赖：
- `tinydb-sql`: 通过 Table API 执行 DDL/DML
- `tinydb-index-txn`: 通过 Page API 管理 B-tree 节点

### 1.3 设计原则

- **教学优先**: 代码结构清晰、模块边界分明、关键概念有注释
- **零外部依赖**: 仅使用 Python 3.10+ 标准库
- **经典模型**: 复用 SQLite/PostgreSQL 中经过验证的设计（Slotted Page、自描述 Catalog）

---

## 2. Architecture

### 2.1 模块总览

```
                    ┌─────────────────────────────────┐
                    │       SQL Engine (上层)          │
                    └───────────────┬─────────────────┘
                                    │ Table API
                                    ▼
┌───────────────────────────────────────────────────────────┐
                    │     Storage Engine          │
                    │                             │
 ┌──────────┐  ┌────┴─────┐  ┌──────────────┐  ┌─────────┐
 │ Catalog  │  │  Table   │  │  BufferPool  │  │  File   │
 │ (元数据   │  │ Manager  │  │  (LRU缓存)   │  │ Manager │
 │  管理)   │  │ (CRUD    │  │             │  │ (文件   │
 └────┬─────┘  │  操作)   │  └──────┬──────┘  │  读写)  │
      │        └────┬─────┘         │         └────┬────┘
      │             │               │              │
      └─────────────┴───────────────┴──────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │         .db 文件               │
                    │  [Header|Catalog|Data Pages]  │
                    └───────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| TypeSystem | `types.py` | DataType 枚举、ColumnDef dataclass、类型检查/转换 |
| RowFormat | `row_format.py` | NULL 位图、行序列化/反序列化 |
| Page | `page.py` | Slotted Page 数据结构、头部解析、slot 管理 |
| FileManager | `file_manager.py` | 文件打开/关闭、页读写、空闲页分配器 |
| BufferPool | `buffer_pool.py` | LRU 页缓存、脏页管理、pin/unpin |
| Catalog | `catalog.py` | 系统目录表、表元数据加载/保存 |
| Table | `table.py` | 表级 CRUD API（insert/scan/get/delete/update） |

---

## 3. TypeSystem

### 3.1 数据类型

```python
class DataType(Enum):
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
```

### 3.2 列定义

```python
@dataclass
class ColumnDef:
    name: str
    data_type: DataType
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
```

### 3.3 类型检查规则

| 目标类型 | 允许的源类型 | 行为 |
|----------|-------------|------|
| INTEGER | int | 直接接受 |
| INTEGER | float | 拒绝（不隐式截断） |
| FLOAT | int | 隐式转换 float(int) |
| FLOAT | float | 直接接受 |
| TEXT | str | 直接接受 |
| BOOLEAN | bool | 直接接受 |
| any | None | 仅当 nullable=True |

---

## 4. Page（Slotted Page）

### 4.1 页布局

```
┌─────────────────────────────────────────────────────┐
│  Page Header (32 bytes)                             │
│  ├─ page_id:        uint32                          │
│  ├─ page_type:      uint8  (DATA=1/CATALOG=2/INDEX=3)│
│  ├─ slot_count:     uint16                          │
│  ├─ free_space:     uint16                          │
│  ├─ free_offset:    uint16                          │
│  ├─ next_page_id:   uint32                          │
│  └─ flags:          uint8                           │
├─────────────────────────────────────────────────────┤
│  Slot Array (每个 slot 4 bytes: offset+length)       │
│  ├─ slot[0]: (offset: uint16, length: uint16)       │
│  ├─ slot[1]: (offset: uint16, length: uint16)       │
│  ├─ ...                                             │
├─────────────────────────────────────────────────────┤
│  Free Space                                         │
│  ◄── free_offset ──►                               │
├─────────────────────────────────────────────────────┤
│  Row Data (从页底向上增长)                           │
│  row_n ┃ row_n-1 ┃ ... ┃ row_1                     │
───────────────────────────────────────────────────────
```

### 4.2 关键常量

```python
PAGE_SIZE = 4096
PAGE_HEADER_SIZE = 32
SLOT_SIZE = 4
MAX_FREE_SPACE = PAGE_SIZE - PAGE_HEADER_SIZE
```

### 4.3 Page 类型

```python
class PageType(Enum):
    DATA = 1     # 用户数据页
    CATALOG = 2  # 目录表页
    INDEX = 3    # B-tree 节点页（后续 change）
```

### 4.4 RowId

```python
@dataclass(frozen=True)
class RowId:
    page_id: int
    slot_index: int
```

---

## 5. RowFormat

### 5.1 行编码格式

```
┌─────────────────────────────────────────┐
│  Header                                 │
│  ├─ null_bitmap: ceil(n/8) bytes       │
│  ├─ num_columns: uint16                │
├─────────────────────────────────────────┤
│  Body (按列顺序)                        │
│  ├─ INTEGER: 8 bytes (int64)           │
│  ├─ FLOAT:   8 bytes (double)          │
│  ├─ BOOLEAN: 1 byte                    │
│  └─ TEXT:    4 bytes length + UTF-8    │
└─────────────────────────────────────────┘
```

### 5.2 接口

```python
def serialize_row(values: list, columns: list[ColumnDef]) -> bytes
def deserialize_row(data: bytes, columns: list[ColumnDef]) -> list
def null_bitmap(NULLs: list[bool]) -> bytes
```

---

## 6. FileManager

### 6.1 文件布局

```
.db 文件:

┌───────────────────────────────────────────────────────┐
│  Page 0: File Header                                  │
│  ├─ magic:         b"TINYDB\0"  (8 bytes)            │
│  ├─ version:       uint32   (1)                      │
│  ├─ page_size:     uint32   (4096)                   │
│  ├─ page_count:    uint32                            │
│  ├─ free_list_head: uint32                           │
│  ├─ catalog_root:  uint32                            │
│  └─ checksum:      uint64   (CRC32)                  │
├───────────────────────────────────────────────────────┤
│  Page 1..N: Catalog 表 (tinydb_master)               │
├───────────────────────────────────────────────────────┤
│  Page N+1..M: 用户数据页                              │
├───────────────────────────────────────────────────────┤
│  末尾: 空闲页 (通过 free_list_head 串联)              │
└───────────────────────────────────────────────────────┘
```

### 6.2 接口

```python
class FileManager:
    def open(self, path: str) -> None
    def close(self) -> None
    def read_page(self, page_id: int) -> Page
    def write_page(self, page_id: int, data: bytes) -> None
    def alloc_page(self) -> int
    def free_page(self, page_id: int) -> None
```

---

## 7. BufferPool

### 7.1 双视角 LRU 实现

```
┌──────────────────────────────────────────────────┐
│               OrderedDict 层                      │
│                                                    │
│   get(page_id):                                   │
│     → cache[page_id].page                         │
│     → OrderedDict.move_to_end(page_id)            │
│     → 同时 doubly_linked_list.move_to_head(node)  │
│                                                    │
│   put(page_id, page):                             │
│     → if full:                                    │
│         victim = doubly_linked_list.remove_tail()  │
│         if victim.dirty: flush(victim)            │
│         del cache[victim.page_id]                 │
│     → cache[page_id] = Node(page)                 │
│     → doubly_linked_list.insert_head(node)        │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│            双向链表层 (教学展示)                   │
│                                                    │
│   HEAD ⟺ Node_A ⟺ Node_B ⟺ ... ⟺ TAIL           │
│  (recent)                        (oldest)         │
│                                                    │
│   move_to_head(node): O(1)                        │
│   remove_tail(): O(1)                             │
│   insert_head(node): O(1)                         │
└──────────────────────────────────────────────────┘
```

### 7.2 Node 结构

```python
class Node:
    page_id: int
    page: Page
    prev: Node | None
    next: Node | None
    ref_count: int = 0  # pin count
```

### 7.3 接口

```python
class BufferPool:
    def __init__(self, capacity: int = 100)
    def get_page(self, page_id: int) -> Page
    def flush(self) -> None
    def pin(self, page_id: int) -> None
    def unpin(self, page_id: int) -> None
```

---

## 8. Catalog

### 8.1 tinydb_master 表结构

| 列名 | 类型 | 说明 |
|------|------|------|
| table_name | TEXT | 表名（主键） |
| columns | TEXT | 列定义 JSON 数组 |
| root_page | INTEGER | 表的根页号 |
| primary_key | TEXT | 主键列名 |

### 8.2 接口

```python
class Catalog:
    def __init__(self, table: Table)
    def load(self) -> None                       # 从磁盘加载
    def save(self) -> None                       # 写回磁盘
    def create_table(self, name: str, columns: list[ColumnDef], pk: str) -> None
    def drop_table(self, name: str) -> None
    def get_table(self, name: str) -> TableMeta
    def list_tables(self) -> list[str]
```

---

## 9. Table（用户 API）

### 9.1 数据流

**INSERT:**
1. 遍历页链表 → 找 `free_space >= len(serialized_row)` 的页
2. 无合适页 → `FileManager.alloc_page()` 追加到链尾
3. `BufferPool.get_page(page_id)` → 获取 Page 对象
4. 序列化行 → 写入 Page 数据区 → 添加 slot → 标记 dirty

**SCAN:**
1. 从 `root_page` 开始遍历页链表
2. 每页 pin → 读取所有有效 slot → 反序列化 → unpin
3. 返回行 `Iterator`

### 9.2 接口

```python
class Table:
    def insert(self, row: list) -> RowId
    def scan(self) -> Iterator[tuple[RowId, list]]  # 返回 (rowId, row) 元组
    def get(self, row_id: RowId) -> list | None
    def delete(self, row_id: RowId) -> None
    def update(self, row_id: RowId, row: list) -> None
```

---

## 10. Error Handling

```python
class StorageError(Exception): ...
class StorageCorruptionError(StorageError): ...
class StorageFullError(StorageError): ...
class PageOutOfRangeError(StorageError): ...
class TableExistsError(StorageError): ...
class TableNotFoundError(StorageError): ...
class SchemaMismatchError(StorageError): ...
```

| 场景 | 异常 |
|------|------|
| 文件 checksum 不匹配 | `StorageCorruptionError` |
| 页号 >= page_count | `PageOutOfRangeError` |
| CREATE 已存在表 | `TableExistsError` |
| 操作不存在的表 | `TableNotFoundError` |
| 值类型与列定义不匹配 | `SchemaMismatchError` |
| 磁盘空间不足 | `StorageFullError` |

---

## 11. Testing Strategy

### 11.1 单元测试

| 模块 | 测试内容 |
|------|----------|
| TypeSystem | 类型检查覆盖所有组合、隐式转换规则、NULL 处理 |
| RowFormat | 序列化/反序列化往返一致性、NULL 位图边界 |
| Page | slot 增删改、空闲空间计算、空间复用 |
| BufferPool | LRU 淘汰顺序（mock 访问序列）、pin 阻止淘汰、脏页刷盘 |
| FileManager | 空闲链表 alloc/free 往返、文件创建/打开 |

### 11.2 集成测试

| 场景 | 验证 |
|------|------|
| CRUD | 创建表 → 插入 → 查询 → 更新 → 删除 |
| 持久性 | 写入 → 关闭 → 重开 → 数据一致 |
| 多页 | 插入足够多行使其跨越多页 → 全表扫描正确 |

### 11.3 测试框架

- **pytest**: fixture 管理临时数据库文件
- **parametrize**: 类型组合、NULL 模式批量覆盖
- **tmp_path**: pytest 内置临时目录管理测试文件

---

## 12. Risks & Mitigations

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 行删除后空间碎片累积 | 高 | 中 | 低优先级：教学项目暂不实现 slot 级空间回收 |
| 顺序扫描污染 LRU | 中 | 低 | pin 机制保护当前扫描页 |
| JSON 列定义解析错误 | 低 | 中 | try/except + 清晰错误信息 |
| 文件并发写入 | N/A | N/A | 不支持并发（文档说明） |

---

## 13. Open Questions

- [ ] 空间碎片回收策略（未来优化，不在本 change scope）
- [ ] 大值（>1页）存储策略（暂不支持）
