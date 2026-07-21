# tinydb/index/index_manager.py
"""Index Manager: manages index metadata and auto-updates on DML."""
from dataclasses import dataclass
from tinydb.types import DataType
from tinydb.page import RowId
from tinydb.index.btree import BTreeIndex


@dataclass
class IndexMeta:
    name: str
    table_name: str
    column_name: str
    column_type: DataType
    root_page: int


class IndexManager:
    """Manages index lifecycle and DML hooks."""

    def __init__(self, catalog, file_manager, buffer_pool):
        self._catalog = catalog
        self._fm = file_manager
        self._pool = buffer_pool
        self._indexes: dict[str, IndexMeta] = {}
        self._table_indexes: dict[str, dict[str, str]] = {}
        self._btrees: dict[str, BTreeIndex] = {}

    def create_index(self, table_name: str, column_name: str, name: str) -> IndexMeta:
        """Create a new index on a table column."""
        if name in self._indexes:
            raise ValueError(f"Index '{name}' already exists")

        table_meta = self._catalog._tables.get(table_name)
        if table_meta is None:
            raise ValueError(f"Table '{table_name}' not found")

        column = None
        for col in table_meta.columns:
            if col.name == column_name:
                column = col
                break
        if column is None:
            raise ValueError(f"Column '{column_name}' not found in table '{table_name}'")

        btree = BTreeIndex(self._pool, key_type=column.data_type)
        meta = IndexMeta(
            name=name,
            table_name=table_name,
            column_name=column_name,
            column_type=column.data_type,
            root_page=btree.root_page,
        )
        self._indexes[name] = meta
        self._btrees[name] = btree

        if table_name not in self._table_indexes:
            self._table_indexes[table_name] = {}
        self._table_indexes[table_name][column_name] = name

        return meta

    def drop_index(self, name: str) -> None:
        """Drop an index by name."""
        if name not in self._indexes:
            raise ValueError(f"Index '{name}' not found")

        meta = self._indexes[name]
        del self._indexes[name]
        del self._btrees[name]

        if meta.table_name in self._table_indexes:
            col_map = self._table_indexes[meta.table_name]
            if meta.column_name in col_map:
                del col_map[meta.column_name]

    def get_index(self, table_name: str, column_name: str) -> IndexMeta | None:
        """Get index metadata for a table column."""
        index_name = self._table_indexes.get(table_name, {}).get(column_name)
        if index_name:
            return self._indexes.get(index_name)
        return None

    def after_insert(self, table_name: str, row_ptr: RowId, row: list) -> None:
        """Update all indexes after INSERT."""
        col_map = self._table_indexes.get(table_name, {})
        if not col_map:
            return

        table_meta = self._catalog._tables.get(table_name)
        if table_meta is None:
            return

        for col_idx, col in enumerate(table_meta.columns):
            index_name = col_map.get(col.name)
            if index_name:
                btree = self._btrees[index_name]
                key = row[col_idx]
                if key is not None:
                    btree.insert(key, row_ptr)

    def after_delete(self, table_name: str, row_ptr: RowId, old_row: list) -> None:
        """Remove index entries before DELETE."""
        col_map = self._table_indexes.get(table_name, {})
        if not col_map:
            return

        table_meta = self._catalog._tables.get(table_name)
        if table_meta is None:
            return

        for col_idx, col in enumerate(table_meta.columns):
            index_name = col_map.get(col.name)
            if index_name:
                btree = self._btrees[index_name]
                key = old_row[col_idx]
                if key is not None:
                    btree.delete(key, row_ptr)

    def after_update(self, table_name: str, row_ptr: RowId, old_row: list, new_row: list) -> None:
        """Update indexes after UPDATE for changed columns."""
        col_map = self._table_indexes.get(table_name, {})
        if not col_map:
            return

        table_meta = self._catalog._tables.get(table_name)
        if table_meta is None:
            return

        for col_idx, col in enumerate(table_meta.columns):
            if old_row[col_idx] == new_row[col_idx]:
                continue
            index_name = col_map.get(col.name)
            if index_name:
                btree = self._btrees[index_name]
                if old_row[col_idx] is not None:
                    btree.delete(old_row[col_idx], row_ptr)
                if new_row[col_idx] is not None:
                    btree.insert(new_row[col_idx], row_ptr)

    def find_matching_index(self, table_name: str, where_clause) -> IndexMeta | None:
        """Find an index matching a WHERE clause condition."""
        col_map = self._table_indexes.get(table_name, {})
        if not col_map or where_clause is None:
            return None

        col_name = getattr(where_clause, "column", None)
        if col_name and col_name in col_map:
            index_name = col_map[col_name]
            return self._indexes.get(index_name)
        return None
