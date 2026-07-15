## 1. B-tree 索引

- [ ] 1.1 定义 BTreeNode 结构（内部节点、叶节点、序列化/反序列化到页）
- [ ] 1.2 实现 BTreeIndex 类：空树创建
- [ ] 1.3 实现 insert(key, value) 方法
- [ ] 1.4 实现叶节点分裂逻辑
- [ ] 1.5 实现内部节点分裂逻辑
- [ ] 1.6 实现 search(key) 等值查找
- [ ] 1.7 实现 range_scan(start, end) 范围查询
- [ ] 1.8 实现 delete(key) 方法
- [ ] 1.9 编写 btree 单元测试（含持久化测试）

## 2. 索引管理器

- [ ] 2.1 实现 IndexManager 类：注册表的所有索引
- [ ] 2.2 实现 create_index(table, column, name) 接口
- [ ] 2.3 实现 drop_index(name) 接口
- [ ] 2.4 实现 get_index(table, column) 查询
- [ ] 2.5 实现 DML 时自动更新索引
- [ ] 2.6 编写 index-manager 单元测试

## 3. Shadow Paging 事务

- [ ] 3.1 实现 Transaction 类：事务状态管理
- [ ] 3.2 实现 copy_on_write(page_id) 影子页创建
- [ ] 3.3 实现 begin() 方法（创建 master 快照）
- [ ] 3.4 实现 commit() 方法（原子切换根指针）
- [ ] 3.5 实现 rollback() 方法（丢弃影子页）
- [ ] 3.6 编写 shadow-paging 单元测试

## 4. 事务管理器

- [ ] 4.1 实现 TransactionManager 类：事务生命周期管理
- [ ] 4.2 实现 BEGIN/COMMIT/ROLLBACK SQL 语句处理
- [ ] 4.3 实现错误自动回滚
- [ ] 4.4 集成到 SQL 执行路径
- [ ] 4.5 编写 transaction 单元测试

## 5. CLI REPL

- [ ] 5.1 实现 REPL 循环（读取-执行-打印）
- [ ] 5.2 实现多行 SQL 输入（分号终止）
- [ ] 5.3 实现结果表格展示（对齐列、表头）
- [ ] 5.4 实现元命令（.exit, .tables, .schema, .help）
- [ ] 5.5 实现 readline 历史记录
- [ ] 5.6 编写 REPL 集成测试

## 6. Database 入口

- [ ] 6.1 实现 Database 类（持有存储引擎、SQL 引擎、事务管理器）
- [ ] 6.2 实现 execute(sql) 方法
- [ ] 6.3 实现 commit() / rollback() 方法
- [ ] 6.4 实现 close() 方法
- [ ] 6.5 实现上下文管理器 (__enter__ / __exit__)
- [ ] 6.6 编写 Database 单元测试

## 7. 索引增强执行器

- [ ] 7.1 实现 IndexScanOperator（替换全表扫描当索引可用时）
- [ ] 7.2 在 Planner 中增加索引选择逻辑
- [ ] 7.3 编写索引加速查询测试

## 8. Integration

- [ ] 8.1 三层完整集成端到端测试
- [ ] 8.2 事务回滚后索引一致性测试
- [ ] 8.3 编写 README 与使用文档
- [ ] 8.4 性能基准测试（对比全表扫描 vs 索引扫描）
