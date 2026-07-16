# Tasks: tinydb-v02-cli

## 任务清单

### Phase 1: P0 功能（核心 CLI 增强）

- [x] T1.1 创建 `tinydb/cli/highlighter.py`，实现 SQLHighlighter 类
  - 基于 pygments 的 SQL 语法高亮
  - 无 pygments 时静默降级（返回原字符串）
  - 配色：keywords(蓝)、strings(绿)、numbers(黄)、comments(灰）

- [x] T1.2 创建 `tinydb/cli/completer.py`，实现 SQLCompleter 类
  - SQL 关键字常量列表
  - 上下文感知补全（FROM 后表名，SELECT 后列名）
  - refresh_schema() 方法从 db 加载元数据

- [x] T1.3 创建 `tinydb/cli/commands.py`，实现 CommandHandler 类
  - .explain 命令：调用 Planner.plan() 格式化输出执行计划树
  - .timing 命令：开关查询计时

- [x] T1.4 重构 `tinydb/cli/repl.py`
  - 集成 SQLHighlighter 实现语法高亮
  - 集成 SQLCompleter 实现 TAB 自动补全
  - 集成 CommandHandler 实现点命令分发
  - 多行语句判断：括号配对 + 分号结尾
  - 续行提示符 `.. `
  - 保留现有 .exit/.quit/.tables/.schema/.help 命令
  - .timing 开启时显示 SQL 执行耗时

### Phase 2: P1 功能（数据导入导出 + 增强）

- [x] T2.1 实现 .import 命令
  - 支持 CSV 格式（首行为列名）
  - 支持 JSON 格式（对象数组）
  - 批量插入（事务包裹）
  - 返回导入行数统计

- [x] T2.2 实现 .dump 命令
  - 导出全表数据
  - 默认输出到 stdout，可选写文件
  - 支持 CSV 和 JSON 格式

### Phase 3: 依赖与配置

- [x] T3.1 更新 `pyproject.toml` 添加 `pygments>=2.10` 依赖

### Phase 4: 测试

- [x] T4.1 编写 test_highlighter.py
  - 测试高亮输出包含 ANSI 转义码
  - 测试无 pygments 降级

- [x] T4.2 编写 test_completer.py
  - 测试关键字补全
  - 测试表名/列名补全
  - 测试上下文感知

- [x] T4.3 编写 test_commands.py
  - 测试 .explain 输出格式
  - 测试 .timing 开关
  - 测试 .import CSV/JSON
  - 测试 .dump CSV/JSON

- [x] T4.4 扩展 test_repl.py
  - 测试多行语句判断（括号配对）
  - 测试续行提示符
  - 测试命令集成

### Phase 5: 验证

- [x] T5.1 运行全量测试确保 v0.1 测试不退化
- [x] T5.2 手动验证 CLI 交互体验（高亮、补全、命令）

## 依赖关系

```
T1.1 ─┐
T1.2 ─┼─→ T1.4 ─→ T4.4
T1.3 ─┘      │
             ▼
T2.1 ─→ T2.2 ─→ T4.3 ─→ T5.1 ─→ T5.2
             ▲
T3.1 ────────┘
```
