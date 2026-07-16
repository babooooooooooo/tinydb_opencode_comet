---
archived-with: 2026-07-16-tinydb-v02-join, 2026-07-16-tinydb-v02-concurrency, 2026-07-16-tinydb-v02-cli
status: final
---

# tinydb v0.2 总体设计文档

> 创建日期: 2026-07-16
> 版本: v0.2
> 基础版本: v0.1 (单表 SQL 引擎，shadow paging 事务，基础 CLI)

---

## 1. 目标

在 v0.1 基础上实现三大能力跃迁：

1. **多表 JOIN 查询** — 支持全部 JOIN 类型（INNER、LEFT、RIGHT、FULL OUTER、CROSS、NATURAL、SELF），三种执行算法（Nested Loop、Hash Join、Sort-Merge Join）
2. **并发控制** — 锁 + MVCC 混合模型，支持多事务并发执行，读不阻塞写、写不阻塞读
3. **CLI 功能增强** — 语法高亮、自动补全、解释执行计划、数据导入导出、查询计时

## 2. 架构概览

```
tinydb/
├── sql/              ← JOIN Change 主要改动区
│   ├── ast.py        # 新增 JoinClause, TableRef 节点
│   ├── lexer.py      # 新增 JOIN/ON/USING/NATURAL 等 token
│   ├── parser.py     # 扩展解析多表 FROM 子句
│   ├── planner.py    # 新增 JoinPlanner（代价选择）
│   ├── executor.py   # 新增三种 JoinOperator
│   └── database.py   # 入口调度（最小改动）
├── concurrency/      ← Concurrency Change 新建模块
│   ├── lock_manager.py      # Shared/Exclusive Lock 管理
│   ├── mvcc_manager.py      # 多版本链管理
│   ├── deadlock_detector.py # 超时 + 等待图检测
│   └── isolation.py         # 隔离级别定义与校验
├── transaction/      ← Concurrency Change 改造区
│   ├── txn_manager.py       # 支持多事务并发
│   └── shadow_paging.py     # 适配 MVCC 版本链
├── buffer_pool.py    ← Concurrency Change 添加 page latch
├── cli/              ← CLI Change 主要改动区
│   ├── repl.py       # 高亮、补全、新命令
│   ├── highlighter.py       # SQL 语法高亮（pygments）
│   └── commands.py          # .explain/.import/.dump/.timing
└── database.py       ← 入口（各 change 最小化改动）
```

## 3. Change 分解

三个独立 OpenSpec change，三个 worktree 从 master 并行出发：

| Change | 名称 | 并行度 | 主要改动文件 |
|--------|------|--------|-------------|
| C1 | tinydb-v02-join | 完全并行 | sql/ast, lexer, parser, planner, executor |
| C2 | tinydb-v02-concurrency | 完全并行 | concurrency/*, transaction/*, buffer_pool |
| C3 | tinydb-v02-cli | 完全并行 | cli/repl, cli/highlighter, cli/commands |

---

## 4. Change 1: 多表 JOIN 查询

### 4.1 范围

**支持的 JOIN 类型：**
- `INNER JOIN ... ON ...`
- `LEFT [OUTER] JOIN ... ON ...`
- `RIGHT [OUTER] JOIN ... ON ...`
- `FULL [OUTER] JOIN ... ON ...`
- `CROSS JOIN`（笛卡尔积，无 ON 条件）
- `NATURAL JOIN`（自动匹配同名列）
- `SELF JOIN`（表别名复用）

**支持的执行算法：**
- **Nested Loop Join** — 通用，小数据集或带索引场景
- **Hash Join** — 大数据集等值连接，右表建哈希表
- **Sort-Merge Join** — 已排序数据或需要排序输出场景

### 4.2 AST 扩展

```python
@dataclass
class TableRef:
    name: str
    alias: str | None = None

@dataclass
class JoinClause:
    join_type: str          # INNER, LEFT, RIGHT, FULL, CROSS, NATURAL
    right_table: TableRef
    on_condition: Expression | None = None   # CROSS JOIN 为 None
    using_columns: list[str] | None = None   # NATURAL/USING 使用

@dataclass
class SelectStatement:
    columns: list[Expression]
    from_table: TableRef           # 主表
    joins: list[JoinClause] = field(default_factory=list)  # 新增
    where: Expression | None = None
    # ... 其余字段不变
```

### 4.3 Lexer 扩展

新增 token：`JOIN`, `INNER`, `LEFT`, `RIGHT`, `FULL`, `OUTER`, `CROSS`, `NATURAL`, `ON`, `USING`

### 4.4 Parser 扩展

扩展 `_parse_select()` 的 FROM 子句解析：

```
FROM table_name [alias]
     { JOIN_CLAUSE }*

JOIN_CLAUSE := [INNER|LEFT [OUTER]|RIGHT [OUTER]|FULL [OUTER]|CROSS|NATURAL]
               JOIN table_ref
               { ON expression | USING (columns) }
```

### 4.5 Planner 扩展

`JoinPlanner` 根据统计信息和代价模型选择算法：

```
选择逻辑：
1. CROSS JOIN → Nested Loop（笛卡尔积，无优化空间）
2. NATURAL/USING 等值连接 + 大表 → Hash Join
3. ON 条件有索引 → Index Nested Loop Join
4. 两表已排序或需排序输出 → Sort-Merge Join
5. 默认 → Nested Loop Join
```

代价估算参数：
- 表行数（从 storage engine 元数据获取）
- 可用索引
- 内存限制（哈希表最大内存，默认 1MB）

阈值："大表" = 右表行数 > 1000 或右表数据量 > 内存限制 / 平均行大小。此时优先选择 Hash Join 或 Sort-Merge Join。

### 4.6 Executor 扩展

```python
class NestedLoopJoinOperator:
    """外循环遍历左表，内循环扫描右表，过滤 ON 条件"""

class HashJoinOperator:
    """构建阶段：扫描右表建哈希表；探测阶段：遍历左表查表"""

class SortMergeJoinOperator:
    """两表按连接键排序后归并，适合已排序或需要排序输出的场景"""
```

所有 JoinOperator 遵循 Volcano 模型（`__iter__`/`__next__`），可嵌套在 Filter/Project 之下。

### 4.7 列引用处理

JOIN 引入表别名后，`ColumnRef` 需要支持限定名：

```python
@dataclass
class ColumnRef:
    name: str
    table: str | None = None    # 表别名限定，如 u.name → table="u"
```

Planner 在生成计划时负责列名解析（按别名查实际表名 → 按表名查列位置）。

### 4.8 测试策略

- 单元测试：每种 JOIN 类型 × 每种算法
- 边界测试：NULL 值处理、空表 JOIN、自连接
- 正确性：与 SQLite 结果对比
- 性能：大数据集验证算法选择正确性

---

## 5. Change 2: 并发控制

### 5.1 范围

**锁 + MVCC 混合模型：**
- **锁** — 控制写并发，保证写操作互斥
- **MVCC** — 提供读快照，读不阻塞写
- **多事务** — 同时支持多个活跃事务
- **死锁处理** — 超时检测 + 等待图检测

### 5.2 核心组件

#### LockManager

```python
class LockManager:
    """管理页级 Shared/Exclusive Lock"""

    def acquire(txn_id, page_id, mode) -> bool
    def release(txn_id, page_id)
    def release_all(txn_id)
    def upgrade(txn_id, page_id)  # S→X 升级
```

- 锁粒度：页级（与 buffer pool 页对应）
- 锁模式：Shared (S) — 读；Exclusive (X) — 写
- 兼容性矩阵：S-S 兼容，S/X-X 互斥
- 锁等待队列：FIFO + 超时

#### MVCCManager

```python
class MVCCManager:
    """维护数据页的多版本链"""

    def read_version(page_id, txn_id) -> PageVersion
    def create_version(page_id, txn_id, data) -> PageVersion
    def get_visible_version(page_id, snapshot) -> PageVersion
    def gc(oldest_active_snapshot)  # 版本清理
```

- 每页维护版本链表（按 txn_id 降序）
- 快照：事务开始时获取活跃事务列表
- 可见性判断：`created_txn in snapshot AND deleted_txn NOT IN snapshot`
- GC：定期清理无活跃事务引用的旧版本

#### DeadlockDetector

```python
class DeadlockDetector:
    """超时 + 等待图检测"""

    def detect_cycle(txn_id, waits_for_graph) -> list[txn_id] | None
    def choose_victim(cycle) -> txn_id  # 选择中止的事务
```

- 默认超时：5 秒
- 等待图检测：每次等待入队时检查环路
- 牺牲者选择： youngest transaction（最新开始的事务）

#### Isolation Levels

```
READ UNCOMMITTED — 读无锁，可能读到未提交数据
READ COMMITTED   — 读加共享锁，语句级快照
REPEATABLE READ  — 读加共享锁，事务级快照（默认）
SERIALIZABLE     — 范围锁 + 两阶段锁
```

v0.2 默认实现 REPEATABLE READ，接口预留其他级别扩展。

### 5.3 事务管理器重构

现有 `_active_txn: Transaction | None` 改为 `_active_txns: dict[txn_id, Transaction]`：

```python
class TransactionManager:
    def begin() -> txn_id
    def commit(txn_id)
    def rollback(txn_id)
    def get_snapshot(txn_id) -> Snapshot   # MVCC 快照
```

### 5.4 Buffer Pool 改造

```python
class BufferPool:
    def pin(page_id, txn_id, mode) -> Page   # 现有 pin() 加锁调用
    def unpin(page_id, txn_id)               # 现有 unpin() 解锁
    def get_page(page_id, txn_id) -> Page     # MVCC 可见性版本
```

- pin/unpin 内部调用 LockManager
- 读操作获取 MVCC 可见版本而非直接返回最新页

### 5.5 与 v0.1 的兼容性

- shadow paging 的页级原子性保留，MVCC 在其上层提供读快照
- 现有单线程代码路径不变，多线程下自动启用并发控制
- 默认 isolation level = REPEATABLE READ，与 v0.1 行为等价（单事务时）

### 5.6 测试策略

- 单元测试：LockManager 兼容性矩阵、MVCC 可见性判断
- 并发测试：多线程读写、死锁检测与恢复
- 隔离测试：验证四种隔离级别下的事务行为
- 回归测试：v0.1 用例在多事务模式下不退化

---

## 6. Change 3: CLI 功能增强

### 6.1 范围

| 功能 | 描述 | 优先级 |
|------|------|--------|
| 语法高亮 | SQL 关键字、字符串、数字、注释着色 | P0 |
| 行编辑 | Emacs 快捷键、Ctrl-A/E/W/K/U | P0 |
| 自动补全 | 关键字、表名、列名 TAB 补全 | P0 |
| .explain | 展示 SQL 执行计划树 | P0 |
| .import | 从 CSV/JSON 导入数据 | P1 |
| .dump | 导出表数据为 CSV/JSON | P1 |
| .timing | 开关查询计时显示 | P1 |
| 多行增强 | 现有基础上完善（括号匹配、续行提示） | P1 |

### 6.2 语法高亮

```python
class SQLHighlighter:
    """基于 pygments 的 SQL 语法高亮"""

    def highlight(sql: str) -> str    # 返回 ANSI 着色字符串
    def highlight_stream(tokens) -> str  # 实时输入高亮
```

- 依赖：`pygments`（`pip install pygments`）
- 配色：keywords(蓝)、strings(绿)、numbers(黄)、comments(灰)
- 降级：无 pygments 时静默不渲染

### 6.3 自动补全

```python
class SQLCompleter:
    """上下文感知的 SQL 补全"""

    def complete(text, state) -> str | None
    def refresh_schema(db)  # 从 db 加载表名/列名
```

- 补全源：SQL 关键字 + 数据库元数据（表名、列名）
- 上下文感知：FROM 后补全表名，SELECT 后补全列名
- 触发：TAB 键

### 6.4 命令实现

#### .explain <SQL>

```
sqlite> .explain SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id;
┌─ ExecutePlan ─────────────────────────────┐
│ Project [name, amount]                     │
│ └─ NestedLoopJoin ON u.id = o.user_id      │
│    ├─ Scan(users AS u)                     │
│    └─ Scan(orders AS o)                    │
└────────────────────────────────────────────┘
```

通过 `planner.plan()` 获取 operator tree，格式化输出。

#### .import <table> <filepath>

- 支持 CSV 和 JSON 格式
- 自动推断列数和类型
- 批量插入（事务包裹）

#### .dump <table> [filepath]

- 默认输出到 stdout，可指定文件
- 支持 CSV 和 JSON 格式

#### .timing on|off

- 开启后每条 SQL 后显示执行耗时
- 默认 off

### 6.5 REPL 重构

```python
class REPL:
    def __init__(self, db):
        self.highlighter = SQLHighlighter()
        self.completer = SQLCompleter(db)
        self.timing_enabled = False

    def run(self):
        # 主循环：输入 → 解析 → 执行 → 显示
        # 支持多行（括号匹配判断语句完整性）
        # DOT 命令分发到 CommandHandler
```

- 多行判断：括号配对 + 分号结尾
- 续行提示：`.. ` 缩进提示符
- 现有 .exit/.quit/.tables/.schema/.help 保留

### 6.6 测试策略

- 单元测试：高亮输出格式、补全候选列表、命令解析
- 集成测试：端到端 REPL 会话模拟
- 边界：超长输入、Unicode、空输入

---

## 7. 接口契约（Interface Contracts）

各 change 通过以下接口边界解耦，减少合并冲突：

### 7.1 SQL 层 → 存储层

```python
# 现有接口不变，JOIN 和并发控制各自扩展
class Database:
    def execute(self, sql: str) -> QueryResult: ...  # 不改签名
    def list_tables(self) -> list[str]: ...         # CLI 补全使用
    def get_schema(self, table: str) -> list[ColumnDef]: ...  # CLI .schema 使用
    def get_stats(self, table: str) -> TableStats: ...  # JOIN planner 使用（新增）
```

### 7.2 并发控制接口

```python
# concurrency/lock_manager.py
class LockManager:
    def acquire(self, txn_id: int, page_id: int, mode: LockMode) -> bool: ...

# concurrency/mvcc_manager.py
class MVCCManager:
    def get_visible_version(self, page_id: int, snapshot: Snapshot) -> PageVersion: ...
```

### 7.3 CLI 接口

```python
# cli/highlighter.py
def highlight_sql(sql: str) -> str: ...

# cli/commands.py
class CommandHandler:
    def handle(self, cmd: str, arg: str, db: Database) -> str | None: ...
```

---

## 8. Worktree 并行开发策略

```
master (v0.1)
│
├── ../tinydb-v02-join/     (branch: feature/v0.2-join)
│   └── 开发 JOIN 功能
│
├── ../tinydb-v02-concurrency/  (branch: feature/v0.2-concurrency)
│   └── 开发并发控制
│
└── ../tinydb-v02-cli/      (branch: feature/v0.2-cli)
    └── 开发 CLI 增强
```

### 合并顺序

1. **先合并 CLI Change**（独立，冲突最小）
2. **再合并 JOIN Change**（改 executor/database）
3. **最后合并 Concurrency Change**（改 database/buffer_pool，冲突最多）

每个 change 合并前 rebase 到最新 master，解决冲突后运行全量测试。

---

## 9. 依赖变更

| 变更 | 新依赖 |
|------|--------|
| JOIN | 无新依赖（纯标准库） |
| Concurrency | 无新依赖（threading 标准库） |
| CLI | `pygments>=2.10`（语法高亮） |

`pyproject.toml`：
```
dependencies = [
    "pygments>=2.10",
]
```

---

## 10. 验证标准

- JOIN：全部类型 × 算法组合通过正确性测试，与 SQLite 对比一致
- Concurrency：多线程测试无数据竞争，死锁检测正确率 100%
- CLI：高亮不崩溃、补全命中率 > 90%、.explain 输出可读
- 全量回归：v0.1 + v0.2 所有变更的 tests/ 全部通过
