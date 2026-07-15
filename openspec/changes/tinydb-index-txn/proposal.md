## Why

tinydb 需要 B-tree 索引加速等值/范围查询，提供基于 Shadow Paging 的 ACID 事务保证，以及 CLI/REPL 交互界面。这是三层中的顶层，将存储和 SQL 能力封装为可交互的数据库产品。依赖 `tinydb-storage` 和 `tinydb-sql`。

## What Changes

- 新增 B-tree 索引结构：支持插入、删除、等值查找、范围扫描
- 新增 Shadow Paging 事务管理：BEGIN、COMMIT、ROLLBACK
- 新增隔离级别支持（基础：语句级一致性）
- 新增 CLI/REPL 交互式界面
- 增强 SQL 执行器支持索引扫描（替换全表扫描）
- 新增 Database 类统一接口

## Capabilities

### New Capabilities
- `btree-index`: B-tree 索引结构，支持等值查找和范围扫描（节点大小 = 页大小）
- `index-manager`: 索引管理器，维护表的索引元数据
- `shadow-paging`: Shadow Paging 事务实现，支持页级写时复制
- `transaction`: 事务管理器，BEGIN/COMMIT/ROLLBACK 接口
- `repl`: 交互式 SQL 命令行界面
- `database`: Database 统一入口类

### Modified Capabilities

（无 — 但 tinydb-sql 的 Scan 算子需要增强为 IndexScan 算子）

## Impact

- 新增包 `tinydb/index/`（btree.py、index_manager.py）
- 新增包 `tinydb/transaction/`（shadow_paging.py、txn_manager.py）
- 新增包 `tinydb/cli/`（repl.py）
- 增强 `tinydb/sql/executor.py`（新增 IndexScanOperator）
- 用户通过 Database 类或 REPL 使用完整功能
