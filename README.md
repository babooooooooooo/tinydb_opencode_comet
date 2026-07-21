# tinydb

一个从零构建的 Python 嵌入式关系型数据库，用于教学和学习数据库核心原理。

**版本**: tinydb v0.2  
**仓库**: https://github.com/babooooooooooo/tinydb_opencode_comet  
**开发工具**: Open Code + LongCat + Comet  
**代码量级**: 源码 4,389 行，测试代码 3,662 行  
**测试**: 473 个测试（单元测试占比 89.8%），覆盖率 87%

## 特性

- **纯 SQL 字符串接口** — `db.execute("SELECT ...")`
- **PostgreSQL 风格 SQL 方言**
- **DDL**: `CREATE TABLE`, `DROP TABLE`
- **DML**: `INSERT`, `SELECT`, `UPDATE`, `DELETE`
- **多表 JOIN**: `INNER/LEFT/RIGHT/FULL OUTER/CROSS/NATURAL/SELF JOIN`
- **两种 JOIN 算法**: Nested Loop Join、Hash Join
- **代价优化**: 基于行数统计自动选择 JOIN 算法（小表 Nested Loop，大表 Hash Join）
- **条件查询**: `WHERE` (AND/OR, `IS NULL`)、`ORDER BY`、`LIMIT`、`OFFSET`
- **列约束**: `PRIMARY KEY`, `NOT NULL`, `UNIQUE`（利用 B-tree 索引加速检查）
- **聚合函数**: `COUNT`, `SUM`, `AVG` + `GROUP BY`
- **B-tree 索引** 加速等值和范围查询
- **ACID 事务**: `BEGIN`, `COMMIT`, `ROLLBACK`（Shadow Paging + MVCC）
- **并发控制**: 锁 + Shadow Paging 混合模型，Database→Table→BufferPool 全链路集成，多线程安全
- **隔离级别**: `READ UNCOMMITTED`/`READ COMMITTED`/`REPEATABLE READ`/`SERIALIZABLE`
- **死锁检测**: 等待图 + 超时检测，自动选择牺牲者
- **单文件持久化** — 数据存储在单个 `.db` 文件
- **CLI/REPL** 交互式界面，语法高亮，自动补全，执行计划可视化，历史持久化

## 快速开始

```bash
# 安装后直接使用 tinydb 命令
tinydb

# 或指定数据库文件路径
tinydb mydata.db

# 也可以使用 python 模块方式
python3 -m tinydb.cli mydata.db
```

```
tinydb> CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
tinydb> CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount FLOAT);
tinydb> INSERT INTO users VALUES (1, 'Alice');
tinydb> INSERT INTO orders VALUES (1, 1, 99.5);
tinydb> SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id;
tinydb> .explain SELECT * FROM users WHERE id = 1;
tinydb> .exit
```

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                      SQL Engine                          │
│  Lexer → Parser → Planner → Executor                    │
│  (Scan/Filter/Project/Aggregate/Sort/Limit/Join)         │
│  JOIN Algorithms: NestedLoop / Hash                      │
└──────────────────────┬──────────────────────────────────┘
                        │ Table API
┌──────────────────────┴──────────────────────────────────┐
│                   Storage Engine                         │
│  TypeSystem → RowFormat → Page → FileManager            │
│  BufferPool (OrderedDict LRU + pin/unpin)               │
│  Catalog (tinydb_master)                                │
│  B-tree Index + IndexManager                            │
│  Transaction (Shadow Paging)                            │
├─────────────────────────────────────────────────────────┤
│                  Concurrency Layer                        │
│  LockManager (S/X locks, compatibility matrix, timeout) │
│  MVCCManager (version chain, snapshot, GC)              │
│  DeadlockDetector (wait-for graph, cycle detection)     │
│  Isolation Levels (4 levels, default REPEATABLE READ)   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                     CLI/REPL                             │
│  SQLHighlighter (pygments) / SQLCompleter (readline)    │
│  Commands: .explain / .import / .dump / .timing /       │
│            .highlight                                    │
│  历史持久化 (~/.tinydb_history)                          │
└─────────────────────────────────────────────────────────┘
```

## 模块说明

| 模块 | 文件 | 说明 |
|------|------|------|
| TypeSystem | `tinydb/types.py` | DataType 枚举、ColumnDef、类型检查/转换 |
| RowFormat | `tinydb/row_format.py` | NULL 位图、行序列化/反序列化 |
| Page | `tinydb/page.py` | Slotted Page 数据结构、slot 管理 |
| FileManager | `tinydb/file_manager.py` | 文件 I/O、空闲页分配、文件头管理 |
| BufferPool | `tinydb/buffer_pool.py` | LRU 页缓存 (OrderedDict)、pin/unpin、脏页管理 |
| Catalog | `tinydb/catalog.py` | 系统目录表、表元数据管理 |
| Table | `tinydb/table.py` | 表级 CRUD API |
| Lexer | `tinydb/sql/lexer.py` | SQL 词法分析器 |
| Parser | `tinydb/sql/parser.py` | 递归下降语法分析器 |
| Planner | `tinydb/sql/planner.py` | 查询计划器（含 JOIN 优化） |
| Executor | `tinydb/sql/executor.py` | 火山模型执行引擎（含 JOIN 算子） |
| B-tree | `tinydb/index/btree.py` | B-tree 索引结构 |
| IndexManager | `tinydb/index/index_manager.py` | 索引管理器 + DML 钩子 |
| Transaction | `tinydb/transaction/shadow_paging.py` | Shadow Paging 事务 |
| TxnManager | `tinydb/transaction/txn_manager.py` | 多事务管理器 |
| LockManager | `tinydb/concurrency/lock_manager.py` | 共享/独占锁管理 + 死锁检测 |
| MVCCManager | `tinydb/concurrency/mvcc_manager.py` | 多版本并发控制 |
| DeadlockDetector | `tinydb/concurrency/deadlock_detector.py` | 死锁检测与恢复 |
| Isolation | `tinydb/concurrency/isolation.py` | 隔离级别定义 |
| QueryResult | `tinydb/query_result.py` | 查询结果类型 |
| Database | `tinydb/database.py` | Database 公共入口 |
| CLI/REPL | `tinydb/cli/repl.py` | 交互式 REPL |
| CLI 入口 | `tinydb/cli/__main__.py` | `tinydb` 命令入口 |
| Highlighter | `tinydb/cli/highlighter.py` | SQL 语法高亮 |
| Completer | `tinydb/cli/completer.py` | 自动补全 |
| Commands | `tinydb/cli/commands.py` | 扩展命令 |

## 项目结构

```
tinydb/
├── __init__.py          # 公共 API 导出
├── types.py             # 数据类型系统
├── row_format.py        # 行序列化
├── page.py              # Slotted Page
├── file_manager.py      # 文件管理
├── buffer_pool.py       # LRU 缓冲池
├── catalog.py           # 系统目录
├── table.py             # 表 CRUD
├── constants.py         # 全局常量
├── exceptions.py        # 异常体系
├── query_result.py      # 查询结果类型
├── database.py          # Database 入口
├── sql/                 # SQL 引擎
│   ├── lexer.py
│   ├── parser.py
│   ├── planner.py
│   └── executor.py
├── index/               # 索引
│   ├── btree.py
│   └── index_manager.py
├── transaction/         # 事务
│   ├── shadow_paging.py
│   └── txn_manager.py
├── concurrency/         # 并发控制
│   ├── __init__.py
│   ├── lock_manager.py
│   ├── mvcc_manager.py
│   ├── deadlock_detector.py
│   └── isolation.py
└── cli/                 # REPL + 增强
    ├── __main__.py
    ├── repl.py
    ├── highlighter.py
    ├── completer.py
    └── commands.py

tests/                   # pytest 测试套件 (444 tests)
├── concurrency/          # 并发控制测试
│   ├── test_lock_manager.py
│   ├── test_mvcc_manager.py
│   ├── test_deadlock_detector.py
│   ├── test_isolation.py
│   └── test_exports.py
├── sql/                  # SQL 引擎测试
│   ├── test_join_lexer.py
│   ├── test_join_parser.py
│   ├── test_join_planner.py
│   ├── test_join_executor.py
│   ├── test_join_ast.py
│   ├── test_join_integration.py
│   └── ... (其他 SQL 测试)
└── ... (其他测试)
```

## 技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| SQL 方言 | PostgreSQL 风格 | 标准、可读 |
| 行存储模型 | Slotted Page | 经典教学模型 (SQLite/PostgreSQL) |
| 缓冲池策略 | OrderedDict LRU | 代码简洁、O(1) 读写、算法教学 |
| 事务模型 | Shadow Paging | 实现简单、回滚自然、适合教学 |
| 并发模型 | 锁 + MVCC 混合 | 读不阻塞写、写不阻塞读 |
| JOIN 算法 | 两种 + 代价选择 | 覆盖不同场景的最优执行 |
| 死锁处理 | 等待图 + 超时 | 双重保障、自动恢复 |
| CLI 高亮 | pygments | 成熟稳定、多语言支持 |
| 页大小 | 固定 4KB | 与 OS 内存页对齐 |
| B-tree 叶节点 | 存行指针 (非聚簇) | 教学演示、避免数据物理重组 |
| 目录表 | 自描述 Catalog | 数据库"认识自己" |
| 执行模型 | Volcano/Iterator | 经典数据库执行架构 |
| 聚合 | 内存哈希聚合 | 实现简单、教学足够 |
| B-tree 删除 | 懒删除（不合并） | 教学简化 |

## 设计取舍

**优先教学可读性**，在以下方面做了简化：

- 并发控制在页粒度实现（S/X 锁），多线程读写安全
- 删除后空间不立即回收（无 compaction）
- MVCC 版本 GC 在每次 commit 时自动触发
- 无 WAL（使用 Shadow Paging）
- 目录表使用 JSON 存储列定义（灵活可读）
- B-tree 不实现重平衡合并
- GROUP BY 仅支持内存哈希（不支持超大数据集）

## 测试

```bash
pytest tests/ -v
```

覆盖：类型检查、行序列化、页操作、缓冲池 LRU、文件管理、目录 CRUD、SQL 解析、JOIN 查询、查询执行、B-tree 索引、事务 ACID、并发控制、死锁检测、CLI 交互、端到端集成测试。

## 最近修复 (v0.2.4)

### CRITICAL
- **修复事务 SELECT 不可见自身写入** — 正确传递 shadow pool 到 planner，事务内 SELECT/INSERT/UPDATE/DELETE 均可看到未提交的修改
- **修复索引绕过事务** — B-tree 写入经 buffer pool CoW 路由，ROLLBACK 后索引不再残留无效条目
- **修复解析错误误杀事务** — SQL 解析/词法错误不再触发自动回滚（符合 SQL 标准行为）

### HIGH
- **BufferPool 线程安全** — 添加 threading.Lock 保护 cache/pinned 数据结构，消除并发竞态
- **表扫描隔离** — 扫描期间持有根页共享锁，防止并发页链修改
- **多事务支持** — 按 txn_id 确定性选择活动事务，支持多事务并发

### MEDIUM
- **MVCC GC 自动触发** — 每次 commit 后自动回收不可见版本，防止内存泄漏
- **B-tree 内部节点容量** — 分别计算 leaf/internal max_keys，减少不必要的分裂
- **删除死代码** — 移除未使用的 `IndexScanOperator` 类及关联测试
- **清理无用属性** — 删除 commit 中对不存在的 `_head`/`_tail` 的属性写入

### LOW
- **锁释放惊群修复** — 仅在锁完全释放时唤醒所有等待者，否则仅唤醒一个
- **NULL 排序合规** — `ORDER BY ASC` 中 NULL 排首位（SQL 标准行为）
- **影子页脏页跟踪** — 所有影子页写入经 buffer pool dirty 跟踪，确保一致性

### 代码卫生
- 修复 27 处 F401/F841/E402 警告，源码和测试 ruff 零警告

## 历史修复 (v0.2.3)

- 统一 `QueryResult` 类型，消除重复定义和字段顺序不一致
- 接入 `DeadlockDetector` 到 `LockManager`，实现真正的死锁检测
- 修复 MVCC 写路径，`ensure_shadow` 创建影子页时记录版本
- 修复 `ensure_shadow` 竞态条件（整个函数体在锁内执行）
- UNIQUE/PRIMARY KEY 约束检查利用 B-tree 索引加速（O(log n) vs O(n)）
- 精简 BufferPool：移除冗余双向链表，改用 OrderedDict + pinned set
- 修复 bool/int 类型混淆（INTEGER 列不再接受 bool 值）
- 提取 `ColumnDef.to_dict()` 消除 3 处重复的 JSON 序列化
- 修复 SortOperator 双重 evaluate（用闭包缓存排序 key）
- 修复 Catalog 写失败时的页泄漏（失败时回滚已分配页）
- 优化 `slot_count` 读取（直接 struct.unpack_from 替代全 dict 解析）
- 优化文件扩展（单次批量写入替代逐页循环）
- 移除不可达的 sort_merge 分支
- 删除死代码 `sql/database.py` (99行) 和重复测试

## 不为之事 (Out of Scope)

- ALTER TABLE、视图、触发器、外键
- 网络/客户端-服务器模式
- 真正的多进程并行查询执行
- 分布式事务

## License

MIT
