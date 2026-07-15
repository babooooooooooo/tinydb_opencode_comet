---
comet_change: tinydb-index-txn
role: technical-design
canonical_spec: openspec
---

# tinydb-index-txn Design Doc

## 1. Architecture Overview

tinydb-index-txn 是 tinydb 的顶层模块，整合存储引擎（tinydb-storage）和 SQL 引擎（tinydb-sql），新增三层核心能力：

```
┌─────────────────────────────────────────────────────┐
│  CLI / REPL                                         │
│  (readline 交互界面，表格输出，元命令)                 │
├─────────────────────────────────────────────────────┤
│  Database (统一入口)                                 │
│  ├─ Query Planner + Executor (from tinydb-sql)      │
│  ├─ Index Manager (索引元数据 + 自动维护)             │
│  └─ Transaction Manager (BEGIN/COMMIT/ROLLBACK)     │
├─────────────────────────────────────────────────────┤
│  B-tree Index (btree.py)                            │
│  ├─ 节点序列化到存储页                               │
│  ├─ 等值查找 O(log n)                               │
│  └─ 范围扫描（叶节点链表）                           │
├─────────────────────────────────────────────────────┤
│  Shadow Paging (shadow_paging.py)                   │
│  ├─ 页级写时复制 (CoW)                              │
│  ├─ 原子根指针切换                                   │
│  └─ 影子页追踪与清理                                 │
├─────────────────────────────────────────────────────┤
│  Storage Layer (tinydb-storage, archived)           │
│  FileManager + BufferPool + Catalog + Table         │
└─────────────────────────────────────────────────────┘
```

**数据流：**
1. 用户通过 `Database.execute(sql)` 或 REPL 输入 SQL
2. SQL 引擎解析为 AST，Planner 选择执行策略（IndexScan vs FullScan）
3. Executor 通过 Table API 或 B-tree Index 访问数据
4. 所有页访问经过 Shadow Paging 层，事务内修改走 CoW
5. COMMIT 时原子切换根指针，ROLLBACK 时丢弃影子页

## 2. B-tree Structure

### 2.1 Node Layout

B-tree 节点直接映射到存储页（4096 bytes）。复用现有 Page 结构，`page_type = PageType.INDEX`。

**内部节点（Internal Node）：**
```
Offset    Size    Field
─────────────────────────────────
0         32      Page Header (复用现有结构)
32        1       node_flags (0x01 = leaf, 0x00 = internal)
33        2       key_count (uint16)
35        1       padding
36        N*K     keys[] (每个 key K 字节，变长详见下方)
36+N*K    (N+1)*4 children[] (uint32 页号数组)
```

**叶节点（Leaf Node）：**
```
Offset    Size    Field
─────────────────────────────────
0         32      Page Header
32        1       node_flags (0x01 = leaf)
33        2       key_count (uint16)
35        1       padding
36        N*K     keys[]
36+N*K    N*8     values[] (每个 value 为 row_pointer: page_id u32 + slot u32)
36+N*(K+8) 4     next_leaf (uint32 叶节点链表指针，0 = end)
```

### 2.2 Key 序列化

由于 key 类型多样（INTEGER/TEXT），B-tree 内部统一将 key 转为 bytes：

| 类型 | 编码方式 |
|------|----------|
| INTEGER (int64) | 大端 8 字节（支持负数正确排序） |
| BOOLEAN | 1 字节 (0/1) |
| FLOAT (double) | IEEE 754 大端 8 字节（负数取反保证排序） |
| TEXT | UTF-8 字节 + 零填充到列定义长度 |

实际 key_size 在运行时根据列类型动态确定。

### 2.3 Order 计算

阶数（max_keys）由页大小和 key_size 动态计算：

```python
# Internal node: key_count * key_size + (key_count + 1) * 4 <= MAX_FREE_SPACE
# Leaf node: key_count * key_size + key_count * 8 + 4 <= MAX_FREE_SPACE

def compute_max_keys(key_size: int, is_leaf: bool) -> int:
    if is_leaf:
        # key_count * (key_size + 8) + 4 <= 4064
        return (MAX_FREE_SPACE - 4) // (key_size + 8)
    else:
        # key_count * key_size + (key_count + 1) * 4 <= 4064
        return (MAX_FREE_SPACE - 4) // (key_size + 4)
```

min_keys = max_keys // 2（标准 B-tree 约束）。

### 2.4 Split Strategy

**叶节点分裂：**
1. 节点已满（key_count == max_keys）时触发
2. 取中间位置 `mid = key_count // 2`
3. 新建右节点，将 `[mid:]` 的键值对移入
4. 左节点保留 `[0:mid]`
5. 提升 right.keys[0]（右节点最小 key）到父节点
6. 父节点插入新 key 和右节点指针
7. 更新 `next_leaf` 链表：left.next → right, right.next → 原 left.next

**内部节点分裂：**
1. 节点已满时触发
2. 取中间位置 `mid = key_count // 2`
3. 提升 `keys[mid]` 到父节点（不保留在子节点）
4. 左节点保留 `keys[0:mid]` + `children[0:mid+1]`
5. 右节点保留 `keys[mid+1:]` + `children[mid+1:]`

**根节点分裂：**
1. 创建新根
2. 原根分裂为左右两子
3. 新根包含一个 key（提升的中间键）和两个子指针
4. 树高 +1

### 2.5 Delete (Lazy)

1. 查找 key 所在叶节点
2. 从叶节点移除该 (key, value) 对
3. 不合并、不重分布
4. 标记节点 dirty

> 教学简化：允许 underflow，保持实现简单。删除后 B-tree 可能稀疏但结构有效。

### 2.6 Range Scan

1. 用等值查找定位 `start` 所在叶节点
2. 从该叶节点开始向右遍历（通过 next_leaf 链表）
3. 收集所有 key <= end 的键值对
4. 若 next_leaf 存在且其第一个 key <= end，继续遍历

## 3. Index Manager

### 3.1 元数据结构

```python
@dataclass
class IndexMeta:
    name: str            # 索引名 (e.g., "idx_users_age")
    table_name: str      # 表名
    column_name: str     # 列名
    column_type: DataType
    root_page: int       # B-tree 根节点页号
```

IndexManager 维护：
```python
class IndexManager:
    _indexes: dict[str, IndexMeta]           # name → meta
    _table_indexes: dict[str, dict[str, str]] # table → {column → index_name}
    _btrees: dict[str, BTreeIndex]            # name → 内存中 B-tree 对象
```

### 3.2 持久化

索引元数据存储在 Catalog 中（复用现有 Catalog 表），新增字段 `indexes`（JSON 数组）：

```json
[
  {"name": "idx_users_age", "table": "users", "column": "age", "root_page": 5}
]
```

### 3.3 DML Hook

IndexManager 提供 hook 方法供 Executor 调用：

```python
def after_insert(self, table_name: str, row_ptr: RowId, row: list):
    """INSERT 后更新所有相关索引"""
    for col_idx, col in enumerate(table.columns):
        index_name = self._table_indexes[table_name].get(col.name)
        if index_name:
            btree = self._btrees[index_name]
            key = row[col_idx]
            btree.insert(key, row_ptr)

def after_delete(self, table_name: str, row_ptr: RowId, old_row: list):
    """DELETE 前移除索引条目"""
    for col_idx, col in enumerate(table.columns):
        index_name = self._table_indexes[table_name].get(col.name)
        if index_name:
            btree = self._btrees[index_name]
            key = old_row[col_idx]
            btree.delete(key, row_ptr)

def after_update(self, table_name: str, row_ptr: RowId, old_row: list, new_row: list):
    """UPDATE 后更新变化的索引列"""
    for col_idx, col in enumerate(table.columns):
        if old_row[col_idx] == new_row[col_idx]:
            continue
        index_name = self._table_indexes[table_name].get(col.name)
        if index_name:
            btree = self._btrees[index_name]
            btree.delete(old_row[col_idx], row_ptr)
            btree.insert(new_row[col_idx], row_ptr)
```

## 4. Index-Aware Query Planning

### 4.1 IndexScan Operator

```python
class IndexScanOperator:
    """当 WHERE 子句包含索引列的等值/范围条件时使用"""

    def __init__(self, table, index_meta, condition):
        self.table = table
        self.index = index_meta
        self.condition = condition  # Column op Value

    def execute(self, buffer_pool) -> Iterator[tuple[RowId, list]]:
        btree = load_btree(self.index.root_page)
        op = self.condition.op  # '=', '>', '>=', '<', '<=', '!='
        key = self.condition.value

        if op == '=':
            results = btree.search(key)  # → list[RowId]
        elif op in ('>', '>='):
            results = btree.range_scan(start=key, end=None,
                                        start_inclusive=(op == '>='))
        elif op in ('<', '<='):
            results = btree.range_scan(start=None, end=key,
                                        end_inclusive=(op == '<='))
        elif op == '!=':
            # 全表扫描过滤
            return FullScan(self.table).filter(lambda r: r[key_idx] != key)

        for row_ptr in results:
            row = self.table.get(buffer_pool, row_ptr)
            if row is not None:
                yield row_ptr, row
```

### 4.2 Planner 启发式

简单规则（无统计信息）：

1. WHERE 子句为 **索引列等值条件** → 优先 IndexScan
2. WHERE 子句为 **索引列范围条件** → 优先 IndexScan
3. 多索引列条件 → 选第一个匹配的索引
4. 无条件或非索引列条件 → FullScan

> 不实现代价模型：教学定位，单表数据量小，索引选择硬编码即可。

## 5. Shadow Paging

### 5.1 核心机制

Shadow Paging 通过页级写时复制实现事务原子性和回滚能力：

```
┌──────────────────────────────────────────────┐
│           Shadow Paging Transaction          │
│                                              │
│  BEGIN:                                      │
│    1. snapshot root_page_id (文件头)         │
│    2. 初始化 shadow_pages = {}               │
│                                              │
│  Write Page N:                               │
│    if N not in shadow_pages:                 │
│      a. alloc_page() → 新页号 N'            │
│      b. copy page N content → page N'       │
│      c. shadow_pages[N] = N'                │
│    modify shadow_pages[N] (N')               │
│                                              │
│  Read Page N:                                │
│    if N in shadow_pages:                     │
│      return shadow_pages[N] (N')             │
│    else:                                     │
│      return original page N                  │
│                                              │
│  COMMIT:                                     │
│    1. 刷新所有影子页到磁盘                   │
│    2. 原子切换文件头 root_page_id            │
│    3. 清理 shadow_pages                      │
│                                              │
│  ROLLBACK:                                   │
│    1. 释放所有影子页 (free_page)             │
│    2. 清理 shadow_pages                      │
└──────────────────────────────────────────────┘
```

### 5.2 Modified BufferPool

Shadow Paging 需要拦截 BufferPool 的 `get_page` 和 `write_page` 调用：

```python
class ShadowBufferPool:
    """BufferPool 的 Shadow Paging 包装"""

    def __init__(self, buffer_pool, txn_manager):
        self._pool = buffer_pool
        self._txn = txn_manager

    def get_page(self, page_id: int) -> bytes:
        shadow_id = self._txn.get_shadow(page_id)
        if shadow_id is not None:
            return self._pool.get_page(shadow_id)
        return self._pool.get_page(page_id)

    def set_page_data(self, page_id: int, data: bytes) -> None:
        shadow_id = self._txn.ensure_shadow(page_id)
        self._pool.set_page_data(shadow_id, data)
```

### 5.3 COMMIT Protocol

```python
def commit(self):
    # 1. 将所有影子页刷盘
    for orig_id, shadow_id in self.shadow_pages.items():
        page_data = self._pool.get_page(shadow_id)  # 触发 flush
    self._pool.flush()

    # 2. 原子切换根指针
    self._fm.root_page_id = self.new_root_page

    # 3. 写入文件头（持久化 root_page_id）
    self._fm._write_header()
    self._fm._file.flush()
    os.fsync(self._fm._file.fileno())

    # 4. 清理
    self.shadow_pages.clear()
    self.state = "committed"
```

### 5.4 ROLLBACK Protocol

```python
def rollback(self):
    # 1. 释放所有影子页到 free list
    for orig_id, shadow_id in self.shadow_pages.items():
        self._fm.free_page(shadow_id)

    # 2. 清理内存状态
    self.shadow_pages.clear()
    self.state = "aborted"
```

### 5.5 File Header Extension

文件头从 `FileHeader` 结构新增字段：

```python
# 新增 root_page_id 字段（uint32）
# 文件头格式更新：
_HEADER_FMT = "<IIIII IQ"  # 增加 root_page_id (I) + padding
```

> 由于 `tinydb-storage` 已 archived，需要在 `shadow_paging.py` 中通过 monkey-patching 或 FileManager 子类实现。

**实际方案**：Shadow Paging 持有 FileManager 引用，直接操作 `root_page_id` 属性，COMMIT 时调用 `_write_header()` 持久化。不修改已 archived 的 storage 层文件。

## 6. Transaction Manager

### 6.1 Transaction State

```python
@dataclass
class Transaction:
    txn_id: int
    state: str                    # "active" | "committed" | "aborted"
    shadow_pages: dict[int, int]  # orig_page_id → shadow_page_id
    snapshot_root: int            # 事务开始时 root_page_id
    new_root: int                 # 事务结束时的 root_page_id
```

### 6.2 TransactionManager API

```python
class TransactionManager:
    def __init__(self, file_manager, buffer_pool, index_manager):
        self._fm = file_manager
        self._pool = buffer_pool
        self._index_mgr = index_manager
        self._active_txn: Transaction | None = None
        self._txn_counter = 0

    def begin(self) -> Transaction:
        if self._active_txn is not None:
            raise TransactionError("Nested transactions not supported")
        self._txn_counter += 1
        txn = Transaction(
            txn_id=self._txn_counter,
            state="active",
            shadow_pages={},
            snapshot_root=self._fm.root_page_id,
            new_root=self._fm.root_page_id,
        )
        self._active_txn = txn
        return txn

    def commit(self):
        if self._active_txn is None:
            raise TransactionError("No active transaction")
        # 刷盘 + 原子切换
        self._pool.flush()
        self._fm._write_header()
        self._fm._file.flush()
        os.fsync(self._fm._file.fileno())
        self._active_txn.state = "committed"
        self._active_txn = None

    def rollback(self):
        if self._active_txn is None:
            raise TransactionError("No active transaction")
        # 释放影子页
        for orig_id, shadow_id in self._active_txn.shadow_pages.items():
            self._fm.free_page(shadow_id)
        self._active_txn.state = "aborted"
        self._active_txn = None

    def ensure_shadow(self, page_id: int) -> int:
        """获取或创建影子页，返回影子页 ID"""
        if self._active_txn is None:
            return page_id  # 无事务，直接修改
        if page_id in self._active_txn.shadow_pages:
            return self._active_txn.shadow_pages[page_id]
        # CoW: 创建影子页
        shadow_id = self._fm.alloc_page()
        orig_data = self._pool.get_page(page_id)
        self._pool._fm.write_page(shadow_id, orig_data)  # 写入磁盘
        self._active_txn.shadow_pages[page_id] = shadow_id
        return shadow_id
```

### 6.3 Error Auto-Rollback

```python
class Database:
    def execute(self, sql: str) -> QueryResult:
        try:
            result = self._executor.execute(sql)
            return result
        except Exception as e:
            if self._txn_manager.has_active_txn():
                self._txn_manager.rollback()
            raise DatabaseError(str(e))
```

## 7. Database Class

### 7.1 Public API

```python
class Database:
    def __init__(self, path: str):
        self._fm = FileManager(path)
        self._fm.open()
        self._pool = BufferPool(self._fm)
        self._catalog = Catalog(self._fm, self._pool)
        self._catalog.load()
        self._index_mgr = IndexManager(self._catalog, self._fm, self._pool)
        self._txn_mgr = TransactionManager(self._fm, self._pool, self._index_mgr)
        self._executor = Executor(self._catalog, self._pool, self._index_mgr)

    def execute(self, sql: str) -> QueryResult:
        """执行 SQL，返回结果"""

    def commit(self):
        """显式提交"""

    def rollback(self):
        """显式回滚"""

    def close(self):
        """关闭数据库：刷盘 + 关闭文件"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
```

### 7.2 QueryResult

```python
@dataclass
class QueryResult:
    columns: list[str]       # 列名
    rows: list[list]         # 数据行
    row_count: int           # 影响行数 (DML) 或结果行数 (SELECT)
```

## 8. CLI REPL

### 8.1 交互循环

```python
class REPL:
    def __init__(self, db: Database):
        self._db = db
        self._buffer = []

    def run(self):
        import readline
        readline.set_history_length(1000)

        while True:
            try:
                prompt = "tinydb> " if not self._buffer else "   ...> "
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print("\n Bye.")
                break

            # 元命令
            if line.startswith("."):
                self._handle_meta(line.strip())
                continue

            self._buffer.append(line)
            sql = " ".join(self._buffer)

            if sql.rstrip().endswith(";"):
                self._buffer.clear()
                result = self._db.execute(sql)
                self._format_output(result)

    def _handle_meta(self, cmd: str):
        parts = cmd.split()
        match parts[0]:
            case ".exit" | ".quit":
                raise SystemExit
            case ".tables":
                tables = self._db.execute("SHOW TABLES")
                print(tables)
            case ".schema":
                if len(parts) < 2:
                    print("Usage: .schema <table>")
                else:
                    schema = self._db.execute(f"DESCRIBE {parts[1]}")
                    print(schema)
            case ".help":
                print("Meta-commands: .exit .tables .schema .help")
```

### 8.2 输出格式

```
tinydb> SELECT * FROM users WHERE age > 25;
┌────┬───────┬─────┐
│ id │ name  │ age │
├────┼───────┼─────┤
│  1 │ Alice │  30 │
│  3 │ Carol │  28 │
└────┴───────┴─────┘
2 rows in set
```

## 9. Integration with Existing Modules

### 9.1 Storage Layer (archived)

- `Page` / `PageType.INDEX`：复用现有页结构
- `BufferPool`：影子页包装层
- `FileManager`：extend to support root_page_id

### 9.2 SQL Layer (parallel design)

SQL 层的 Executor 需要新增 IndexScanOperator。集成点：

```python
# tinydb/sql/executor.py 新增
from tinydb.index.index_manager import IndexManager

class Executor:
    def __init__(self, catalog, pool, index_mgr: IndexManager | None = None):
        self._index_mgr = index_mgr

    def _choose_scan(self, table, where_clause):
        if self._index_mgr and where_clause:
            index = self._index_mgr.find_matching_index(table.name, where_clause)
            if index:
                return IndexScanOperator(table, index, where_clause)
        return FullScanOperator(table)
```

### 9.3 跨模块调用链

```
REPL → Database.execute()
         → SQL Parser → AST
         → Planner (uses IndexManager for index selection)
         → Executor
             ├─ IndexScan (uses BTreeIndex)
             └─ FullScan (uses Table API)
         → Table/Index operations
         → ShadowBufferPool.get_page() / set_page_data()
         → BufferPool
         → FileManager
```

## 10. Testing Strategy

### 10.1 Unit Tests

| 模块 | 测试内容 |
|------|----------|
| `btree.py` | 空树插入、节点分裂、根分裂、等值查找、范围扫描、删除、持久化-恢复 |
| `index_manager.py` | CREATE/DROP INDEX、DML 自动更新、多索引管理 |
| `shadow_paging.py` | CoW 创建、COMMIT 原子性、ROLLBACK 清理、影子页追踪 |
| `transaction.py` | BEGIN/COMMIT/ROLLBACK、错误自动回滚 |
| `database.py` | execute() 返回值、上下文管理器、close() 清理 |
| `repl.py` | 元命令、多行 SQL、表格格式化 |

### 10.2 Integration Tests

1. **端到端 CRUD**：INSERT → SELECT → UPDATE → DELETE
2. **索引加速验证**：EXPLAIN 或计时对比 FullScan vs IndexScan
3. **事务一致性**：COMMIT 后数据持久化、ROLLBACK 后索引同步回滚
4. **持久化恢复**：关闭后重开，B-tree 和索引结构完整
5. **错误回滚**：SQL 执行出错 → 自动回滚 → 数据不变

### 10.3 Test Helpers

```python
@pytest.fixture
def db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    yield db
    db.close()
```

## 11. File Layout

```
tinydb/
├── index/
│   ├── __init__.py
│   ├── btree.py          # BTreeIndex 类
│   └── index_manager.py  # IndexManager 类
├── transaction/
│   ├── __init__.py
│   ├── shadow_paging.py  # ShadowBufferPool + Transaction
│   └── txn_manager.py    # TransactionManager
├── cli/
│   ├── __init__.py
│   └── repl.py           # REPL 类
└── database.py           # Database 类 + QueryResult

tests/
├── test_btree.py
├── test_index_manager.py
├── test_shadow_paging.py
├── test_transaction.py
├── test_database.py
├── test_repl.py
└── test_integration.py
```

## 12. Risk Mitigation

| 风险 | 缓解 |
|------|------|
| Shadow Paging 导致文件膨胀 | free_page 回收影子页，ROLLBACK 时释放 |
| B-tree 删除后查询到幽灵数据 | lazy delete 不影响正确性；range scan 时过滤已标记删除项 |
| 事务中 B-tree 结构变化 | 根指针在 COMMIT 时原子切换；ROLLBACK 释放所有新分配页 |
| FileManager 已 archived 无法修改 | Shadow Paging 持有 FM 引用，直接操作 root_page_id 属性 |
| SQL 层并发设计 | 定义清晰接口契约，tinydb-sql 设计时对齐 |

---

## 确认的设计决策

### 文件头扩展
- 添加 `root_page_id` 到文件头结构
- 文件格式 version bump: 1 → 2
- 向后兼容：读取 version=1 时 root_page_id 默认为 0（catalog 表根页）

### TEXT 键编码
- 使用 length-prefix 编码（4 字节长度 + UTF-8 字节）
- 不支持零填充定长（浪费空间）

### != 操作符
- 使用全表扫描 + Filter 回退
- 不实现 index-skip 路径
