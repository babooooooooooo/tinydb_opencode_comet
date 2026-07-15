"""Shared fixtures for SQL engine tests."""
import tempfile
from pathlib import Path
import pytest
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.types import ColumnDef, DataType


@pytest.fixture
def tmp_db_path():
    """Provide a temporary database file path."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "test.db"


@pytest.fixture
def catalog_and_pool(tmp_db_path):
    """Provide a Catalog with a pre-built 'users' table containing 3 rows."""
    db_path = str(tmp_db_path)
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    cat = Catalog(fm, pool)
    cat.load()

    cat.create_table("users", [
        ColumnDef(name="id", data_type=DataType.INTEGER, nullable=False),
        ColumnDef(name="name", data_type=DataType.TEXT),
        ColumnDef(name="age", data_type=DataType.INTEGER),
    ], pk="id")

    tbl = cat.get_table("users")
    tbl.insert(pool, [1, "Alice", 30])
    tbl.insert(pool, [2, "Bob", 25])
    tbl.insert(pool, [3, "Charlie", 35])

    yield cat, pool
    fm.close()
