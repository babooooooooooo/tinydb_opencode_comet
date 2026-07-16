"""Volcano model executor operators."""
from tinydb.sql.expressions import (
    Expression, ColumnRef, AggregateExpr, StarExpr, _to_bool,
)
from tinydb.sql.ast import (
    SelectStatement, InsertStatement, UpdateStatement,
    DeleteStatement, CreateTableStatement, DropTableStatement,
)
from tinydb.sql.errors import ExecutionError, ConstraintError
from tinydb.sql.result import QueryResult
from tinydb.types import ColumnDef, DataType


class Operator:
    """Base class for all operators (Volcano model)."""

    def __iter__(self):
        return self

    def __next__(self) -> dict:
        raise NotImplementedError


class ScanOperator(Operator):
    """Full table scan operator."""

    def __init__(self, table, buffer_pool):
        self.table = table
        self.buffer_pool = buffer_pool

    def __iter__(self):
        col_names = [col.name for col in self.table.columns]
        for row_id, row_values in self.table.scan(self.buffer_pool):
            yield {"_rowid": row_id, **dict(zip(col_names, row_values))}


class NestedLoopJoinOperator(Operator):
    """Nested loop join: outer loop scans left, inner loop scans right."""

    def __init__(self, left_op, right_op, join_type, on_condition,
                 left_name, left_alias, left_cols,
                 right_name, right_alias, right_cols,
                 join_keys):
        self.left_op = left_op
        self.right_op = right_op
        self.join_type = join_type
        self.on_condition = on_condition
        self.left_name = left_name
        self.left_alias = left_alias
        self.left_cols = left_cols
        self.right_name = right_name
        self.right_alias = right_alias
        self.right_cols = right_cols
        self.join_keys = join_keys

    def __iter__(self):
        if self.join_type in ("RIGHT", "FULL"):
            right_rows = list(self.right_op)
        else:
            right_rows = None

        matched_right = set()

        for left_row in self.left_op:
            if right_rows is not None:
                right_iter = enumerate(right_rows)
            else:
                right_iter = enumerate(self.right_op)

            matched = False
            for j, right_row in right_iter:
                # Evaluate ON condition before prefixing (use raw combined row)
                # Add right first, then left overwrites — left takes precedence
                raw_combined = {}
                for k, v in right_row.items():
                    if k != '_rowid':
                        raw_combined[k] = v
                for k, v in left_row.items():
                    if k != '_rowid':
                        raw_combined[k] = v
                if self.on_condition is not None and not _to_bool(self.on_condition.evaluate(raw_combined)):
                    continue
                combined = self._combine_rows(left_row, right_row)
                matched = True
                matched_right.add(j)
                yield combined

            if not matched and self.join_type in ("LEFT", "FULL"):
                yield self._combine_with_nulls(left_row, None)

        if self.join_type in ("RIGHT", "FULL"):
            for j, right_row in enumerate(right_rows):
                if j not in matched_right:
                    yield self._combine_with_nulls(None, right_row)

    def _combine_rows(self, left_row, right_row):
        """Merge two rows, handling column name conflicts."""
        result = {}
        left_prefix = self.left_alias or self.left_name
        right_prefix = self.right_alias or self.right_name

        left_cols = {k: v for k, v in left_row.items() if k != '_rowid'}
        right_cols = {k: v for k, v in right_row.items() if k != '_rowid'}

        # Find conflicts
        conflicts = set(left_cols.keys()) & set(right_cols.keys())

        for k, v in left_cols.items():
            if k in conflicts:
                result[f'{left_prefix}_{k}'] = v
            else:
                result[k] = v

        for k, v in right_cols.items():
            if k in conflicts:
                result[f'{right_prefix}_{k}'] = v
            else:
                result[k] = v

        return result

    def _combine_with_nulls(self, left_row, right_row):
        """Combine a row with NULLs for the missing side (OUTER JOIN)."""
        result = {}
        left_prefix = self.left_alias or self.left_name
        right_prefix = self.right_alias or self.right_name

        if left_row is None:
            left_cols = {}
        else:
            left_cols = {k: v for k, v in left_row.items() if k != '_rowid'}

        if right_row is None:
            right_cols = {k: None for k in self.right_cols}
        else:
            right_cols = {k: v for k, v in right_row.items() if k != '_rowid'}

        conflicts = set(left_cols.keys()) & set(right_cols.keys())

        for k, v in left_cols.items():
            if k in conflicts:
                result[f'{left_prefix}_{k}'] = v
            else:
                result[k] = v

        for k, v in right_cols.items():
            if k in conflicts:
                result[f'{right_prefix}_{k}'] = v
            else:
                result[k] = v

        return result


class FilterOperator(Operator):
    """WHERE clause filter operator."""

    def __init__(self, source: Operator, condition: Expression):
        self.source = source
        self.condition = condition

    def __iter__(self):
        for row in self.source:
            val = self.condition.evaluate(row)
            if _to_bool(val):
                yield row


class ProjectOperator(Operator):
    """Column projection operator."""

    def __init__(self, source: Operator, columns: list):
        self.source = source
        self.columns = columns

    def __iter__(self):
        for row in self.source:
            result = {}
            for alias, expr in self.columns:
                if alias == '*' and isinstance(expr, StarExpr):
                    for k, v in row.items():
                        if k != '_rowid':
                            result[k] = v
                else:
                    result[alias] = expr.evaluate(row)
            yield result


class AggregateOperator(Operator):
    """Hash aggregation operator with GROUP BY."""

    def __init__(self, source: Operator,
                 group_keys: list,
                 aggregations: list):
        self.source = source
        self.group_keys = group_keys
        self.aggregations = aggregations

    def __iter__(self):
        groups: dict = {}

        for row in self.source:
            key = tuple(k.evaluate(row) for k in self.group_keys)
            if key not in groups:
                groups[key] = self._init_agg_state()

            state = groups[key]
            for i, (alias, func, arg_expr) in enumerate(self.aggregations):
                if func == 'VALUE':
                    state[i] = row.get(alias)
                else:
                    val = arg_expr.evaluate(row)
                    state[i] = self._accumulate(func, state[i], val)

        for key, state in groups.items():
            result = {}
            if self.group_keys:
                for i, k_exp in enumerate(self.group_keys):
                    if isinstance(k_exp, ColumnRef):
                        result[k_exp.name] = key[i]

            for i, (alias, func, _) in enumerate(self.aggregations):
                if func == 'VALUE':
                    result[alias] = state[i]
                else:
                    result[alias] = self._finalize(func, state[i])

            yield result

    def _init_agg_state(self) -> list:
        return [None] * len(self.aggregations)

    def _accumulate(self, func: str, state: object, val: object) -> object:
        if func == 'COUNT':
            return (state or 0) + 1
        elif func == 'SUM':
            if val is None:
                return state
            return (state or 0) + val
        elif func == 'AVG':
            if state is None:
                state = (0, 0)
            if val is not None:
                return (state[0] + val, state[1] + 1)
            return state
        raise ValueError(f"Unknown aggregate function: {func}")

    def _finalize(self, func: str, state: object) -> object:
        if state is None:
            return None
        if func == 'AVG':
            if state[1] == 0:
                return None
            return state[0] / state[1]
        return state


class SortOperator(Operator):
    """ORDER BY sort operator."""

    def __init__(self, source: Operator, order_keys: list):
        self.source = source
        self.order_keys = order_keys

    def __iter__(self):
        rows = list(self.source)
        for expr, direction in reversed(self.order_keys):
            rows.sort(
                key=lambda r, e=expr: (e.evaluate(r) is None, e.evaluate(r) or 0),
                reverse=(direction == 'DESC')
            )
        yield from rows


class LimitOperator(Operator):
    """LIMIT/OFFSET operator."""

    def __init__(self, source: Operator, limit, offset: int):
        self.source = source
        self.limit = limit
        self.offset = offset

    def __iter__(self):
        iterator = iter(self.source)
        for _ in range(self.offset):
            try:
                next(iterator)
            except StopIteration:
                return

        count = 0
        for row in iterator:
            if self.limit is not None and count >= self.limit:
                return
            yield row
            count += 1


class DmlOperator(Operator):
    """DML (INSERT/UPDATE/DELETE) operator."""

    def __init__(self, stmt, catalog, buffer_pool):
        self.stmt = stmt
        self.catalog = catalog
        self.buffer_pool = buffer_pool

    def __iter__(self):
        result = self._execute()
        yield {"_result": result}

    def _execute(self) -> QueryResult:
        if isinstance(self.stmt, InsertStatement):
            return self._execute_insert()
        elif isinstance(self.stmt, UpdateStatement):
            return self._execute_update()
        elif isinstance(self.stmt, DeleteStatement):
            return self._execute_delete()

    def _execute_insert(self) -> QueryResult:
        table = self.catalog.get_table(self.stmt.table)
        col_names = [col.name for col in table.columns]

        for value_exprs in self.stmt.values:
            row_values = [expr.evaluate({}) for expr in value_exprs]
            if self.stmt.columns:
                row_dict = dict(zip(self.stmt.columns, row_values))
                ordered_row = [row_dict.get(cn) for cn in col_names]
            else:
                ordered_row = row_values
            self._check_constraints(table, ordered_row)
            table.insert(self.buffer_pool, ordered_row)

        return QueryResult([], [], len(self.stmt.values))

    def _execute_update(self) -> QueryResult:
        table = self.catalog.get_table(self.stmt.table)
        col_names = [col.name for col in table.columns]
        updated = 0

        for row_id, row_values in table.scan(self.buffer_pool):
            row_dict = dict(zip(col_names, row_values))
            if self.stmt.where is None or _to_bool(self.stmt.where.evaluate(row_dict)):
                new_row = list(row_values)
                for col_name, expr in self.stmt.assignments:
                    col_idx = col_names.index(col_name)
                    new_row[col_idx] = expr.evaluate(row_dict)
                self._check_constraints_update(table, row_id, new_row)
                table.update(self.buffer_pool, row_id, new_row)
                updated += 1

        return QueryResult([], [], updated)

    def _execute_delete(self) -> QueryResult:
        table = self.catalog.get_table(self.stmt.table)
        col_names = [col.name for col in table.columns]
        to_delete = []

        for row_id, row_values in table.scan(self.buffer_pool):
            row_dict = dict(zip(col_names, row_values))
            if self.stmt.where is None or _to_bool(self.stmt.where.evaluate(row_dict)):
                to_delete.append(row_id)

        for row_id in to_delete:
            table.delete(self.buffer_pool, row_id)

        return QueryResult([], [], len(to_delete))

    def _check_constraints(self, table, row) -> None:
        for i, (val, col) in enumerate(zip(row, table.columns)):
            if not col.nullable and val is None:
                raise ConstraintError(
                    f"NOT NULL constraint violated on column '{col.name}'"
                )
            if col.primary_key or col.unique:
                self._check_unique(table, i, val, exclude_row_id=None)

    def _check_constraints_update(self, table, row_id, new_row) -> None:
        for i, (val, col) in enumerate(zip(new_row, table.columns)):
            if not col.nullable and val is None:
                raise ConstraintError(
                    f"NOT NULL constraint violated on column '{col.name}'"
                )
            if col.primary_key or col.unique:
                self._check_unique(table, i, val, exclude_row_id=row_id)

    def _check_unique(self, table, col_idx, value, exclude_row_id) -> None:
        for existing_id, existing_row in table.scan(self.buffer_pool):
            if exclude_row_id is not None:
                if (existing_id.page_id == exclude_row_id.page_id and
                        existing_id.slot_index == exclude_row_id.slot_index):
                    continue
            if existing_row[col_idx] == value:
                col = table.columns[col_idx]
                raise ConstraintError(
                    f"{'PRIMARY KEY' if col.primary_key else 'UNIQUE'} "
                    f"constraint violated on column '{col.name}': "
                    f"value {value!r} already exists"
                )


class CreateTableOperator(Operator):
    """CREATE TABLE operator."""

    def __init__(self, stmt, catalog):
        self.stmt = stmt
        self.catalog = catalog

    def __iter__(self):
        result = self._execute()
        yield {"_result": result}

    def _execute(self) -> QueryResult:
        columns = []
        pk = ""
        for col_def in self.stmt.columns:
            data_type = DataType(col_def.data_type.upper())
            col = ColumnDef(
                name=col_def.name,
                data_type=data_type,
                nullable=col_def.nullable,
                primary_key=col_def.primary_key,
                unique=col_def.unique,
            )
            columns.append(col)
            if col.primary_key:
                pk = col.name

        self.catalog.create_table(self.stmt.table, columns, pk)
        return QueryResult([], [], 0)


class DropTableOperator(Operator):
    """DROP TABLE operator."""

    def __init__(self, stmt, catalog):
        self.stmt = stmt
        self.catalog = catalog

    def __iter__(self):
        result = self._execute()
        yield {"_result": result}

    def _execute(self) -> QueryResult:
        self.catalog.drop_table(self.stmt.table)
        return QueryResult([], [], 0)


# === IndexScanOperator (integrated from tinydb-index-txn) ===

from tinydb.index.btree import BTreeIndex
from tinydb.index.index_manager import IndexMeta


class IndexScanOperator:
    """使用 B-tree 索引进行等值/范围扫描的算子。"""

    def __init__(self, table, index_meta: IndexMeta, condition):
        self.table = table
        self.index = index_meta
        self.condition = condition

    def execute(self, buffer_pool):
        btree = BTreeIndex(buffer_pool, key_type=self.index.column_type,
                           root_page=self.index.root_page)
        op = self.condition.op
        key = self.condition.value

        if op == "=":
            results = btree.search(key)
        elif op == ">":
            results = btree.range_scan(start=key, end=None, start_inclusive=False)
        elif op == ">=":
            results = btree.range_scan(start=key, end=None, start_inclusive=True)
        elif op == "<":
            results = btree.range_scan(start=None, end=key, end_inclusive=False)
        elif op == "<=":
            results = btree.range_scan(start=None, end=key, end_inclusive=True)
        elif op == "!=":
            # != 回退到全表扫描 + 过滤
            results = []
            for row_ptr, row in self.table.scan(buffer_pool):
                col_idx = next(
                    (i for i, c in enumerate(self.table.columns)
                     if c.name == self.condition.column), -1
                )
                if col_idx >= 0 and row[col_idx] != key:
                    results.append(row_ptr)
        else:
            raise ValueError(f"Unsupported operator for index scan: {op}")

        # 通过 row_ptr 从表中获取完整行
        rows = []
        for row_ptr in results:
            row = self.table.get(buffer_pool, row_ptr)
            if row is not None:
                rows.append(row)
        return rows
