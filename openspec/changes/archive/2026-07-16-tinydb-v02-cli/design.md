# Design: tinydb-v02-cli

## 1. 概述

本设计基于 v0.2 总体设计文档第 6 节（CLI 功能增强），为 tinydb 的交互式 REPL 增加现代数据库 CLI 的标准功能。

## 2. 架构

### 2.1 模块划分

```
tinydb/cli/
├── repl.py           # 主 REPL 循环，协调各组件
├── highlighter.py    # SQLHighlighter：语法高亮
├── completer.py      # SQLCompleter：自动补全
└── commands.py       # CommandHandler：点命令分发
```

### 2.2 组件交互

```
用户输入 → REPL.run()
           ├─ 点命令 → CommandHandler.handle()
           │            ├─ .explain → Planner.plan() → 格式化输出
           │            ├─ .import → CSV/JSON 解析 → 批量 INSERT
           │            ├─ .dump   → SELECT → CSV/JSON 序列化
           │            └─ .timing → 开关切换
           └─ SQL → SQLHighlighter.highlight() → 着色显示
                   → SQLCompleter.complete() → TAB 补全
                   → db.execute() → 结果输出
```

## 3. 详细设计

### 3.1 语法高亮（SQLHighlighter）

**文件**: `tinydb/cli/highlighter.py`

```python
class SQLHighlighter:
    """基于 pygments 的 SQL 语法高亮"""

    def __init__(self):
        self._lexer = None
        self._formatter = None
        self._enabled = self._init_pygments()

    def _init_pygments(self) -> bool:
        """初始化 pygments，失败时返回 False（静默降级）"""
        ...

    def highlight(self, sql: str) -> str:
        """返回 ANSI 着色字符串，无 pygments 时返回原字符串"""
        ...
```

**配色方案**:
- 关键字（SELECT, FROM, WHERE, JOIN 等）: 蓝色
- 字符串字面量: 绿色
- 数字: 黄色
- 注释: 灰色

**降级策略**: `pygments` 不可用时，`highlight()` 直接返回输入字符串，不抛出异常。

### 3.2 自动补全（SQLCompleter）

**文件**: `tinydb/cli/completer.py`

```python
class SQLCompleter:
    """上下文感知的 SQL 补全"""

    SQL_KEYWORDS = [
        "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE",
        "CREATE", "DROP", "TABLE", "INDEX", "JOIN", "ON", "AND",
        "OR", "NOT", "NULL", "ORDER", "GROUP", "BY", "LIMIT",
        "OFFSET", "AS", "INTO", "VALUES", "SET", "BEGIN", "COMMIT",
        "ROLLBACK",
    ]

    def __init__(self, db):
        self._db = db
        self._table_cache: dict[str, list[str]] = {}

    def complete(self, text: str, state: int) -> str | None:
        """readline 补全回调，返回第 state 个候选"""
        ...

    def _get_candidates(self, text: str, line: str) -> list[str]:
        """根据上下文生成候选列表"""
        ...

    def refresh_schema(self):
        """刷新表名/列名缓存"""
        ...
```

**上下文感知规则**:
- 行首或 `;` 后 → 补全 SQL 关键字
- `FROM`/`JOIN`/`INTO`/`UPDATE` 后 → 补全表名
- `SELECT` 后或 `.` 后 → 补全列名
- 其他 → 补全关键字 + 表名 + 列名

### 3.3 命令实现（CommandHandler）

**文件**: `tinydb/cli/commands.py`

```python
class CommandHandler:
    """处理点命令"""

    def __init__(self, db):
        self._db = db
        self._timing_enabled = False

    def handle(self, cmd: str, arg: str) -> str | None:
        """处理命令，返回输出字符串或 None"""
        ...

    def _explain(self, sql: str) -> str:
        """格式化执行计划树"""
        ...

    def _import(self, table: str, filepath: str) -> str:
        """从 CSV/JSON 导入数据"""
        ...

    def _dump(self, table: str, filepath: str | None) -> str:
        """导出表数据为 CSV/JSON"""
        ...

    def _timing(self, arg: str) -> str:
        """开关查询计时"""
        ...
```

#### .explain <SQL>

通过 `Planner.plan()` 获取 operator tree，递归格式化输出：

```
┌─ ExecutePlan ─────────────────────────────┐
│ Project [name, amount]                     │
│ └─ Filter WHERE id > 10                    │
│    └─ Scan(users)                          │
└────────────────────────────────────────────┘
```

#### .import <table> <filepath>

- 支持 `.csv` 和 `.json` 文件扩展名自动识别格式
- CSV: 首行为列名，后续行为数据
- JSON: 对象数组格式 `[{"col1": val1, "col2": val2}, ...]`
- 批量插入：整个导入包裹在一个事务中
- 返回导入行数

#### .dump <table> [filepath]

- 默认输出到 stdout
- 指定 filepath 时写入文件
- 格式同 .import（CSV/JSON）
- 导出全表数据

#### .timing on|off

- `on` — 开启后每条 SQL 后显示 `Time: X.XX ms`
- `off` — 关闭（默认）
- 使用 `time.perf_counter_ns()` 计时

### 3.4 REPL 重构

**文件**: `tinydb/cli/repl.py`

```python
class REPL:
    def __init__(self, db):
        self._db = db
        self._highlighter = SQLHighlighter()
        self._completer = SQLCompleter(db)
        self._commands = CommandHandler(db)
        self._buffer: list[str] = []
        self._timing_enabled = False

    def run(self):
        """主循环：输入 → 解析 → 执行 → 显示"""
        self._setup_readline()
        while True:
            try:
                line = input(self._get_prompt())
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break

            if line.strip().startswith("."):
                self._handle_command(line.strip())
                continue

            self._buffer.append(line)
            if self._is_complete():
                self._execute_buffer()

    def _is_complete(self) -> bool:
        """括号配对 + 分号结尾判断语句完整性"""
        ...

    def _execute_buffer(self):
        """执行缓冲区中的 SQL"""
        ...
```

**多行判断逻辑**:
1. 合并缓冲区文本
2. 检查括号是否配对（`()`、`[]`、`{}`）
3. 检查是否以 `;` 结尾
4. 两者都满足则执行，否则继续等待输入

**续行提示符**: `.. `（缩进两空格）

**保留的现有命令**: `.exit`、`.quit`、`.tables`、`.schema`、`.help`

## 4. 接口契约

### 4.1 Database 接口（已有，不变）

```python
class Database:
    def execute(self, sql: str) -> QueryResult: ...
    def list_tables(self) -> list[str]: ...
    def get_schema(self, table: str) -> list[ColumnDef]: ...
```

### 4.2 新增 CLI 接口

```python
# cli/highlighter.py
class SQLHighlighter:
    def highlight(self, sql: str) -> str: ...

# cli/completer.py
class SQLCompleter:
    def complete(self, text: str, state: int) -> str | None: ...
    def refresh_schema(self): ...

# cli/commands.py
class CommandHandler:
    def handle(self, cmd: str, arg: str) -> str | None: ...
```

## 5. 依赖变更

`pyproject.toml` 新增：

```toml
dependencies = [
    "pygments>=2.10",
]
```

## 6. 测试策略

### 6.1 单元测试

| 测试目标 | 测试内容 |
|----------|----------|
| SQLHighlighter | 高亮输出包含 ANSI 转义码；无 pygments 时返回原字符串 |
| SQLCompleter | 关键字补全、表名补全、列名补全、上下文感知 |
| CommandHandler | .explain 输出格式、.import 解析、.dump 序列化、.timing 开关 |
| REPL 多行判断 | 括号配对、分号结尾、不完整语句继续等待 |

### 6.2 集成测试

- 端到端 REPL 会话模拟（使用 `io.StringIO` 模拟输入）
- 超长输入、Unicode、空输入边界

### 6.3 回归测试

- 现有 `test_repl.py` 全部通过
- 现有 `test_database.py` 全部通过

## 7. 实现顺序

1. **highlighter.py** — 独立，无外部状态依赖
2. **completer.py** — 依赖 Database 接口
3. **commands.py** — 依赖 Database + Planner
4. **repl.py 重构** — 集成以上三个组件
5. **pyproject.toml 更新** — 添加 pygments 依赖
