## Context

tinydb v0.1 采用 shadow paging 实现单事务原子性，`_active_txn` 全局变量限制同时只能有一个活跃事务。本模块引入锁 + MVCC 混合并发控制，使多事务可以并发执行：锁保证写互斥，MVCC 提供读快照。

设计原则：教学优先，模块边界清晰（LockManager / MVCCManager / DeadlockDetector / Isolation 各自独立），与 v0.1 shadow paging 兼容（MVCC 在上层提供读快照，shadow paging 保证页级原子性）。

## Goals / Non-Goals

**Goals:**
- 页级 Shared/Exclusive Lock 管理，含兼容性矩阵和 S→X 升级
- 多版本链 + 快照读，读不阻塞写、写不阻塞读
- 多事务并发管理（begin/commit/rollback + 快照）
- 死锁检测：超时（5s）+ 等待图环路检测
- 四种隔离级别定义，默认 REPEATABLE READ
- BufferPool 集成 page latch + MVCC 版本路由
- 与 v0.1 兼容：单事务时行为等价

**Non-Goals:**
- 表级锁（v0.2 仅页级）
- 分布式事务
- 无锁数据结构
- WAL（v0.2 仍用 shadow paging 保证持久性）
- SERIALIZABLE 的完整实现（接口预留，v0.2 仅默认实现 REPEATABLE READ）

## Decisions

### D1: 锁粒度选择页级

| 方案 | 优点 | 缺点 |
|------|------|------|
| 页级锁 | 与 buffer pool 页对应，实现简单，并发度适中 | 可能锁住无关行 |
| 行级锁 | 并发度最高 | 锁内存开销大，实现复杂 |
| 表级锁 | 实现最简单 | 并发度太低 |

选择页级：buffer pool 以页为管理单位，页级锁天然对齐，教学清晰，并发度够用。

### D2: MVCC 版本链按 txn_id 降序排列

每页维护一个版本链表，按创建事务 txn_id 降序。事务读快照时遍历链表找到第一个可见版本。降序排列使最新版本（最多读取）在链头，减少遍历。

### D3: 可见性判断规则

```
visible(version, snapshot) =
    version.created_txn in snapshot.active_txns
    AND version.deleted_txn NOT IN snapshot.active_txns
```

快照在事务开始时获取活跃事务列表。单事务时快照只含自身，与 v0.1 行为等价。

### D4: 死锁检测采用超时 + 等待图

| 方案 | 优点 | 缺点 |
|------|------|------|
| 仅超时 | 实现简单 | 可能误杀，延迟高 |
| 仅等待图 | 精确 | 维护有向图有开销 |
| 超时 + 等待图 | 精确 + 兜销 | 稍复杂 |

选择双轨：每次锁等待入队时检查环路（精确），超时作为兜底（5s）。

### D5: 牺牲者选择 youngest transaction

死锁环路中选择开始时间最晚（youngest）的事务中止。Youngest 事务做的最少，回滚代价最小。这是 PostgreSQL 的常用策略。

### D6: 默认隔离级别 REPEATABLE READ

| 级别 | 适用 | v0.2 状态 |
|------|------|-----------|
| READ UNCOMMITTED | 读无锁 | 接口预留 |
| READ COMMITTED | 语句级快照 | 接口预留 |
| REPEATABLE READ | 事务级快照（默认） | 默认实现 |
| SERIALIZABLE | 范围锁 + 2PL | 接口预留 |

默认 REPEATABLE READ 保证事务内多次读取一致，与 v0.1 单事务行为等价。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 页级锁并发度不足 | v0.2 教学场景够用，后续可升级为行级锁 |
| MVCC 版本链内存膨胀 | 定期 GC：清理无活跃事务引用的旧版本 |
| 死锁检测有向图维护成本 | 仅活跃等待边入图，释放锁时移除 |
| 多事务竞争 buffer pool 槽位 | BufferPool 扩容 + GC 回收旧版本释放空间 |
