# tinydb

一个从零构建的 Python 嵌入式关系型数据库，用于教学和学习数据库核心原理。

## 特性

- **纯 SQL 字符串接口** — `db.execute("SELECT ...")`
- **PostgreSQL 风格 SQL 方言**
- **DDL**: `CREATE TABLE`, `DROP TABLE`
- **DML**: `INSERT`, `SELECT`, `UPDATE`, `DELETE`
- **条件查询**: `WHERE` (AND/OR)、`ORDER BY`、`LIMIT`、`OFFSET`
- **列约束**: `PRIMARY KEY`, `NOT NULL`, `UNIQUE`
- **聚合函数**: `COUNT`, `SUM`, `AVG` + `GROUP BY`
- **B-tree 索引** 加速等值和范围查询
- **ACID 事务**: `BEGIN`, `COMMIT`, `ROLLBACK`（Shadow Paging）
- **单文件持久化** — 数据存储在单个 `.db` 文件
- **CLI/REPL** 交互式界面

## 架构

```
┌─────────────────────────────────────────────┐
│                  SQL Engine                  │
│  Lexer → Parser → Planner → Executor        │
└──────────────────┬──────────────────────────┘
                   │ Table API
┌──────────────────┴──────────────────────────┐
│               Storage Engine                 │
│  TypeSystem → RowFormat → Page → FileManager │
│                                   BufferPool │
│  Catalog (tinydb_master)                     │
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
└── exceptions.py        # 异常体系

tests/                   # pytest 测试套件
docs/
├── superpowers/
│   ├── specs/           # Design Doc
│   └── plans/           # 实施计划
└── changes/             # OpenSpec change 目录
    ├── archive/         # 已归档 change
    ├── tinydb-sql/      # SQL 引擎 (进行中)
    └── tinydb-index-txn/ # 索引+事务+CLI (进行中)
```

## 开发状态

| Change | 阶段 | 说明 |
|--------|------|------|
| `tinydb-storage` | ✅ 已完成 | 存储引擎（80 tests, archived） |
| `tinydb-sql` | ⏳ 设计中 | SQL 解析器 + 执行引擎 |
| `tinydb-index-txn` | ⏳ 设计中 | B-tree + 事务 + CLI |

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

## 设计取舍

**优先教学可读性**，在以下方面做了简化：

- 不支持并发（单 Writer）
- 删除后空间不立即回收（无 compaction）
- 无 WAL（使用 Shadow Paging）
- 目录表使用 JSON 存储列定义（灵活可读）

## 测试

```bash
pytest tests/ -v
```

当前覆盖：类型检查、行序列化、页操作、缓冲池 LRU、文件管理、目录 CRUD、端到端集成测试。

## 不为之事 (Out of Scope)

- 多表 JOIN 查询
- 并发控制（多线程/多进程）
- ALTER TABLE、视图、触发器、外键
- 网络/客户端-服务器模式

## License

MIT
