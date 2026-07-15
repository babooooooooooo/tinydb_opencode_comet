# file-format Specification

## Purpose
TBD - created by archiving change tinydb-storage. Update Purpose after archive.
## Requirements
### Requirement: 文件格式标识
The system SHALL use a magic bytes "TINYDB\0" at the start of the database file for format identification.

#### Scenario: 打开有效的 .db 文件
- **WHEN** 文件以 "TINYDB\0" 开头
- **THEN** 系统识别为有效的 tinydb 数据库文件

#### Scenario: 打开无效文件
- **WHEN** 文件不以 "TINYDB\0" 开头
- **THEN** 系统拒绝并返回格式错误

### Requirement: 文件头元数据
The system SHALL store page_size, page_count, free_list_head, and version in the file header (Page 0).

#### Scenario: 创建新数据库
- **WHEN** 首次创建 .db 文件
- **THEN** 系统写入正确的文件头元数据，page_count 初始为 1

#### Scenario: 读取元数据
- **WHEN** 打开已有数据库
- **THEN** 系统从 Page 0 读取 page_size、page_count 等元数据

### Requirement: 数据库打开与关闭
The system SHALL provide open(path) and close() methods for database lifecycle management.

#### Scenario: 打开不存在文件
- **WHEN** open() 调用时文件不存在
- **THEN** 系统创建新的空数据库文件

#### Scenario: 关闭时刷盘
- **WHEN** close() 调用
- **THEN** 系统将所有脏页刷盘后再关闭文件句柄

### Requirement: 完整性检查
The system SHALL verify file integrity on open using checksum.

#### Scenario: 文件损坏检测
- **WHEN** 文件 checksum 不匹配
- **THEN** 系统报告文件损坏错误

