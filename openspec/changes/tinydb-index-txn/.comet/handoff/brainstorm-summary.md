# Brainstorm Summary

- Change: tinydb-index-txn
- Date: 2026-07-15

## 确认的技术方案

### B-tree 索引
- 节点大小 = 页大小 (4096 bytes)，1 节点 = 1 页（D1）
- 叶节点存储 (key, row_pointer) 对，非聚簇索引（D2）
- 阶数由页大小动态计算：`order = (PAGE_SIZE - HEADER_SIZE) / (key_size + pointer_size)`（D4）
- 分裂策略：中位键提升（even split），自底向上递归
- 删除：lazy deletion（标记删除，不合并/重分布）——教学优先简化

### 索引管理器
- IndexManager 维护 `{table_name: {column_name: BTreeIndex}`} 映射
- CREATE INDEX 时从表扫描现有数据构建索引
- DML 时自动更新：
  - INSERT → 对新行调用 `index.insert(key, row_ptr)`
  - DELETE → 对旧行调用 `index.delete(key, row_ptr)`
  - UPDATE → 若索引列值变化，先 delete 旧值再 insert 新值

### 索引感知扫描
- 执行器新增 IndexScanOperator：当 WHERE 子句包含索引列的等值/范围条件时使用
- 简单启发式：优先使用第一个匹配的索引列
- 无匹配索引时回退到全表扫描

### Shadow Paging 事务
- CoW：事务中修改页时，分配新页（影子页），在新页上修改
- 影子页追踪：`Transaction.shadow_pages: set[int]` 记录所有影子页 ID
- COMMIT：原子切换根指针（catalog_root 在文件头），影子页成为正式页
- ROLLBACK：释放影子页（加入 free list），原页不受影响
- 文件头新增 `root_page_id` 字段存储 B-tree 根节点指针

### 事务管理器
- 单 Writer：同一时间只允许一个活跃事务
- 事务状态：active | committed | aborted
- 语句级一致性：事务内读能见到自己的写
- 错误自动回滚：SQL 执行异常时自动 discard 影子页

### Database 类
- `Database(path)` 构造函数
- `execute(sql)` 方法，返回 `QueryResult`（列名 + 行列表）
- 上下文管理器：`with Database(path) as db:`
- `close()` 刷盘 + 关闭文件

### CLI REPL
- Python readline，无额外依赖（D5）
- 多行 SQL（分号终止）
- 元命令：`.exit`, `.tables`, `.schema`, `.help`
- 结果表格展示

## 关键取舍与风险

| 取舍/风险 | 决策 |
|-----------|------|
| Shadow Paging 写放大 | 教学定位，性能非首要目标 |
| B-tree 不实现合并 | Lazy deletion，节点可能稀疏但结构正确 |
| 单 Writer 限制 | 明确不支持并发，文档说明 |
| 索引仅单列 | 复合索引留未来 |
| 简单索引选择启发式 | 无统计信息，不实现代价模型 |

## 测试策略

- B-tree：插入/分裂/查找/范围扫描/删除 + 持久化测试
- 索引管理器：创建/删除索引 + DML 自动更新验证
- Shadow Paging：CoW 验证 + COMMIT/ROLLBACK 原子性
- 事务：BEGIN/COMMIT/ROLLBACK + 错误自动回滚
- 集成：端到端 CRUD + 索引加速查询 + 事务一致性

## Spec Patch

无需回写 delta spec。OpenSpec 的 proposal/design/tasks 已充分覆盖所有需求。
