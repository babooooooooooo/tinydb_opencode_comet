# shadow-paging Specification

## Purpose
TBD - created by archiving change tinydb-index-txn. Update Purpose after archive.
## Requirements
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

