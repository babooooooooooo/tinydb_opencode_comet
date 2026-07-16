"""Tests for tinydb.concurrency.mvcc_manager module."""
import time
import pytest
from tinydb.concurrency.mvcc_manager import PageVersion, Snapshot, MVCCManager


class TestPageVersion:
    def test_creation(self):
        pv = PageVersion(data=b"hello", created_txn=1, deleted_txn=None, next=None)
        assert pv.data == b"hello"
        assert pv.created_txn == 1
        assert pv.deleted_txn is None
        assert pv.next is None


class TestSnapshot:
    def test_creation(self):
        snap = Snapshot(active_txns={1, 2}, timestamp=time.time())
        assert snap.active_txns == {1, 2}


class TestMVCCManagerBasic:
    def setup_method(self):
        self.mvcc = MVCCManager()

    def test_create_version(self):
        self.mvcc.create_version(page_id=0, data=b"v1", txn_id=1)
        snap = Snapshot(active_txns={1}, timestamp=time.time())
        result = self.mvcc.get_visible_version(0, snap)
        assert result == b"v1"

    def test_version_chain_descending(self):
        """Versions are sorted by txn_id descending (newest first)."""
        self.mvcc.create_version(page_id=0, data=b"v1", txn_id=1)
        self.mvcc.create_version(page_id=0, data=b"v2", txn_id=2)
        snap = Snapshot(active_txns={1, 2}, timestamp=time.time())
        result = self.mvcc.get_visible_version(0, snap)
        assert result == b"v2"  # newest visible

    def test_visibility_excludes_deleted(self):
        """A version is not visible if its deleted_txn is in active_txns."""
        self.mvcc.create_version(page_id=0, data=b"v1", txn_id=1)
        self.mvcc.mark_deleted(page_id=0, version_txn_id=1, txn_id=2)
        # Snapshot where txn 2 is active → v1 is deleted
        snap = Snapshot(active_txns={1, 2}, timestamp=time.time())
        result = self.mvcc.get_visible_version(0, snap)
        assert result is None

    def test_visibility_includes_created(self):
        """A version is visible if created_txn is in active_txns."""
        self.mvcc.create_version(page_id=0, data=b"v1", txn_id=1)
        # Snapshot where txn 1 is NOT active → v1 not visible
        snap = Snapshot(active_txns={2}, timestamp=time.time())
        result = self.mvcc.get_visible_version(0, snap)
        assert result is None

    def test_get_visible_version_no_versions(self):
        snap = Snapshot(active_txns={1}, timestamp=time.time())
        result = self.mvcc.get_visible_version(999, snap)
        assert result is None
