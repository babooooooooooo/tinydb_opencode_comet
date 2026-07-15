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
