# Brainstorm Summary

- Change: tinydb-sql
- Date: 2026-07-15

## 确认的技术方案

### 整体架构
SQL 字符串 → Lexer (token 流) → Parser (AST) → Planner (算子树) → Executor (迭代执行) → QueryResult

### 模块划分
- `tinydb/sql/lexer.py`: 词法分析器，输出 Token 列表
- `tinydb/sql/parser.py`: 语法分析器，递归下降，输出 AST 节点
- `tinydb/sql/expressions.py`: 表达式树定义与求值
- `tinydb/sql/planner.py`: AST → 物理执行计划（算子树）
- `tinydb/sql/executor.py`: 火山模型算子实现（Scan/Filter/Project/Aggregate/Sort/Limit）
- `tinydb/sql/result.py`: QueryResult 返回对象
- `tinydb/sql/errors.py`: SQL 异常体系
- `tinydb/sql/database.py`: Database.execute() 入口

### 关键设计决策
1. **Lexer**: 手写逐字符扫描，支持关键字/字面量/运算符/标识符
2. **Parser**: 递归下降，每个 SQL 语句一个方法；表达式优先级: OR > AND > NOT > comparison > additive > multiplicative > unary > primary
3. **Expressions**: 表达式树节点（ColumnRef, Literal, BinaryOp, UnaryOp），`evaluate(row)` 方法对行数据求值
4. **Planner**: 简单 AST→算子树映射，默认全表扫描
5. **Executor**: 火山模型，每个算子实现 `__iter__()`/`__next__()`
6. **GROUP BY**: 内存哈希聚合，group key → 聚合状态累加
7. **排序**: Sort 算子物化所有行后用 Python `sorted()` 排序
8. **约束**: NOT NULL 预检查；PRIMARY KEY/UNIQUE 通过 Table 扫描检查
9. **错误**: 带位置信息的异常，fail-fast 策略
10. **返回值**: QueryResult(rows: list[dict], columns: list[str], row_count: int)

## 关键取舍与风险

| 取舍/风险 | 说明 |
|----------|------|
| 全表扫描 | 无索引优化，后续 change 引入 B-tree 后增强 |
| 哈希聚合内存 | 教学场景数据集小，不处理超大数据集 |
| 无错误恢复 | fail-fast，只报第一个错误，不尝试继续解析 |
| 无子查询/JOIN | 不在本 change 范围内 |
| 类型检查复用 types.py | Table.insert 已调用 convert_value，SQL 层不再重复校验类型 |
| UNIQUE 线性扫描 | 无索引时全表扫描检查唯一性，性能 O(n) 但正确 |

## 测试策略

- **单元测试**: 每个模块独立测试（lexer/parser/planner/executor/expressions 各自一个 test 文件）
- **集成测试**: 端到端 SQL 语句测试（创建表→插入→查询→更新→删除）
- **测试框架**: pytest + tmp_path fixture
- **覆盖重点**: 边界条件（空表、NULL 值、类型优先级、表达式组合、约束违反）

## Spec Patch

无回写 delta spec。OpenSpec delta spec 已包含足够验收场景。
