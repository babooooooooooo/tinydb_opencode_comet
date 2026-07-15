# Brainstorm Summary

- Change: tinydb-storage
- Date: 2026-07-15

## 确认的技术方案

### 行存储模型: Slotted Page
- 每页有 slot array 指向行数据偏移量
- 行 ID (RowId) = (page_id, slot_index)
- 支持稳定行引用、高效删除（slot 标记空闲）和空间复用
- 经典数据库教学模型，类似 SQLite/PostgreSQL

### 系统目录: 自描述 Catalog 表
- 特殊的系统表 tinydb_master 存储所有表元数据
- 每行对应一个表：表名、列定义（JSON）、根页号、约束信息
- 启动时从磁盘加载到内存字典（Catalog 对象）
- 修改 catalog 时同步写盘（通过 Shadow Paging）

### 表-页映射: 页链表
- 每表有根页，根页及每页头部存 next_page_id
- 表的页链表 = root_page → page_a → page_b → ... → NULL
- 全表扫描 = 遍历页链表，每页读所有有效 slot
- INSERT 时遍历页链表找有空闲空间的页；都不够时追加新页到链尾
- 删除行时 slot 标记空闲供复用

### API 风格: Table 对象 + 迭代器
- 存储引擎暴露 Database.create_table() → Table 对象
- Table 对象提供: insert(row)、scan() 迭代器、get(rowid)、delete(rowid)、update(rowid, row)
- 高封装、Pythonic、教学接口清晰
- SQL 层通过 Table API 间接操纵存储

### 缓冲池实现: OrderedDict + 双向链表混合
- cache 层用 OrderedDict（简洁的 get/put/淘汰语义）
- LRU 顺序用显式双向链表跟踪（展示经典 LRU 算法）
- 兼顾代码简洁和算法教学（两种视角都保留）

## 关键取舍与风险

| 风险 | 缓解 |
|------|------|
| 删除行后空间碎片 | 低优先级：教学项目，DELETE 后空间不复用（简化实现） |
| LRU 顺序扫描污染 | pin 机制保护当前扫描页，其他页正常淘汰 |
| JSON 列定义性能 | 教学场景足够，catalog 常驻内存不影响热点路径 |
| 单 Writer | 本项目不支持并发，文档说明 |

## 测试策略

- 单元测试：类型检查、行序列化、Page slot、LRU 顺序、空闲链表
- 集成测试：端到端 CRUD + 关闭重开一致性

## Spec Patch

无需回写 delta spec — 现有 spec 已足够，Design Doc 不引入新需求。
