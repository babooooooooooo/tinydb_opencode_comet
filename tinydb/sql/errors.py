"""SQL engine error hierarchy."""


class SQLError(Exception):
    """SQL 引擎所有异常的基类."""

    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.line = line
        self.column = column
        if line > 0:
            super().__init__(f"[{line}:{column}] {message}")
        else:
            super().__init__(message)


class LexerError(SQLError):
    """词法分析错误."""
    pass


class ParserError(SQLError):
    """语法分析错误."""
    pass


class PlanningError(SQLError):
    """查询计划错误."""
    pass


class ExecutionError(SQLError):
    """执行时错误."""
    pass


class ConstraintError(SQLError):
    """约束违反错误."""
    pass
