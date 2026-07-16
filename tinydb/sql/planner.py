"""Query planner: converts AST to operator tree."""
from dataclasses import dataclass

from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
    TableRef, JoinClause,
)
from tinydb.sql.expressions import (
    Expression, ColumnRef, AggregateExpr, StarExpr, BinaryOp, _to_bool,
)
from tinydb.sql.executor import (
    Operator, ScanOperator, FilterOperator, ProjectOperator,
    AggregateOperator, SortOperator, LimitOperator,
    DmlOperator, CreateTableOperator, DropTableOperator,
)
from tinydb.sql.errors import PlanningError


@dataclass
class _JoinInput:
    """Internal: tracks operator + metadata for a join input side."""
    op: object  # Operator
    table_name: str
    alias: str | None
    columns: list  # list[str]


class JoinPlanner:
    """Plans JOIN clauses into operator trees with algorithm selection."""

    def __init__(self, catalog, buffer_pool):
        self.catalog = catalog
        self.buffer_pool = buffer_pool

    def plan_joins(self, from_table, joins, where):
        """Build operator tree for FROM + JOINs."""
        left = self._build_join_input(from_table)

        if not joins:
            return left.op

        for join in joins:
            # Resolve NATURAL JOIN before processing
            if join.join_type == "NATURAL":
                join = self._resolve_natural_join(left, join)

            right = self._build_join_input(join.right_table)
            join_keys = self._extract_join_keys(join)
            algorithm = self._choose_algorithm(join, left, right, join_keys)
            join_op = self._build_join_operator(algorithm, left, right, join, join_keys)
            left = _JoinInput(join_op, left.table_name, left.alias, left.columns)

        return left.op

    def _resolve_natural_join(self, left_info, join):
        """Resolve NATURAL JOIN by finding common columns between tables."""
        common = set(left_info.columns) & set(
            c.name for c in self.catalog.get_table(join.right_table.name).columns
        )
        if not common:
            # No common columns → treat as CROSS JOIN
            return JoinClause(
                join_type="CROSS",
                right_table=join.right_table,
                on_condition=None,
            )
        # Use the first common column as join key
        key = sorted(common)[0]
        on_condition = BinaryOp('=', ColumnRef(key), ColumnRef(key))
        return JoinClause(
            join_type="INNER",
            right_table=join.right_table,
            on_condition=on_condition,
            using_columns=[key],
        )

    def _build_join_input(self, tableref):
        """Build scan operator + metadata for a table reference."""
        table = self.catalog.get_table(tableref.name)
        op = ScanOperator(table, self.buffer_pool)
        columns = [c.name for c in table.columns]
        return _JoinInput(op, tableref.name, tableref.alias, columns)

    def _extract_join_keys(self, join):
        """Extract equi-join key column names from ON condition or USING."""
        if join.using_columns:
            return join.using_columns
        if join.on_condition is None:
            return []
        # Extract from BinaryOp(=, ColumnRef, ColumnRef)
        cond = join.on_condition
        if hasattr(cond, 'op') and cond.op == '=':
            left_keys = self._get_eq_keys(cond.left)
            right_keys = self._get_eq_keys(cond.right)
            if left_keys and right_keys:
                return left_keys
        return []

    def _get_eq_keys(self, expr):
        """Extract column name from a ColumnRef in an equality condition."""
        if hasattr(expr, 'name') and hasattr(expr, 'table'):
            return [expr.name]
        return []

    def _choose_algorithm(self, join, left_info, right_info, join_keys):
        """Choose join algorithm based on heuristics."""
        if join.join_type == "CROSS":
            return "nested_loop"
        if not join_keys:
            return "nested_loop"
        # For small tables, use nested_loop
        # For larger tables, could use hash or sort_merge
        # Simple heuristic: always nested_loop for now (can be extended)
        return "nested_loop"

    def _build_join_operator(self, algorithm, left_info, right_info, join, join_keys):
        """Construct the appropriate JoinOperator."""
        if algorithm == "hash":
            from tinydb.sql.executor import HashJoinOperator
            return HashJoinOperator(
                left_info.op, right_info.op, join.join_type, join.on_condition,
                left_info.table_name, left_info.alias, left_info.columns,
                right_info.table_name, right_info.alias, right_info.columns,
                join_keys,
            )
        elif algorithm == "sort_merge":
            from tinydb.sql.executor import SortMergeJoinOperator
            return SortMergeJoinOperator(
                left_info.op, right_info.op, join.join_type, join.on_condition,
                left_info.table_name, left_info.alias, left_info.columns,
                right_info.table_name, right_info.alias, right_info.columns,
                join_keys,
            )
        else:
            from tinydb.sql.executor import NestedLoopJoinOperator
            return NestedLoopJoinOperator(
                left_info.op, right_info.op, join.join_type, join.on_condition,
                left_info.table_name, left_info.alias, left_info.columns,
                right_info.table_name, right_info.alias, right_info.columns,
                join_keys,
            )


class Planner:
    """Converts AST statements into operator trees."""

    def __init__(self, catalog, buffer_pool):
        self.catalog = catalog
        self.buffer_pool = buffer_pool
        self._join_planner = JoinPlanner(catalog, buffer_pool)

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
        if stmt.joins:
            op = self._join_planner.plan_joins(stmt.from_table, stmt.joins, stmt.where)
        else:
            table = self.catalog.get_table(stmt.from_table.name)
            op = ScanOperator(table, self.buffer_pool)

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
