## Context

SQL 引擎是 tinydb 的核心中间层，接收 SQL 字符串，解析为 AST，生成执行计划，通过存储引擎读写数据。本模块依赖 `tinydb-storage` 的缓冲池、页管理、行格式 API。

教学优先原则：每个处理阶段（词法→语法→计划→执行）独立模块化，有清晰的数据结构流转。

## Goals / Non-Goals

**Goals:**
- PostgreSQL 风格 SQL 语法支持（DDL + DML + 条件表达式）
- 清晰的词法→语法→计划→执行流水线
- 火山模型执行引擎（迭代器模式）
- WHERE 条件求值支持 AND/OR/NOT
- ORDER BY + LIMIT + OFFSET 支持
- 聚合函数 COUNT/SUM/AVG + GROUP BY
- 列约束在 DML 时强制执行

**Non-Goals:**
- 子查询、JOIN、窗口函数
- 查询优化器（无基于代价的优化）
- 预编译/参数化查询
- 多表操作

## Decisions

### D1: 词L分析器采用手写递归下降

| 方案 | 优点 | 缺点 |
|------|------|------|
| 手写递归下降 | 清晰可控、错误信息好、教学友好 | 代码量稍大 |
| PLY/ANTLR | 自动生成 | 额外依赖、不透明 |

选择手写：零依赖、教学清晰、错误定位精确。

### D2: 语法分析器采用递归下降

每个 SQL 语句类型对应一个解析方法：
```
parse_select() → parse_where() → parse_order_by() → parse_limit()
```

### D3: 执行引擎采用火山模型（Iterator Model）

```
┌─────────────┐
│   Limit     │
├─────────────┤
│   Sort      │
├─────────────┤
│  Aggregate  │
├─────────────┤
│   Project   │
├─────────────┤
│   Filter    │
├─────────────┤
│   Scan      │  ← 全表扫描，从存储引擎逐行读取
└─────────────┘
```

每个算子实现 `__iter__()` 和 `__next__()`，向上游拉取数据。教学上这是最经典的执行模型。

### D4: WHERE 条件采用表达式树求值

```
        AND
       /   \
     >       =
    / \     / \
   age 25  name 'Alice'
```

每个节点是一个表达式对象，对一行数据求值返回 bool。

### D5: GROUP BY 采用内存哈希聚合

遍历时以 GROUP BY 列为 key 构建哈希表，聚合函数累加。简单但不支持超大数据集（教学足够）。

### D6: 约束检查嵌入 DML 执行路径

- PRIMARY KEY / UNIQUE：INSERT/UPDATE 时检查列值是否已存在
- NOT NULL：INSERT 时检查值是否为 NULL
- 检查失败回滚当前操作

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| SQL 语法覆盖率不全 | 先支持提案中的最小语法集，后续可扩展 |
| 全表扫描无索引优化 | 第二个 change 引入 B-tree 索引后增强 Scan 算子 |
| 哈希聚合内存爆炸 | 教学场景数据集小，暂不考虑 |

