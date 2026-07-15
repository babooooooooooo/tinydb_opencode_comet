## 1. Lexer

- [x] 1.1 定义 Token 类型和 TokenType 枚举（关键字、字面量、运算符、分隔符、标识符）
- [x] 1.2 实现 Lexer 类：逐个字符扫描，生成 token 列表
- [x] 1.3 实现关键字识别（SELECT, FROM, WHERE 等）
- [x] 1.4 实现字面量识别（整数、浮点数、字符串、布尔值、NULL）
- [x] 1.5 实现运算符识别（=, !=, <>, <, >, <=, >=, +, -, *, /）
- [x] 1.6 实现标识符识别（字母/下划线开头）
- [x] 1.7 编写 lexer 单元测试

## 2. Parser

- [x] 2.1 定义 AST 节点类型（SelectStatement, InsertStatement, UpdateStatement 等）
- [x] 2.2 实现 Parser 类：递归下降解析
- [x] 2.3 实现 parse_select 方法（列、FROM、WHERE、ORDER BY、LIMIT、OFFSET）
- [x] 2.4 实现 parse_insert 方法
- [x] 2.5 实现 parse_update 方法
- [x] 2.6 实现 parse_delete 方法
- [x] 2.7 实现 parse_create_table 方法（含列约束）
- [x] 2.8 实现 parse_drop_table 方法
- [x] 2.9 实现 parse_where 表达式解析（AND/OR/NOT 优先级）
- [x] 2.10 实现 parse_expression（比较、算术）
- [x] 2.11 编写 parser 单元测试

## 3. Expressions

- [x] 3.1 定义 Expression 基类和子类（ColumnRef, Literal, BinaryOp, UnaryOp）
- [x] 3.2 实现表达式求值方法 evaluate(row)
- [x] 3.3 实现逻辑运算（AND, OR, NOT）
- [x] 3.4 实现比较运算（=, !=, <, >, <=, >=）
- [x] 3.5 实现算术运算（+, -, *, /）
- [x] 3.6 编写 expressions 单元测试

## 4. Planner

- [x] 4.1 定义 PlanNode 基类和子类
- [x] 4.2 实现 Planner 类：将 AST 转换为执行计划树
- [x] 4.3 实现 SELECT 计划生成（选择扫描策略）
- [x] 4.4 实现聚合查询计划生成
- [x] 4.5 编写 planner 单元测试

## 5. Executor

- [x] 5.1 定义 Operator 基类（next() 接口）
- [x] 5.2 实现 ScanOperator：全表扫描，从存储引擎逐行读取
- [x] 5.3 实现 FilterOperator：应用 WHERE 条件
- [x] 5.4 实现 ProjectOperator：选择列
- [x] 5.5 实现 AggregateOperator：COUNT/SUM/AVG + GROUP BY
- [x] 5.6 实现 SortOperator：内存排序
- [x] 5.7 实现 LimitOperator：LIMIT/OFFSET
- [x] 5.8 编写 executor 单元测试

## 6. DDL

- [x] 6.1 实现 CreateTableExecutor：调用存储引擎创建表
- [x] 6.2 实现 DropTableExecutor：调用存储引擎删除表
- [x] 6.3 编写 ddl 单元测试

## 7. DML

- [x] 7.1 实现 InsertExecutor：插入行
- [x] 7.2 实现 SelectExecutor：查询并返回结果
- [x] 7.3 实现 UpdateExecutor：更新行
- [x] 7.4 实现 DeleteExecutor：删除行
- [x] 7.5 编写 dml 单元测试

## 8. Constraints

- [x] 8.1 实现约束检查模块（调用存储引擎检查唯一性）
- [x] 8.2 在 DML 执行路径嵌入约束检查
- [x] 8.3 编写约束测试

## 9. Integration

- [x] 9.1 实现 Database.execute(sql) 入口方法
- [x] 9.2 编写端到端集成测试
- [x] 9.3 编写 SQL 基准测试脚本
