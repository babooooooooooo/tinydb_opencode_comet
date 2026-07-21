# tests/test_transaction.py
import pytest
from tinydb.transaction.txn_manager import TransactionManager, TransactionError
from tinydb.concurrency.isolation import IsolationLevel
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.index.index_manager import IndexManager


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
        txn_id = tm.begin()
        entry = tm.get_active_txns()[txn_id]
        assert entry.txn.state == "active"
        tm.commit()
        assert entry.txn.state == "committed"

    def test_begin_rollback(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn_id = tm.begin()
        entry = tm.get_active_txns()[txn_id]
        tm.rollback()
        assert entry.txn.state == "aborted"

    def test_multiple_txn_supported(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn1 = tm.begin()
        txn2 = tm.begin()
        assert txn1 != txn2
        tm.commit(txn1)
        tm.commit(txn2)

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
        txn_id = tm.begin()
        assert tm.has_active_txn()
        tm.commit(txn_id)
        assert not tm.has_active_txn()

    def test_ensure_shadow(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn_id = tm.begin()
        shadow_id = tm.ensure_shadow(1)
        assert shadow_id != 1
        assert tm.ensure_shadow(1) == shadow_id
        tm.commit(txn_id)


class TestMultiTransaction:
    def test_begin_returns_txn_id(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn_id = tm.begin()
        assert isinstance(txn_id, int)
        assert txn_id > 0

    def test_multiple_concurrent_txns(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn1 = tm.begin()
        txn2 = tm.begin()
        assert txn1 != txn2
        assert len(tm.get_active_txns()) == 2

    def test_commit_specific_txn(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn1 = tm.begin()
        txn2 = tm.begin()
        tm.commit(txn1)
        assert txn1 not in tm.get_active_txns()
        assert txn2 in tm.get_active_txns()

    def test_rollback_specific_txn(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn1 = tm.begin()
        txn2 = tm.begin()
        tm.rollback(txn1)
        assert txn1 not in tm.get_active_txns()
        assert txn2 in tm.get_active_txns()

    def test_get_snapshot(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn1 = tm.begin()
        snap = tm.get_snapshot(txn1)
        assert txn1 in snap.active_txns

    def test_isolation_level_set(self, db_env):
        """Transaction gets the specified isolation level."""
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn_id = tm.begin(isolation=IsolationLevel.SERIALIZABLE)
        entry = tm.get_active_txns()[txn_id]
        assert entry.isolation == IsolationLevel.SERIALIZABLE
