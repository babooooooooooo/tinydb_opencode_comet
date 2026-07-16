"""Tests for tinydb.concurrency.lock_manager module."""
import time
import pytest
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
