# tinydb

一个从零构建的 Python 嵌入式关系型数据库，用于教学和学习数据库核心原理。

## 特性

- **纯 SQL 字符串接口** — `db.execute("SELECT ...")`
- **PostgreSQL 风格 SQL 方言**
- **DDL**: `CREATE TABLE`, `DROP TABLE`
- **DML**: `INSERT`, `SELECT`, `UPDATE`, `DELETE`
- **条件查询**: `WHERE` (AND/OR, `IS NULL`)、`ORDER BY`、`LIMIT`、`OFFSET`
- **列约束**: `PRIMARY KEY`, `NOT NULL`, `UNIQUE`
- **聚合函数**: `COUNT`, `SUM`, `AVG` + `GROUP BY`
- **B-tree 索引** 加速等值和范围查询
- **ACID 事务**: `BEGIN`, `COMMIT`, `ROLLBACK`（Shadow Paging）
- **单文件持久化** — 数据存储在单个 `.db` 文件
- **CLI/REPL** 交互式界面

## 快速开始

```python
from tinydb import Database

# 打开（或创建）数据库
db = Database("mydata.db")

# 建表
db.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        age INTEGER,
        score FLOAT
    )
""")

# 插入数据
db.execute("INSERT INTO users (id, name, age, score) VALUES (1, 'Alice', 30, 95.5)")
db.execute("INSERT INTO users (id, name, age, score) VALUES (2, 'Bob', 25, 88.0)")
db.execute("INSERT INTO users (id, name, age, score) VALUES (3, 'Charlie', 35, 92.3)")

# 条件查询
result = db.execute("SELECT name, score FROM users WHERE age > 25 ORDER BY score DESC")
for row in result.rows:
    print(row)

# 聚合
result = db.execute("SELECT COUNT(*), AVG(score) FROM users")
print(f"总数: {result.rows[0][0]}, 平均分: {result.rows[0][1]:.2f}")

# 事务
db.execute("BEGIN")
db.execute("UPDATE users SET score = 99.0 WHERE name = 'Alice'")
db.execute("COMMIT")

# 创建索引
db.execute("CREATE INDEX idx_age ON users (age)")

db.close()
```

或使用 REPL：

```bash
python -m tinydb.cli
tinydb> CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
tinydb> INSERT INTO users VALUES (1, 'Alice');
tinydb> SELECT * FROM users;
tinydb> .exit
```

## 架构

```
┌─────────────────────────────────────────────┐
│                  SQL Engine                  │
│  Lexer → Parser → Planner → Executor        │
│  (Scan/Filter/Project/Aggregate/Sort/Limit)  │
└──────────────────┬──────────────────────────┘
                   │ Table API
┌──────────────────┴──────────────────────────┐
│               Storage Engine                 │
│  TypeSystem → RowFormat → Page → FileManager │
│  BufferPool (LRU + pin/unpin)               │
│  Catalog (tinydb_master)                    │
│  B-tree Index + IndexManager                │
│  Transaction (Shadow Paging)                │
└─────────────────────────────────────────────┘
```

## 模块说明

| 模块 | 文件 | 说明 |
|------|------|------|
| TypeSystem | `tinydb/types.py` | DataType 枚举、ColumnDef、类型检查/转换 |
| RowFormat | `tinydb/row_format.py` | NULL 位图、行序列化/反序列化 |
| Page | `tinydb/page.py` | Slotted Page 数据结构、slot 管理 |
| FileManager | `tinydb/file_manager.py` | 文件 I/O、空闲页分配、文件头管理 |
| BufferPool | `tinydb/buffer_pool.py` | LRU 页缓存、pin/unpin、脏页管理 |
| Catalog | `tinydb/catalog.py` | 系统目录表、表元数据管理 |
| Table | `tinydb/table.py` | 表级 CRUD API |
| Lexer | `tinydb/sql/lexer.py` | SQL 词法分析器 |
| Parser | `tinydb/sql/parser.py` | 递归下降语法分析器 |
| Planner | `tinydb/sql/planner.py` | 查询计划器 |
| Executor | `tinydb/sql/executor.py` | 火山模型执行引擎 |
| B-tree | `tinydb/index/btree.py` | B-tree 索引结构 |
| IndexManager | `tinydb/index/index_manager.py` | 索引管理器 + DML 钩子 |
| Transaction | `tinydb/transaction/shadow_paging.py` | Shadow Paging 事务 |
| Database | `tinydb/database.py` | Database 公共入口 |
| CLI | `tinydb/cli/repl.py` | 交互式 REPL |

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
└── cli/                 # REPL
    └── repl.py

tests/                   # pytest 测试套件 (311 tests)
```

## 技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| SQL 方言 | PostgreSQL 风格 | 标准、可读 |
| 行存储模型 | Slotted Page | 经典教学模型 (SQLite/PostgreSQL) |
| 缓冲池策略 | OrderedDict + 双链表 LRU | 兼顾代码简洁和算法教学 |
| 事务模型 | Shadow Paging | 实现简单、回滚自然、适合教学 |
| 页大小 | 固定 4KB | 与 OS 内存页对齐 |
| B-tree 叶节点 | 存行指针 (非聚簇) | 教学演示、避免数据物理重组 |
| 目录表 | 自描述 Catalog | 数据库"认识自己" |
| 执行模型 | Volcano/Iterator | 经典数据库执行架构 |
| 聚合 | 内存哈希聚合 | 实现简单、教学足够 |
| B-tree 删除 | 懒删除（不合并） | 教学简化 |

## 设计取舍

**优先教学可读性**，在以下方面做了简化：

- 不支持并发（单 Writer）
- 删除后空间不立即回收（无 compaction）
- 无 WAL（使用 Shadow Paging）
- 目录表使用 JSON 存储列定义（灵活可读）
- B-tree 不实现重平衡合并
- GROUP BY 仅支持内存哈希（不支持超大数据集）

## 测试

```bash
pytest tests/ -v
```

覆盖：类型检查、行序列化、页操作、缓冲池 LRU、文件管理、目录 CRUD、SQL 解析、查询执行、B-tree 索引、事务 ACID、端到端集成测试。

## 不为之事 (Out of Scope)

- 多表 JOIN 查询
- 并发控制（多线程/多进程）
- ALTER TABLE、视图、触发器、外键
- 网络/客户端-服务器模式

## License

MIT
