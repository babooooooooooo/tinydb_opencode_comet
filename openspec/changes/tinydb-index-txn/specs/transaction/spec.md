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
