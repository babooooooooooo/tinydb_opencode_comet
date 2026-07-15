# row-format Specification

## Purpose
TBD - created by archiving change tinydb-storage. Update Purpose after archive.
## Requirements
### Requirement: 行序列化
The system SHALL serialize a row (list of values) into bytes using length-prefixed encoding for variable-length types.

#### Scenario: 序列化含 NULL 的行
- **WHEN** 行中某些列为 NULL
- **THEN** 系统使用 NULL 位图标记，不写入实际值

#### Scenario: 序列化全类型行
- **WHEN** 行包含 INT、FLOAT、TEXT、BOOL 各一列
- **THEN** 系统正确序列化每个类型到字节流

### Requirement: 行反序列化
The system SHALL deserialize bytes back into a row (list of values) given a column definition.

#### Scenario: 反序列化有效数据
- **WHEN** 给定的字节流是某行序列化的结果
- **THEN** 系统还原出原始值列表（含正确的 NULL）

#### Scenario: 反序列化空行
- **WHEN** 字节流为空
- **THEN** 系统返回空列表

### Requirement: 变长字段编码
The system SHALL encode variable-length TEXT using a 4-byte length prefix followed by UTF-8 bytes.

#### Scenario: 编码中文文本
- **WHEN** 列值为 UTF-8 中文字符串
- **THEN** 系统正确编码长度并写入字节

### Requirement: NULL 位图
The system SHALL use a bitmap (1 bit per column) to indicate NULL values in the row header.

#### Scenario: 8 列中位图为 1 字节
- **WHEN** 行定义为 8 列
- **THEN** NULL 位图占用 1 字节

#### Scenario: 12 列位图为 2 字节
- **WHEN** 行定义为 12 列
- **THEN** NULL 位图占用 2 字节

