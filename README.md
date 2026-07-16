# tinydb

一个从零构建的 Python 嵌入式关系型数据库，用于教学和学习数据库核心原理。

当前版本: **v0.2.0**

## 特性

- **纯 SQL 字符串接口** — `db.execute("SELECT ...")`
- **PostgreSQL 风格 SQL 方言**
- **DDL**: `CREATE TABLE`, `DROP TABLE`
- **DML**: `INSERT`, `SELECT`, `UPDATE`, `DELETE`
- **多表 JOIN**: `INNER/LEFT/RIGHT/FULL OUTER/CROSS/NATURAL/SELF JOIN`
- **三种 JOIN 算法**: Nested Loop Join、Hash Join、Sort-Merge Join
- **代价优化**: 基于行数统计自动选择 JOIN 算法（小表 Nested Loop，大表 Hash Join）
- **条件查询**: `WHERE` (AND/OR, `IS NULL`)、`ORDER BY`、`LIMIT`、`OFFSET`
- **列约束**: `PRIMARY KEY`, `NOT NULL`, `UNIQUE`
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
│  JOIN Algorithms: NestedLoop / Hash / SortMerge          │
└──────────────────────┬──────────────────────────────────┘
                       │ Table API
┌──────────────────────┴──────────────────────────────────┐
│                   Storage Engine                         │
│  TypeSystem → RowFormat → Page → FileManager            │
│  BufferPool (LRU + pin/unpin + Page Latch)              │
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
| BufferPool | `tinydb/buffer_pool.py` | LRU 页缓存、pin/unpin、脏页管理、Page Latch |
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
| LockManager | `tinydb/concurrency/lock_manager.py` | 共享/独占锁管理 |
| MVCCManager | `tinydb/concurrency/mvcc_manager.py` | 多版本并发控制 |
| DeadlockDetector | `tinydb/concurrency/deadlock_detector.py` | 死锁检测与恢复 |
| Isolation | `tinydb/concurrency/isolation.py` | 隔离级别定义 |
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

tests/                   # pytest 测试套件 (473 tests)
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
| 缓冲池策略 | OrderedDict + 双链表 LRU | 兼顾代码简洁和算法教学 |
| 事务模型 | Shadow Paging | 实现简单、回滚自然、适合教学 |
| 并发模型 | 锁 + MVCC 混合 | 读不阻塞写、写不阻塞读 |
| JOIN 算法 | 三种 + 代价选择 | 覆盖不同场景的最优执行 |
| 死锁处理 | 超时 + 等待图 | 双重保障、自动恢复 |
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
- MVCC 版本 GC 为手动触发（无后台清理线程）
- 无 WAL（使用 Shadow Paging）
- 目录表使用 JSON 存储列定义（灵活可读）
- B-tree 不实现重平衡合并
- GROUP BY 仅支持内存哈希（不支持超大数据集）

## 测试

```bash
pytest tests/ -v
```

覆盖：类型检查、行序列化、页操作、缓冲池 LRU、文件管理、目录 CRUD、SQL 解析、JOIN 查询、查询执行、B-tree 索引、事务 ACID、并发控制、死锁检测、CLI 交互、端到端集成测试。

## 不为之事 (Out of Scope)

- ALTER TABLE、视图、触发器、外键
- 网络/客户端-服务器模式
- 真正的多进程并行查询执行
- 分布式事务

## License

MIT
