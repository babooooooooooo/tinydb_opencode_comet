"""tinydb: a tiny embedded relational database for learning."""

from tinydb.types import DataType, ColumnDef, Value
from tinydb.exceptions import (
    StorageError,
    StorageCorruptionError,
    PageOutOfRangeError,
    TableExistsError,
    TableNotFoundError,
    SchemaMismatchError,
    StorageFullError,
)
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog, TableMeta
from tinydb.table import Table
from tinydb.page import Page, PageType, RowId
from tinydb.database import Database, QueryResult, DatabaseError
from tinydb.index import BTreeIndex, IndexManager, IndexMeta
from tinydb.transaction import Transaction, ShadowBufferPool, TransactionManager
from tinydb.concurrency import (
    IsolationLevel, LockMode, LockManager,
    PageVersion, Snapshot, MVCCManager,
    DeadlockDetector,
)
from tinydb.sql import IndexScanOperator, Planner
from tinydb.cli import REPL

__version__ = "0.1.0"

__all__ = [
    "DataType",
    "ColumnDef",
    "Value",
    "StorageError",
    "StorageCorruptionError",
    "PageOutOfRangeError",
    "TableExistsError",
    "TableNotFoundError",
    "SchemaMismatchError",
    "StorageFullError",
    "FileManager",
    "BufferPool",
    "Catalog",
    "TableMeta",
    "Table",
    "Page",
    "PageType",
    "RowId",
    "Database",
    "QueryResult",
    "DatabaseError",
    "BTreeIndex",
    "IndexManager",
    "IndexMeta",
    "Transaction",
    "ShadowBufferPool",
    "TransactionManager",
    "IsolationLevel",
    "LockMode",
    "LockManager",
    "PageVersion",
    "Snapshot",
    "MVCCManager",
    "DeadlockDetector",
    "IndexScanOperator",
    "Planner",
    "REPL",
]
