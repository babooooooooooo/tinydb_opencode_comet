# tinydb/sql/executor.py
"""Index-aware query executor with planner."""
from tinydb.index.btree import BTreeIndex
from tinydb.index.index_manager import IndexMeta


class IndexScanOperator:
    """Scan using B-tree index for equality/range conditions."""

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
            for row_ptr, row in self.table.scan(buffer_pool):
                col_idx = next(
                    (i for i, c in enumerate(self.table.columns)
                     if c.name == self.condition.column), -1
                )
                if col_idx >= 0 and row[col_idx] != key:
                    yield row_ptr, row
            return
        else:
            results = []

        for row_ptr in results:
            row = self.table.get(buffer_pool, row_ptr)
            if row is not None:
                yield row_ptr, row


class Planner:
    """Simple heuristic planner: use index if available."""

    def __init__(self, index_manager=None):
        self._index_mgr = index_manager

    def _choose_scan(self, table, where_clause):
        """Choose scan strategy. Returns IndexScanOperator or None (full scan)."""
        if self._index_mgr and where_clause:
            index = self._index_mgr.find_matching_index(table.table_name, where_clause)
            if index:
                return IndexScanOperator(table, index, where_clause)
        return None
