## 1. LockManager

- [x] 1.1 定义 LockMode 枚举（SHARED, EXCLUSIVE）和兼容性矩阵
- [x] 1.2 实现 LockManager 类：acquire / release / release_all / upgrade 方法
- [x] 1.3 实现 FIFO 等待队列 + 超时机制（默认 5s）
- [x] 1.4 实现 S→X 锁升级（同一事务先 S 后 X 场景）
- [x] 1.5 编写 LockManager 单元测试（兼容性矩阵、超时、升级）

## 2. MVCCManager

- [x] 2.1 定义 PageVersion 数据结构（data, created_txn, deleted_txn, next 指针）
- [x] 2.2 实现 MVCCManager 类：read_version / create_version / get_visible_version 方法
- [x] 2.3 实现快照结构（Snapshot：活跃事务列表 + 快照时间戳）
- [x] 2.4 实现可见性判断逻辑（created_txn in snapshot AND deleted_txn NOT IN snapshot）
- [x] 2.5 实现版本 GC：清理无活跃事务引用的旧版本
- [x] 2.6 编写 MVCCManager 单元测试（版本链、可见性、GC）

## 3. DeadlockDetector

- [x] 3.1 实现等待图数据结构（txn_id → waits_for set）
- [x] 3.2 实现环路检测算法（DFS 或拓扑排序）
- [x] 3.3 实现牺牲者选择策略（youngest transaction）
- [x] 3.4 集成超时检测（5s 超时触发检测）
- [x] 3.5 编写 DeadlockDetector 单元测试（环路检测、牺牲者选择）

## 4. Isolation

- [x] 4.1 定义 IsolationLevel 枚举（READ_UNCOMMITTED, READ_COMMITTED, REPEATABLE_READ, SERIALIZABLE）
- [x] 4.2 实现隔离级别校验接口（预留扩展点）
- [x] 4.3 默认 REPEATABLE READ 行为实现
- [x] 4.4 编写隔离级别单元测试

## 5. TransactionManager 重构

- [x] 5.1 将 `_active_txn: Transaction | None` 改为 `_active_txns: dict[txn_id, Transaction]`
- [x] 5.2 实现 begin() → txn_id（生成新事务 ID + 获取快照）
- [x] 5.3 实现 commit(txn_id)（释放所有锁 + 清理版本）
- [x] 5.4 实现 rollback(txn_id)（回滚修改 + 释放所有锁）
- [x] 5.5 实现 get_snapshot(txn_id) → Snapshot
- [x] 5.6 编写 TransactionManager 单元测试（多事务并发 begin/commit/rollback）

## 6. BufferPool 改造

- [x] 6.1 修改 pin(page_id, txn_id, mode)：内部调用 LockManager.acquire
- [x] 6.2 修改 unpin(page_id, txn_id)：内部调用 LockManager.release
- [x] 6.3 修改 get_page(page_id, txn_id)：返回 MVCC 可见版本而非最新页
- [x] 6.4 编写 BufferPool 集成测试（pin/unpin 锁交互、MVCC 版本路由）

## 7. Shadow Paging 适配

- [x] 7.1 修改 shadow_paging 提交逻辑：与 MVCC 版本链协调
- [x] 7.2 确保页级原子性在 MVCC 上层仍然有效
- [x] 7.3 编写 shadow paging + MVCC 集成测试

## 8. 并发测试

- [x] 8.1 编写多线程读写并发测试
- [x] 8.2 编写死锁场景测试（环路检测 + 牺牲者回滚）
- [x] 8.3 编写隔离级别行为测试（REPEATABLE READ 验证）
- [x] 8.4 编写 v0.1 回归测试（多事务模式下原有用例不退化）

## 9. Integration

- [x] 9.1 更新 Database 入口：多事务模式下自动启用并发控制
- [x] 9.2 编写端到端并发集成测试
- [x] 9.3 编写并发性能基准测试脚本
