# Proposal: tinydb-v02-cli

## 摘要

为 tinydb 交互式 CLI 增加语法高亮、自动补全、执行计划展示（.explain）、数据导入导出（.import/.dump）、查询计时（.timing）等功能，将 tinydb 从基础 REPL 升级为开发体验友好的数据库命令行工具。

## 动机

v0.1 的 CLI 仅提供最基础的 SQL 执行循环，缺乏现代数据库 CLI（如 sqlite3、mysql）的标准功能：

- 无语法高亮，长 SQL 难以阅读
- 无自动补全，用户需记忆所有表名和关键字
- 无执行计划展示，无法理解查询性能
- 无数据导入导出，无法与外部工具协作
- 无查询计时，无法评估性能

这些功能对开发者体验至关重要，且与 JOIN、并发控制两个 change 完全独立，可并行开发、优先合并。

## 范围

### 范围内

| 功能 | 描述 | 优先级 |
|------|------|--------|
| 语法高亮 | SQL 关键字、字符串、数字、注释着色 | P0 |
| 行编辑 | Emacs 快捷键、Ctrl-A/E/W/K/U | P0 |
| 自动补全 | 关键字、表名、列名 TAB 补全 | P0 |
| .explain | 展示 SQL 执行计划树 | P0 |
| .import | 从 CSV/JSON 导入数据 | P1 |
| .dump | 导出表数据为 CSV/JSON | P1 |
| .timing | 开关查询计时显示 | P1 |
| 多行增强 | 括号匹配、续行提示 | P1 |

### 范围外

- 图形界面或 Web 界面
- 网络协议 / 远程连接
- 多数据库同时连接
- 脚本执行模式（.read 命令）

## 变更文件

```
tinydb/cli/
├── repl.py           # 重构：集成高亮、补全、新命令
├── highlighter.py    # 新增：SQL 语法高亮（基于 pygments）
├── completer.py      # 新增：上下文感知自动补全
└── commands.py       # 新增：.explain/.import/.dump/.timing 命令实现
```

## 新依赖

- `pygments>=2.10` — SQL 语法高亮

## 验证标准

- 高亮不崩溃，无 pygments 时静默降级
- 补全命中率 > 90%
- .explain 输出可读的执行计划树
- .import/.dump 支持 CSV 和 JSON 格式
- .timing 正确显示毫秒级耗时
- 所有现有测试继续通过
