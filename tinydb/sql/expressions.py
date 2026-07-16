"""Expression tree definitions and evaluation."""
from dataclasses import dataclass

from tinydb.sql.errors import ExecutionError


class Expression:
    """Base class for all expressions."""

    def evaluate(self, row: dict) -> object:
        raise NotImplementedError


@dataclass
class Literal(Expression):
    """Literal value expression."""
    value: object

    def evaluate(self, row: dict) -> object:
        return self.value


@dataclass
class ColumnRef(Expression):
    """Column reference expression."""
    name: str
    table: str | None = None  # table alias qualifier (e.g., u.name → table="u")

    def evaluate(self, row: dict) -> object:
        return row.get(self.name)


@dataclass
class StarExpr(Expression):
    """STAR (*) expression for SELECT * and COUNT(*)."""
    def evaluate(self, row: dict) -> object:
        return '*'


@dataclass
class BinaryOp(Expression):
    """Binary operation expression."""
    op: str
    left: Expression
    right: Expression

    def evaluate(self, row: dict) -> object:
        left_val = self.left.evaluate(row)
        right_val = self.right.evaluate(row)

        if self.op == 'AND':
            return _to_bool(left_val) and _to_bool(right_val)
        if self.op == 'OR':
            return _to_bool(left_val) or _to_bool(right_val)
        if self.op == '=':
            return _compare_eq(left_val, right_val)
        if self.op in ('!=', '<>'):
            return not _compare_eq(left_val, right_val)
        if self.op == '<':
            return _compare_lt(left_val, right_val)
        if self.op == '>':
            return _compare_gt(left_val, right_val)
        if self.op == '<=':
            return _compare_le(left_val, right_val)
        if self.op == '>=':
            return _compare_ge(left_val, right_val)
        if self.op == '+':
            return left_val + right_val
        if self.op == '-':
            return left_val - right_val
        if self.op == '*':
            return left_val * right_val
        if self.op == '/':
            if right_val == 0:
                raise ExecutionError("Division by zero")
            return left_val / right_val

        raise ExecutionError(f"Unknown operator: {self.op}")


@dataclass
class UnaryOp(Expression):
    """Unary operation expression."""
    op: str
    operand: Expression

    def evaluate(self, row: dict) -> object:
        val = self.operand.evaluate(row)
        if self.op == 'NOT':
            return not _to_bool(val)
        if self.op == '-':
            return -val
        raise ExecutionError(f"Unknown unary operator: {self.op}")


@dataclass
class AggregateExpr(Expression):
    """Aggregate function expression (COUNT, SUM, AVG)."""
    func: str
    arg: Expression
    distinct: bool = False

    def evaluate(self, row: dict) -> object:
        raise NotImplementedError("AggregateExpr requires AggregateOperator")


@dataclass
class IsNullExpr(Expression):
    """IS NULL / IS NOT NULL expression."""
    operand: Expression
    negated: bool = False

    def evaluate(self, row: dict) -> object:
        val = self.operand.evaluate(row)
        is_null = val is None
        return not is_null if self.negated else is_null


def _to_bool(val: object) -> bool:
    """Convert value to boolean. NULL -> False."""
    if val is None:
        return False
    return bool(val)


def _compare_eq(left: object, right: object) -> bool:
    """Equality comparison. NULL on either side -> False."""
    if left is None or right is None:
        return False
    return left == right


def _compare_lt(left: object, right: object) -> bool:
    """Less-than comparison. NULL -> False."""
    if left is None or right is None:
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left < right
    if isinstance(left, str) and isinstance(right, str):
        return left < right
    raise ExecutionError(f"Cannot compare {type(left)} with {type(right)}")


def _compare_gt(left: object, right: object) -> bool:
    """Greater-than comparison. NULL -> False."""
    if left is None or right is None:
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left > right
    if isinstance(left, str) and isinstance(right, str):
        return left > right
    raise ExecutionError(f"Cannot compare {type(left)} with {type(right)}")


def _compare_le(left: object, right: object) -> bool:
    """Less-than-or-equal comparison. NULL -> False."""
    if left is None or right is None:
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left <= right
    if isinstance(left, str) and isinstance(right, str):
        return left <= right
    raise ExecutionError(f"Cannot compare {type(left)} with {type(right)}")


def _compare_ge(left: object, right: object) -> bool:
    """Greater-than-or-equal comparison. NULL -> False."""
    if left is None or right is None:
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left >= right
    if isinstance(left, str) and isinstance(right, str):
        return left >= right
    raise ExecutionError(f"Cannot compare {type(left)} with {type(right)}")
