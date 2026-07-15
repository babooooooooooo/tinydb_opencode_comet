# type-system Specification

## Purpose
TBD - created by archiving change tinydb-storage. Update Purpose after archive.
## Requirements
### Requirement: 类型系统支持四种基本数据类型
The system SHALL support INTEGER, FLOAT, TEXT, and BOOLEAN data types with proper type checking.

#### Scenario: 创建整数列
- **WHEN** 定义列类型为 INTEGER
- **THEN** 系统接受 int 值，拒绝非 int 值并返回 TypeError

#### Scenario: 创建文本列
- **WHEN** 定义列类型为 TEXT
- **THEN** 系统接受 str 值，拒绝非 str 值并返回 TypeError

### Requirement: 类型检查在运行时执行
The system SHALL validate values against column types at write time (INSERT/UPDATE).

#### Scenario: 插入整数到浮点列
- **WHEN** 向 FLOAT 列插入 INTEGER 值
- **THEN** 系统隐式转换为 FLOAT 类型成功

#### Scenario: 插入字符串到整数列
- **WHEN** 向 INTEGER 列插入 TEXT 值
- **THEN** 系统拒绝并返回类型不匹配错误

### Requirement: NULL 值表示
The system SHALL support NULL values through a NULL sentinel in the type system.

#### Scenario: 查询含 NULL 的行
- **WHEN** 某行某列值为 NULL
- **THEN** 系统正确返回 NULL 而非空字符串或 0

### Requirement: ColumnDef 定义
The system SHALL provide a ColumnDef structure containing name, type, nullable, and constraints.

#### Scenario: 定义 NOT NULL 列
- **WHEN** 创建 ColumnDef 时设置 nullable=False
- **THEN** 系统拒绝向该列插入 NULL 值

