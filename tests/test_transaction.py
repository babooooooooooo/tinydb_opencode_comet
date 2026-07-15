# tests/test_transaction.py
import pytest
from tinydb.transaction.txn_manager import TransactionManager, TransactionError
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.index.index_manager import IndexManager
from tinydb.page import create_empty_page, PageType


@pytest.fixture
def db_env(tmp_path):
    db_path = str(tmp_path / "test.db")
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    cat = Catalog(fm, pool)
    cat.load()
    imgr = IndexManager(cat, fm, pool)
    yield fm, pool, cat, imgr
    fm.close()


class TestTransactionManager:
    def test_begin_commit(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn = tm.begin()
        assert txn.state == "active"
        tm.commit()
        assert txn.state == "committed"

    def test_begin_rollback(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn = tm.begin()
        tm.rollback()
        assert txn.state == "aborted"

    def test_nested_txn_rejected(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        tm.begin()
        with pytest.raises(TransactionError):
            tm.begin()

    def test_no_active_txn_error(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        with pytest.raises(TransactionError):
            tm.commit()
        with pytest.raises(TransactionError):
            tm.rollback()

    def test_has_active_txn(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        assert not tm.has_active_txn()
        tm.begin()
        assert tm.has_active_txn()
        tm.commit()
        assert not tm.has_active_txn()

    def test_ensure_shadow(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        tm.begin()
        shadow_id = tm.ensure_shadow(1)
        assert shadow_id != 1
        assert tm.ensure_shadow(1) == shadow_id
        tm.commit()
