# tinydb/catalog.py
"""System catalog: manages table metadata in tinydb_master table.

tinydb_master table schema:
  - table_name: TEXT (primary key)
  - columns:    TEXT (JSON array of column definitions)
  - root_page:  INTEGER
  - primary_key: TEXT
"""
import json
from dataclasses import dataclass
from tinydb.types import ColumnDef, DataType
from tinydb.row_format import serialize_row, deserialize_row
from tinydb.table import Table
from tinydb.page import (
    Page, PageType, create_empty_page,
    insert_row_into_page, get_all_rows_from_page, parse_page_header,
)
from tinydb.exceptions import TableExistsError, TableNotFoundError


# Catalog table column definitions
_CATALOG_COLUMNS = [
    ColumnDef(name="table_name", data_type=DataType.TEXT, nullable=False),
    ColumnDef(name="columns", data_type=DataType.TEXT, nullable=False),
    ColumnDef(name="root_page", data_type=DataType.INTEGER, nullable=False),
    ColumnDef(name="primary_key", data_type=DataType.TEXT, nullable=False),
]


@dataclass
class TableMeta:
    table_name: str
    columns: list[ColumnDef]
    root_page: int
    primary_key: str


class Catalog:
    """Manages table metadata persistence."""

    def __init__(self, file_manager, buffer_pool):
        self._fm = file_manager
        self._pool = buffer_pool
        self._tables: dict[str, TableMeta] = {}
        self._catalog_page_id: int = 0

    def load(self) -> None:
        """Load catalog from disk. Creates catalog table if not exists."""
        self._catalog_page_id = self._fm.catalog_root

        if self._catalog_page_id == 0:
            self._init_catalog()
        else:
            self._load_from_disk()

    def save(self) -> None:
        """Persist catalog to disk. Write all pages and flush."""
        self._save_to_disk()
        self._pool.flush()

    def create_table(self, name: str, columns: list[ColumnDef], pk: str) -> None:
        """Register a new table in the catalog."""
        if name in self._tables:
            raise TableExistsError(f"Table '{name}' already exists")

        root_page = self._fm.alloc_page()
        empty_page = create_empty_page(root_page, PageType.DATA)
        self._fm.write_page(root_page, empty_page.data)

        meta = TableMeta(
            table_name=name,
            columns=columns,
            root_page=root_page,
            primary_key=pk,
        )
        self._tables[name] = meta

        self._write_table_meta(meta)

    def drop_table(self, name: str) -> None:
        """Remove a table from the catalog."""
        if name not in self._tables:
            raise TableNotFoundError(f"Table '{name}' not found")

        del self._tables[name]

    def get_table(self, name: str) -> Table:
        """Get a Table object for the named table."""
        if name not in self._tables:
            raise TableNotFoundError(f"Table '{name}' not found")
        meta = self._tables[name]
        return Table(meta.table_name, meta.columns, meta.root_page, meta.primary_key)

    def list_tables(self) -> list[str]:
        """List all registered table names."""
        return list(self._tables.keys())

    # --- Internal methods ---

    def _init_catalog(self) -> None:
        """Create the initial catalog table."""
        self._catalog_page_id = self._fm.alloc_page()
        self._fm.catalog_root = self._catalog_page_id
        self._fm._write_header()

        empty_page = create_empty_page(self._catalog_page_id, PageType.CATALOG)
        self._fm.write_page(self._catalog_page_id, empty_page.data)

    def _load_from_disk(self) -> None:
        """Read all table metadata from catalog pages."""
        page_id = self._catalog_page_id
        while page_id != 0:
            raw = self._fm.read_page(page_id)
            header = parse_page_header(raw)
            page = Page(
                page_id=page_id,
                page_type=PageType.CATALOG,
                data=raw,
                dirty=False,
            )

            rows = get_all_rows_from_page(page)
            for row_data in rows:
                values = deserialize_row(row_data, _CATALOG_COLUMNS)
                if values is None:
                    continue
                table_name = values[0]
                columns_json = values[1]
                root_page = values[2]
                primary_key = values[3]

                columns = self._parse_columns_json(columns_json)
                self._tables[table_name] = TableMeta(
                    table_name=table_name,
                    columns=columns,
                    root_page=root_page,
                    primary_key=primary_key,
                )

            page_id = header["next_page_id"]

    def _write_table_meta(self, meta: TableMeta) -> None:
        """Write a single table's metadata into the catalog page."""
        columns_json = json.dumps([
            {
                "name": col.name,
                "data_type": col.data_type.value,
                "nullable": col.nullable,
                "primary_key": col.primary_key,
                "unique": col.unique,
            }
            for col in meta.columns
        ])

        row = [meta.table_name, columns_json, meta.root_page, meta.primary_key]
        serialized = serialize_row(row, _CATALOG_COLUMNS)

        raw = self._fm.read_page(self._catalog_page_id)
        page = Page(
            page_id=self._catalog_page_id,
            page_type=PageType.CATALOG,
            data=raw,
            dirty=True,
        )
        insert_row_into_page(page, serialized)
        self._fm.write_page(self._catalog_page_id, page.data)

    def _save_to_disk(self) -> None:
        """Rewrite the catalog pages from in-memory state."""
        page = create_empty_page(self._catalog_page_id, PageType.CATALOG)
        for meta in self._tables.values():
            columns_json = json.dumps([
                {
                    "name": col.name,
                    "data_type": col.data_type.value,
                    "nullable": col.nullable,
                    "primary_key": col.primary_key,
                    "unique": col.unique,
                }
                for col in meta.columns
            ])
            row = [meta.table_name, columns_json, meta.root_page, meta.primary_key]
            serialized = serialize_row(row, _CATALOG_COLUMNS)
            insert_row_into_page(page, serialized)

        self._fm.write_page(self._catalog_page_id, page.data)

    @staticmethod
    def _parse_columns_json(json_str: str) -> list[ColumnDef]:
        """Parse JSON back into ColumnDef list."""
        items = json.loads(json_str)
        return [
            ColumnDef(
                name=item["name"],
                data_type=DataType(item["data_type"]),
                nullable=item.get("nullable", True),
                primary_key=item.get("primary_key", False),
                unique=item.get("unique", False),
            )
            for item in items
        ]
