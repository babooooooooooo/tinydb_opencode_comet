## Context

顶层模块整合存储引擎和 SQL 引擎，引入索引加速和事务保证，并通过 CLI 提供交互界面。本模块依赖前两层的所有 API，是面向用户的最终产品层。

教学优先原则：Shadow Paging 的事务机制实现清晰可见；B-tree 操作有可视化调试接口。

## Goals / Non-Goals

**Goals:**
- B-tree 索引：等值查询 O(log n)、范围查询有序遍历
- Shadow Paging 事务：页级写时复制，天然支持 ROLLBACK
- ACID 原子性和持久性
- CLI REPL：交互式 SQL 输入执行和结果展示
- Database 类统一 API：`Database(path)` → `execute(sql)` → `fetchall()`

**Non-Goals:**
- 多隔离级别（仅语句级一致性）
- 并发事务（单 Writer）
- WAL 事务模式（未来可选）
- 分布式事务

## Decisions

### D1: B-tree 节点大小与页大小一致

B-tree 节点直接映射到存储页（4KB），便于缓冲池管理。

```
┌─────────────────────────────────────────┐
│  B-tree Internal Node                   │
│  ├─ page_header                         │
│  ├─ keys: [k1, k2, ..., kn]             │
│  └─ children: [p0, p1, ..., pn]         │
├─────────────────────────────────────────┤
│  B-tree Leaf Node                       │
│  ├─ page_header                         │
│  ├─ keys: [k1, k2, ..., kn]             │
│  └─ values: [v1, v2, ..., vn]           │
│     (v 为行指针: (page_id, slot))       │
└─────────────────────────────────────────┘
```

### D2: B-tree 叶节点存行指针（非聚簇）

叶节点存储 `(key, row_pointer)` 对，row_pointer 指向实际数据页中的行。适合教学演示，避免数据物理重组。

### D3: Shadow Paging 实现

```
┌─────────────────────────────────────────┐
│  Shadow Paging 原理                     │
│                                         │
│  BEGIN → 创建 master page 快照          │
│                                         │
│  Write:                                 │
│  ┌──────┐    ┌──────┐                  │
│  │ Page │ →  │ Page │ (copy-on-write)  │
│  │  A   │    │  A'  │                  │
│  └──────┘    └──────┘                  │
│                                         │
│  COMMIT → master 指向新根              │
│  ROLLBACK → 丢弃影子页，恢复 master     │
└─────────────────────────────────────────┘
```

写时复制：修改页时先复制到影子页，修改影子页，COMMACT 时原子切换根指针。

### D4: B-tree 阶数由页大小决定

阶数 = `(page_size - header_size) / (key_size + pointer_size)`，无需手动配置。

### D5: CLI REPL 使用 Python readline

基础 REPL，支持多行 SQL（以分号结束）、历史记录（上下方向键）、退出命令（`.exit`）。不引入额外依赖。

### D6: 事务状态管理

```
Transaction:
  - txn_id: 唯一标识
  - state: active | committed | aborted
  - shadow_pages: 事务内修改的影子页集合
  - master_snapshot: 事务开始时的根页快照
```

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| Shadow Paging 写放大 | 教学定位，性能非首要目标 |
| B-tree 节点分裂实现复杂 | 先实现基础分裂，暂不处理合并 |
| 单 Writer 限制并发 | 明确不支持并发，文档说明 |
