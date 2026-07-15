# Comet Design Handoff

- Change: tinydb-index-txn
- Phase: design
- Mode: compact
- Context hash: 0626ac403a3011bbfd03215e70b4e17c65c8663ac2173b15fa06e9a8037a353e

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/tinydb-index-txn/proposal.md

- Source: openspec/changes/tinydb-index-txn/proposal.md
- Lines: 1-34
- SHA256: 229b75afcc9c90b39f00f06025451ab039640ab667e52bc1f2812beee98e38c8

```md
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

```

## openspec/changes/tinydb-index-txn/design.md

- Source: openspec/changes/tinydb-index-txn/design.md
- Lines: 1-92
- SHA256: 8e69d350a8dc056352fab1a60b1f08f119fae24311a30ef5cd5e5db8a1755b5b

[TRUNCATED]

```md
## Context

顶层模块整合存储引擎和 SQL 引擎，引入索引加速和事务保证，并通过 CLI 提供交互界面。本模块依赖前两层的所有 API，是面向用户的最终产品层。

教学优先原则：Shadow Paging 的事务机制实现清晰可见；B-tree 操作有可视化调试接口。

## Goals / Non-Goals

**Goals:**
- B-tree 索引：等值查询 O(log n)、范围查询有序遍历
- Shadow Paging 事务：页级写时复制，天然支持 ROLLBACK
- ACID 原子性和持久性
- CLI REPL：交互式 SQL 输入执行和结果展示
- Database 类统一 API：`Database(path)` → `execute(sql)` → `fetchall()`

**Non-Goals:**
- 多隔离级别（仅语句级一致性）
- 并发事务（单 Writer）
- WAL 事务模式（未来可选）
- 分布式事务

## Decisions

### D1: B-tree 节点大小与页大小一致

B-tree 节点直接映射到存储页（4KB），便于缓冲池管理。

```
┌─────────────────────────────────────────┐
│  B-tree Internal Node                   │
│  ├─ page_header                         │
│  ├─ keys: [k1, k2, ..., kn]             │
│  └─ children: [p0, p1, ..., pn]         │
├─────────────────────────────────────────┤
│  B-tree Leaf Node                       │
│  ├─ page_header                         │
│  ├─ keys: [k1, k2, ..., kn]             │
│  └─ values: [v1, v2, ..., vn]           │
│     (v 为行指针: (page_id, slot))       │
└─────────────────────────────────────────┘
```

### D2: B-tree 叶节点存行指针（非聚簇）

叶节点存储 `(key, row_pointer)` 对，row_pointer 指向实际数据页中的行。适合教学演示，避免数据物理重组。

### D3: Shadow Paging 实现

```
┌─────────────────────────────────────────┐
│  Shadow Paging 原理                     │
│                                         │
│  BEGIN → 创建 master page 快照          │
│                                         │
│  Write:                                 │
│  ┌──────┐    ┌──────┐                  │
│  │ Page │ →  │ Page │ (copy-on-write)  │
│  │  A   │    │  A'  │                  │
│  └──────┘    └──────┘                  │
│                                         │
│  COMMIT → master 指向新根              │
│  ROLLBACK → 丢弃影子页，恢复 master     │
└─────────────────────────────────────────┘
```

写时复制：修改页时先复制到影子页，修改影子页，COMMACT 时原子切换根指针。

### D4: B-tree 阶数由页大小决定

阶数 = `(page_size - header_size) / (key_size + pointer_size)`，无需手动配置。

### D5: CLI REPL 使用 Python readline

基础 REPL，支持多行 SQL（以分号结束）、历史记录（上下方向键）、退出命令（`.exit`）。不引入额外依赖。

### D6: 事务状态管理

```
Transaction:
  - txn_id: 唯一标识

```

Full source: openspec/changes/tinydb-index-txn/design.md

## openspec/changes/tinydb-index-txn/tasks.md

- Source: openspec/changes/tinydb-index-txn/tasks.md
- Lines: 1-68
- SHA256: 857d577b48dacaa715ea85194e4543b1f51f8f2e5a159ac56d95d50b502e8639

```md
## 1. B-tree 索引

- [ ] 1.1 定义 BTreeNode 结构（内部节点、叶节点、序列化/反序列化到页）
- [ ] 1.2 实现 BTreeIndex 类：空树创建
- [ ] 1.3 实现 insert(key, value) 方法
- [ ] 1.4 实现叶节点分裂逻辑
- [ ] 1.5 实现内部节点分裂逻辑
- [ ] 1.6 实现 search(key) 等值查找
- [ ] 1.7 实现 range_scan(start, end) 范围查询
- [ ] 1.8 实现 delete(key) 方法
- [ ] 1.9 编写 btree 单元测试（含持久化测试）

## 2. 索引管理器

- [ ] 2.1 实现 IndexManager 类：注册表的所有索引
- [ ] 2.2 实现 create_index(table, column, name) 接口
- [ ] 2.3 实现 drop_index(name) 接口
- [ ] 2.4 实现 get_index(table, column) 查询
- [ ] 2.5 实现 DML 时自动更新索引
- [ ] 2.6 编写 index-manager 单元测试

## 3. Shadow Paging 事务

- [ ] 3.1 实现 Transaction 类：事务状态管理
- [ ] 3.2 实现 copy_on_write(page_id) 影子页创建
- [ ] 3.3 实现 begin() 方法（创建 master 快照）
- [ ] 3.4 实现 commit() 方法（原子切换根指针）
- [ ] 3.5 实现 rollback() 方法（丢弃影子页）
- [ ] 3.6 编写 shadow-paging 单元测试

## 4. 事务管理器

- [ ] 4.1 实现 TransactionManager 类：事务生命周期管理
- [ ] 4.2 实现 BEGIN/COMMIT/ROLLBACK SQL 语句处理
- [ ] 4.3 实现错误自动回滚
- [ ] 4.4 集成到 SQL 执行路径
- [ ] 4.5 编写 transaction 单元测试

## 5. CLI REPL

- [ ] 5.1 实现 REPL 循环（读取-执行-打印）
- [ ] 5.2 实现多行 SQL 输入（分号终止）
- [ ] 5.3 实现结果表格展示（对齐列、表头）
- [ ] 5.4 实现元命令（.exit, .tables, .schema, .help）
- [ ] 5.5 实现 readline 历史记录
- [ ] 5.6 编写 REPL 集成测试

## 6. Database 入口

- [ ] 6.1 实现 Database 类（持有存储引擎、SQL 引擎、事务管理器）
- [ ] 6.2 实现 execute(sql) 方法
- [ ] 6.3 实现 commit() / rollback() 方法
- [ ] 6.4 实现 close() 方法
- [ ] 6.5 实现上下文管理器 (__enter__ / __exit__)
- [ ] 6.6 编写 Database 单元测试

## 7. 索引增强执行器

- [ ] 7.1 实现 IndexScanOperator（替换全表扫描当索引可用时）
- [ ] 7.2 在 Planner 中增加索引选择逻辑
- [ ] 7.3 编写索引加速查询测试

## 8. Integration

- [ ] 8.1 三层完整集成端到端测试
- [ ] 8.2 事务回滚后索引一致性测试
- [ ] 8.3 编写 README 与使用文档
- [ ] 8.4 性能基准测试（对比全表扫描 vs 索引扫描）

```

## openspec/changes/tinydb-index-txn/specs/btree-index/spec.md

- Source: openspec/changes/tinydb-index-txn/specs/btree-index/spec.md
- Lines: 1-52
- SHA256: 1738fca87fc34e53b2f3fac7756b4ccbfb1aa235288235838965513869873c2e

```md
## ADDED Requirements

### Requirement: B-tree 插入键值对
The system SHALL support inserting a (key, value) pair into a B-tree index.

#### Scenario: 空树插入
- **WHEN** 向空 B-tree 插入 (25, row_ptr)
- **THEN** B-tree 根节点包含一个叶节点，存储该键值对

#### Scenario: 触发节点分裂
- **WHEN** 插入导致叶节点超过阶数限制
- **THEN** 叶节点分裂为两个，中位键提升至父节点

### Requirement: B-tree 等值查找
The system SHALL support searching for a specific key and returning the associated value(s).

#### Scenario: 查找存在的键
- **WHEN** B-tree 中存在键 42
- **THEN** 返回 42 对应的 row pointer

#### Scenario: 查找不存在的键
- **WHEN** B-tree 中不存在键 99
- **THEN** 返回空结果

### Requirement: B-tree 范围扫描
The system SHALL support range queries (e.g., `key >= 10 AND key <= 50`) returning all matching key-value pairs in sorted order.

#### Scenario: 范围查询
- **WHEN** 查询范围 [20, 40]
- **THEN** 按 key 升序返回所有匹配的键值对

#### Scenario: 左开区间
- **WHEN** 查询 `key > 10`
- **THEN** 返回所有 key > 10 的键值对，升序

### Requirement: B-tree 删除键
The system SHALL support deleting a key from the B-tree.

#### Scenario: 删除存在的键
- **WHEN** 删除存在的键
- **THEN** 键被移除，B-tree 保持有效结构

### Requirement: B-tree 节点映射到存储页
The system SHALL serialize/deserialize B-tree nodes to/from storage pages.

#### Scenario: 持久化
- **WHEN** 包含 B-tree 的数据库关闭后重新打开
- **THEN** B-tree 结构完整恢复

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-index-txn/specs/database/spec.md

- Source: openspec/changes/tinydb-index-txn/specs/database/spec.md
- Lines: 1-40
- SHA256: 1553eb2ac49d6558d134e01d50d662616e7d9784158bedf2c44006ec69355f28

```md
## ADDED Requirements

### Requirement: Database 类入口
The system SHALL provide a Database class as the primary user-facing API.

#### Scenario: 创建/打开数据库
- **WHEN** db = Database("mydata.db")
- **THEN** 打开或创建数据库实例

### Requirement: execute 方法
The system SHALL provide an execute(sql) method to run SQL statements.

#### Scenario: 执行 SQL
- **WHEN** db.execute("SELECT * FROM users")
- **THEN** 执行 SQL 并返回结果集

### Requirement: commit/rollback 方法
The system SHALL provide commit() and rollback() methods for explicit transaction control.

#### Scenario: 显式提交
- **WHEN** db.execute("BEGIN"); db.execute("INSERT ..."); db.commit()
- **THEN** 插入的数据持久化

### Requirement: close 方法
The system SHALL provide a close() method to cleanly shut down the database.

#### Scenario: 关闭数据库
- **WHEN** db.close()
- **THEN** 所有脏页刷盘，文件句柄关闭

### Requirement: 上下文管理器支持
The system SHALL support `with Database(path) as db:` syntax for automatic resource management.

#### Scenario: 使用 with 语句
- **WHEN** with Database("data.db") as db: db.execute(...)
- **THEN** 退出 with 块时自动调用 close()

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-index-txn/specs/index-manager/spec.md

- Source: openspec/changes/tinydb-index-txn/specs/index-manager/spec.md
- Lines: 1-26
- SHA256: 66e262f1b9dc4e60b0696bf51df6b974d868083071ae6bf8cc5f05e1f8edff8e

```md
## ADDED Requirements

### Requirement: 创建索引
The system SHALL support creating a B-tree index on a table column via CREATE INDEX.

#### Scenario: 创建单列索引
- **WHEN** 执行 CREATE INDEX idx_age ON users (age)
- **THEN** 在 age 列上创建 B-tree 索引

### Requirement: 列出表索引
The system SHALL maintain metadata about all indexes associated with each table.

#### Scenario: 查看索引元数据
- **WHEN** 查询某表的索引信息
- **THEN** 返回所有索引名称和对应列

### Requirement: 删除索引
The system SHALL support dropping an index via DROP INDEX.

#### Scenario: 删除索引
- **WHEN** 执行 DROP INDEX idx_age
- **THEN** 索引被删除，后续查询不再使用该索引

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-index-txn/specs/repl/spec.md

- Source: openspec/changes/tinydb-index-txn/specs/repl/spec.md
- Lines: 1-43
- SHA256: ad31c2c788a4e1918d66a9054bac0fdbd81c635d8cf90b510dd773851d4b536f

```md
## ADDED Requirements

### Requirement: REPL 交互循环
The system SHALL provide an interactive REPL that accepts SQL input and displays results.

#### Scenario: 执行查询
- **WHEN** 用户在 REPL 输入 "SELECT * FROM users;"
- **THEN** 执行查询并以表格形式展示结果

### Requirement: 多行 SQL 输入
The system SHALL support multi-line SQL statements terminated by semicolon.

#### Scenario: 多行输入
- **WHEN** 用户输入多行后以分号结束
- **THEN** 系统合并多行作为一条 SQL 执行

### Requirement: 元命令支持
The system SHALL support REPL meta-commands:
- `.exit` or `.quit` — 退出 REPL
- `.tables` — 列出所有表
- `.schema <table>` — 显示表结构

#### Scenario: 查看表列表
- **WHEN** 用户输入 ".tables"
- **THEN** 显示数据库中所有表名

### Requirement: 错误提示
The system SHALL display errors (syntax errors, constraint violations) in a user-friendly format.

#### Scenario: 语法错误
- **WHEN** 输入无效 SQL
- **THEN** 显示错误信息，不崩溃

### Requirement: 历史记录
The system SHALL support command history navigation (up/down arrow).

#### Scenario: 调出历史命令
- **WHEN** 用户按上箭头
- **THEN** 显示上一条输入的 SQL

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-index-txn/specs/shadow-paging/spec.md

- Source: openspec/changes/tinydb-index-txn/specs/shadow-paging/spec.md
- Lines: 1-33
- SHA256: ae5343a60bdffa7a4cb0300b54cfe64b79cd728faec215a056b69651e3bb7c0d

```md
## ADDED Requirements

### Requirement: 写时复制 (Copy-on-Write)
The system SHALL copy a page before modification, preserving the original for rollback.

#### Scenario: 修改页时复制
- **WHEN** 事务中修改页 A
- **THEN** 创建影子页 A'，修改作用于 A'，原页 A 保持不变

### Requirement: 原子提交
The system SHALL atomically switch the root pointer on COMMIT.

#### Scenario: 提交事务
- **WHEN** COMMIT 调用
- **THEN** 根指针原子切换到新状态，所有修改生效

### Requirement: 回滚恢复
The system SHALL restore the pre-transaction state on ROLLBACK.

#### Scenario: 回滚事务
- **WHEN** ROLLBACK 调用
- **THEN** 所有影子页被丢弃，数据恢复到事务前状态

### Requirement: 脏页追踪
The system SHALL track all shadow pages created during a transaction for cleanup.

#### Scenario: 长时间事务
- **WHEN** 事务修改 10 页后回滚
- **THEN** 10 个影子页均被释放，内存被回收

## MODIFIED Requirements

（无）

```

## openspec/changes/tinydb-index-txn/specs/transaction/spec.md

- Source: openspec/changes/tinydb-index-txn/specs/transaction/spec.md
- Lines: 1-40
- SHA256: 3c83b36c80f21a23f39f8a8770bc60e69a4057ae890bb814751d5de548d69f7d

```md
## ADDED Requirements

### Requirement: BEGIN 开启事务
The system SHALL support BEGIN statement to start a transaction.

#### Scenario: 开启事务
- **WHEN** 执行 BEGIN
- **THEN** 系统进入事务状态，后续修改可回滚

### Requirement: COMMIT 提交事务
The system SHALL support COMMIT statement to finalize a transaction.

#### Scenario: 提交成功
- **WHEN** 执行 COMMIT
- **THEN** 所有修改持久化，事务结束

### Requirement: ROLLBACK 回滚事务
The system SHALL support ROLLBACK statement to undo a transaction.

#### Scenario: 回滚成功
- **WHEN** 执行 ROLLBACK
- **THEN** 所有修改被撤销，数据恢复事务前状态

### Requirement: 自动回滚错误
The system SHALL automatically rollback on statement execution errors.

#### Scenario: 执行出错
- **WHEN** 事务中某条 SQL 执行失败
- **THEN** 自动回滚当前事务所有修改

### Requirement: 事务内一致性
The system SHALL provide statement-level consistency within a transaction.

#### Scenario: 事务内读到自己的写入
- **WHEN** 事务中 INSERT 后 SELECT
- **THEN** SELECT 能看到刚插入的数据

## MODIFIED Requirements

（无）

```
