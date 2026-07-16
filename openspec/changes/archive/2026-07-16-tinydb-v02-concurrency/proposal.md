## Why

tinydb v0.1 仅支持单事务串行执行，无法处理多事务并发场景。本_change_引入锁 + MVCC 混合并发控制模型，使 tinydb 支持多事务同时活跃、读不阻塞写、写不阻塞读，并具备死锁检测与恢复能力。

## What Changes

- 新增页级 LockManager：管理 Shared/Exclusive 锁的获取、释放、升级
- 新增 MVCCManager：维护数据页多版本链，提供快照读可见性判断
- 新增 DeadlockDetector：超时检测 + 等待图环路检测
- 新增隔离级别定义与校验模块（默认 REPEATABLE READ）
- 重构 TransactionManager：支持多事务并发（从单 `_active_txn` 改为 `_active_txns` 字典）
- 改造 BufferPool：pin/unpin 内部集成 LockManager，读操作获取 MVCC 可见版本

## Capabilities

### New Capabilities
- `lock-manager`: 页级 Shared/Exclusive Lock 管理，含兼容性矩阵、FIFO 等待队列、S→X 升级
- `mvcc-manager`: 多版本链管理，快照读可见性判断，版本 GC
- `deadlock-detector`: 超时检测（默认 5s）+ 等待图环路检测，youngest 事务牺牲策略
- `isolation`: 四种隔离级别定义与校验（READ UNCOMMITTED / READ COMMITTED / REPEATABLE READ / SERIALIZABLE）
- `transaction-manager`: 多事务并发管理，begin/commit/rollback + 快照获取
- `buffer-pool-latch`: BufferPool page latch 集成，MVCC 可见版本读取

### Modified Capabilities

（无 v0.1 已有 capability 被修改，均为新增）

## Impact

- 新增模块 `tinydb/concurrency/`（lock_manager.py、mvcc_manager.py、deadlock_detector.py、isolation.py）
- 改造 `tinydb/transaction/txn_manager.py`（支持多事务）
- 改造 `tinydb/transaction/shadow_paging.py`（适配 MVCC 版本链）
- 改造 `tinydb/buffer_pool.py`（添加 page latch + MVCC 版本路由）
- 无新外部依赖（threading 标准库）
- 与 v0.1 兼容：单事务时行为等价（默认 REPEATABLE READ）
