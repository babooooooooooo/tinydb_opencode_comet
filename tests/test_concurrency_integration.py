"""End-to-end concurrency integration tests."""
import threading
import time
import pytest
from tinydb.concurrency.lock_manager import LockManager, LockMode
from tinydb.concurrency.mvcc_manager import MVCCManager, Snapshot
from tinydb.concurrency.deadlock_detector import DeadlockDetector
from tinydb.concurrency.isolation import IsolationLevel, default_isolation


class TestConcurrencyIntegration:
    def test_lock_mvcc_deadlock_together(self):
        """Full pipeline: lock -> MVCC read -> deadlock detect."""
        lm = LockManager()
        mvcc = MVCCManager()
        dd = DeadlockDetector()

        # txn 1 writes a version
        lm.acquire(1, page_id=0, mode=LockMode.EXCLUSIVE)
        mvcc.create_version(0, b"data_v1", txn_id=1)
        lm.release_all(1)

        # txn 2 reads with snapshot
        snap = Snapshot(active_txns={1, 2}, timestamp=time.time())
        result = mvcc.get_visible_version(0, snap)
        assert result == b"data_v1"

        # deadlock: 3 waits for 4, 4 waits for 3
        dd.add_wait_edge(3, 4)
        dd.add_wait_edge(4, 3)
        cycle = dd.detect_cycle()
        assert cycle is not None
        victim = dd.select_victim(cycle)
        assert victim == 4  # youngest

    def test_concurrent_lock_acquisition(self):
        """Multiple threads acquiring/releasing locks."""
        lm = LockManager()
        results = []

        def worker(txn_id):
            acquired = lm.acquire(txn_id, page_id=0, mode=LockMode.SHARED, timeout=1.0)
            results.append((txn_id, acquired))
            if acquired:
                time.sleep(0.05)
                lm.release_all(txn_id)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3.0)

        # All should have acquired (shared-compatible)
        assert all(r[1] for r in results)

    def test_deadlock_timeout_recovery(self):
        """Timeout-based deadlock recovery."""
        lm = LockManager()
        lm.acquire(1, 0, LockMode.EXCLUSIVE)

        # txn 2 times out waiting
        result = lm.acquire(2, 0, LockMode.SHARED, timeout=0.2)
        assert result is False

        # txn 1 releases, txn 2 can now acquire
        lm.release_all(1)
        result = lm.acquire(2, 0, LockMode.SHARED, timeout=1.0)
        assert result is True

    def test_isolation_default(self):
        """Default isolation is REPEATABLE READ."""
        assert default_isolation() == IsolationLevel.REPEATABLE_READ
