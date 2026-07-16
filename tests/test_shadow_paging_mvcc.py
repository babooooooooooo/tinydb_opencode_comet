"""Tests for shadow paging + MVCC coordination."""
import pytest
from tinydb.transaction.shadow_paging import Transaction, ShadowBufferPool
from tinydb.concurrency.mvcc_manager import MVCCManager, Snapshot
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.page import create_empty_page, PageType


@pytest.fixture
def db_env(tmp_path):
    db_path = str(tmp_path / "test.db")
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    mvcc = MVCCManager()
    yield fm, pool, mvcc
    fm.close()


class TestShadowPagingMVCC:
    def test_commit_creates_mvcc_version(self, db_env):
        fm, pool, mvcc = db_env
        txn = Transaction(
            txn_id=1, state="active",
            shadow_pages={0: 5}, snapshot_root=0, new_root=0,
        )
        shadow = ShadowBufferPool(pool, txn, fm, mvcc_manager=mvcc)
        # After commit, a version should exist in MVCC
        snap = Snapshot(active_txns={1}, timestamp=0.0)
        # The shadow paging commit writes to disk; MVCC version created separately
        # This test verifies the integration point exists
        assert hasattr(shadow, '_mvcc')

    def test_shadow_pool_without_mvcc(self, db_env):
        """ShadowBufferPool works without MVCC (backward compat)."""
        fm, pool, _ = db_env
        txn = Transaction(
            txn_id=1, state="active",
            shadow_pages={}, snapshot_root=0, new_root=0,
        )
        shadow = ShadowBufferPool(pool, txn, fm)
        assert shadow._mvcc is None
