# btree-index Specification

## Purpose
TBD - created by archiving change tinydb-index-txn. Update Purpose after archive.
## Requirements
### Requirement: B-tree 插入键值对
The system SHALL support inserting a (key, value) pair into a B-tree index.

#### Scenario: 空树插入
- **WHEN** 向空 B-tree 插入 (25, row_ptr)
- **THEN** B-tree 根节点包含一个叶节点，存储该键值对

#### Scenario: 触发节点分裂
- **WHEN** 插入导致叶节点超过阶数限制
- **THEN** 叶节点分裂为两个，中位键提升至父节点

### Requirement: B-tree 等值查找
The system SHALL support searching for a specific key and returning the associated value(s).

#### Scenario: 查找存在的键
- **WHEN** B-tree 中存在键 42
- **THEN** 返回 42 对应的 row pointer

#### Scenario: 查找不存在的键
- **WHEN** B-tree 中不存在键 99
- **THEN** 返回空结果

### Requirement: B-tree 范围扫描
The system SHALL support range queries (e.g., `key >= 10 AND key <= 50`) returning all matching key-value pairs in sorted order.

#### Scenario: 范围查询
- **WHEN** 查询范围 [20, 40]
- **THEN** 按 key 升序返回所有匹配的键值对

#### Scenario: 左开区间
- **WHEN** 查询 `key > 10`
- **THEN** 返回所有 key > 10 的键值对，升序

### Requirement: B-tree 删除键
The system SHALL support deleting a key from the B-tree.

#### Scenario: 删除存在的键
- **WHEN** 删除存在的键
- **THEN** 键被移除，B-tree 保持有效结构

### Requirement: B-tree 节点映射到存储页
The system SHALL serialize/deserialize B-tree nodes to/from storage pages.

#### Scenario: 持久化
- **WHEN** 包含 B-tree 的数据库关闭后重新打开
- **THEN** B-tree 结构完整恢复

