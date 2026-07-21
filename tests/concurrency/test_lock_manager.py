"""Tests for tinydb.concurrency.lock_manager module."""
import threading
import time
from tinydb.concurrency.lock_manager import LockMode, LockManager


class TestLockMode:
    def test_enum_values(self):
        assert LockMode.SHARED.value == "S"
        assert LockMode.EXCLUSIVE.value == "X"


class TestLockManagerBasic:
    def setup_method(self):
        self.lm = LockManager()

    def test_acquire_shared_lock(self):
        result = self.lm.acquire(txn_id=1, page_id=0, mode=LockMode.SHARED)
        assert result is True
        assert 1 in self.lm.get_lock_holders(0)

    def test_acquire_exclusive_lock(self):
        result = self.lm.acquire(txn_id=1, page_id=0, mode=LockMode.EXCLUSIVE)
        assert result is True
        assert 1 in self.lm.get_lock_holders(0)

    def test_release_lock(self):
        self.lm.acquire(txn_id=1, page_id=0, mode=LockMode.EXCLUSIVE)
        self.lm.release(txn_id=1, page_id=0)
        assert 1 not in self.lm.get_lock_holders(0)

    def test_release_all(self):
        self.lm.acquire(txn_id=1, page_id=0, mode=LockMode.SHARED)
        self.lm.acquire(txn_id=1, page_id=1, mode=LockMode.EXCLUSIVE)
        self.lm.release_all(txn_id=1)
        assert 1 not in self.lm.get_lock_holders(0)
        assert 1 not in self.lm.get_lock_holders(1)

    def test_get_lock_holders_empty(self):
        assert self.lm.get_lock_holders(999) == set()


class TestLockCompatibility:
    def setup_method(self):
        self.lm = LockManager()

    def test_shared_shared_compatible(self):
        """Two transactions can hold SHARED on the same page."""
        assert self.lm.acquire(1, 0, LockMode.SHARED) is True
        assert self.lm.acquire(2, 0, LockMode.SHARED) is True
        assert self.lm.get_lock_holders(0) == {1, 2}

    def test_shared_exclusive_conflict(self):
        """SHARED blocks EXCLUSIVE from another txn."""
        self.lm.acquire(1, 0, LockMode.SHARED)
        # txn 2 tries EXCLUSIVE — should block then timeout
        result = self.lm.acquire(2, 0, LockMode.EXCLUSIVE, timeout=0.1)
        assert result is False

    def test_exclusive_shared_conflict(self):
        """EXCLUSIVE blocks SHARED from another txn."""
        self.lm.acquire(1, 0, LockMode.EXCLUSIVE)
        result = self.lm.acquire(2, 0, LockMode.SHARED, timeout=0.1)
        assert result is False

    def test_exclusive_exclusive_conflict(self):
        """EXCLUSIVE blocks EXCLUSIVE from another txn."""
        self.lm.acquire(1, 0, LockMode.EXCLUSIVE)
        result = self.lm.acquire(2, 0, LockMode.EXCLUSIVE, timeout=0.1)
        assert result is False

    def test_release_unblocks_waiter(self):
        """Releasing a lock unblocks a waiting transaction."""
        self.lm.acquire(1, 0, LockMode.EXCLUSIVE)
        result_holder = {"value": None}

        def waiter():
            result_holder["value"] = self.lm.acquire(2, 0, LockMode.SHARED, timeout=2.0)

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.2)
        self.lm.release(1, 0)
        t.join(timeout=3.0)
        assert result_holder["value"] is True
        assert 2 in self.lm.get_lock_holders(0)

    def test_upgrade_shared_to_exclusive(self):
        """A txn can upgrade S→X when it's the only holder."""
        self.lm.acquire(1, 0, LockMode.SHARED)
        assert self.lm.upgrade(1, 0) is True

    def test_upgrade_blocked_by_other_holder(self):
        """S→X upgrade fails when another txn holds SHARED."""
        self.lm.acquire(1, 0, LockMode.SHARED)
        self.lm.acquire(2, 0, LockMode.SHARED)
        assert self.lm.upgrade(1, 0) is False
