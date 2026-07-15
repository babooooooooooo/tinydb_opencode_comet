# page-storage Specification

## Purpose
TBD - created by archiving change tinydb-storage. Update Purpose after archive.
## Requirements
### Requirement: 页大小固定 4KB
The system SHALL use a fixed page size of 4096 bytes.

#### Scenario: 创建新页
- **WHEN** 分配一个新页
- **THEN** 该页恰好占用 4096 字节空间

### Requirement: 页分配与回收
The system SHALL maintain a free list to track available pages and support allocation/deallocation.

#### Scenario: 分配新页
- **WHEN** 空闲链表非空时请求新页
- **THEN** 系统从空闲链表头部取出一页并返回其页号

#### Scenario: 无空闲页时分配
- **WHEN** 空闲链表为空时请求新页
- **THEN** 系统追加新页到文件末尾并返回新页号

#### Scenario: 回收页
- **WHEN** 删除数据导致某页空闲
- **THEN** 系统将该页加入空闲链表头部

### Requirement: Page 基本结构
The system SHALL provide a Page class with page_id, data buffer, and dirty flag.

#### Scenario: 读取页
- **WHEN** 请求读取页号为 N 的页
- **THEN** 系统返回包含该页数据的 Page 对象

#### Scenario: 写入页
- **WHEN** 修改页数据后标记为 dirty
- **THEN** 系统维护 dirty 标志用于后续刷盘

### Requirement: 页读写接口
The system SHALL provide read_page(page_id) and write_page(page_id, data) operations.

#### Scenario: 读取不存在的页
- **WHEN** 请求读取超出文件范围的页号
- **THEN** 系统返回错误

