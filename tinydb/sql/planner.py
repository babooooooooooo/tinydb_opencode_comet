"""Query planner: converts AST to operator tree."""
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
)
from tinydb.sql.expressions import (
    Expression, ColumnRef, AggregateExpr, StarExpr, _to_bool,
)
from tinydb.sql.executor import (
    Operator, ScanOperator, FilterOperator, ProjectOperator,
    AggregateOperator, SortOperator, LimitOperator,
    DmlOperator, CreateTableOperator, DropTableOperator,
)
from tinydb.sql.errors import PlanningError


class Planner:
    """Converts AST statements into operator trees."""

    def __init__(self, catalog, buffer_pool):
        self.catalog = catalog
        self.buffer_pool = buffer_pool

    def plan(self, stmt) -> Operator:
        if isinstance(stmt, SelectStatement):
            return self._plan_select(stmt)
        elif isinstance(stmt, (InsertStatement, UpdateStatement, DeleteStatement)):
            return DmlOperator(stmt, self.catalog, self.buffer_pool)
        elif isinstance(stmt, CreateTableStatement):
            return CreateTableOperator(stmt, self.catalog)
        elif isinstance(stmt, DropTableStatement):
            return DropTableOperator(stmt, self.catalog)
        else:
            raise PlanningError(f"Unknown statement type: {type(stmt)}")

    def _plan_select(self, stmt: SelectStatement) -> Operator:
        table = self.catalog.get_table(stmt.table)
        op: Operator = ScanOperator(table, self.buffer_pool)

        if stmt.where:
            op = FilterOperator(op, stmt.where)

        has_agg = any(isinstance(col, AggregateExpr) for col in stmt.columns)

        if has_agg or stmt.group_by:
            group_keys = stmt.group_by or []
            aggregations = []
            for col in stmt.columns:
                if isinstance(col, AggregateExpr):
                    alias = col.func.lower()
                    if isinstance(col.arg, StarExpr):
                        alias = col.func.lower() + "_*"
                    aggregations.append((alias, col.func, col.arg))
                elif isinstance(col, ColumnRef):
                    aggregations.append((col.name, 'VALUE', col))
                else:
                    aggregations.append((str(col), 'VALUE', col))
            op = AggregateOperator(op, group_keys, aggregations)
        else:
            projections = []
            for col in stmt.columns:
                if isinstance(col, StarExpr):
                    projections.append(('*', col))
                elif isinstance(col, ColumnRef):
                    projections.append((col.name, col))
                elif isinstance(col, AggregateExpr):
                    projections.append((col.func.lower(), col))
                else:
                    projections.append((str(col), col))
            op = ProjectOperator(op, projections)

        if stmt.order_by:
            op = SortOperator(op, stmt.order_by)

        if stmt.limit is not None or stmt.offset:
            op = LimitOperator(op, stmt.limit, stmt.offset or 0)

        return op
