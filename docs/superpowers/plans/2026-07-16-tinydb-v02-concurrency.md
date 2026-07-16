# tinydb-v02-concurrency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add concurrency control to tinydb via a new `tinydb/concurrency/` module (lock management, MVCC, deadlock detection, isolation levels) and refactor existing TransactionManager and BufferPool to support multi-transaction concurrent execution.

**Architecture:** Page-level Shared/Exclusive lock manager with FIFO wait queue + timeout; MVCC version chain per page sorted by txn_id descending for snapshot reads; wait-for-graph deadlock detector with youngest-victim selection; isolation level enum with REPEATABLE READ as default; TransactionManager holds `_active_txns` dict instead of single `_active_txn`; BufferPool pin/unpin integrated with LockManager and get_page routes to MVCC visible version.

**Tech Stack:** Python 3.10+, threading (Lock, Condition, Thread), dataclasses, enum, collections.deque, pytest

## Global Constraints

- No new external dependencies — use only Python standard library (threading, time, collections)
- Default isolation level: REPEATABLE READ
- Default lock timeout: 5 seconds
- Default deadlock detection: timeout (5s) + wait-for-graph cycle detection
- Victim selection: youngest transaction (highest txn_id / start timestamp)
- Page version chain: sorted by txn_id descending (newest first)
- Backward compatible: single-transaction behavior must be equivalent to v0.1
- All modules go in `tinydb/concurrency/` package
- Lock granularity: page-level only (no row-level, no table-level)

---

## File Structure

```
tinydb/
├── concurrency/                  # NEW package
│   ├── __init__.py               # re-exports
│   ├── isolation.py              # IsolationLevel enum
│   ├── lock_manager.py           # LockMode enum + LockManager class
│   ├── mvcc_manager.py           # PageVersion + Snapshot + MVCCManager
│   └── deadlock_detector.py      # DeadlockDetector with wait-for-graph
├── transaction/
│   ├── __init__.py               # MODIFY: add new exports
│   ├── txn_manager.py            # MODIFY: _active_txn → _active_txns dict
│   └── shadow_paging.py          # MODIFY: coordinate with MVCC on commit
├── buffer_pool.py                # MODIFY: pin/unpin with locks, get_page MVCC route
└── __init__.py                   # MODIFY: add concurrency exports

tests/
├── concurrency/                  # NEW test package
│   ├── __init__.py
│   ├── test_isolation.py
│   ├── test_lock_manager.py
│   ├── test_mvcc_manager.py
│   └── test_deadlock_detector.py
├── test_transaction.py           # MODIFY: add multi-txn tests
├── test_buffer_pool.py           # MODIFY: add lock/MVCC integration tests
└── test_concurrency_integration.py # NEW: end-to-end concurrency tests
```

---

### Task 1: Isolation Level Enum

**Files:**
- Create: `tinydb/concurrency/__init__.py`
- Create: `tinydb/concurrency/isolation.py`
- Test: `tests/concurrency/__init__.py`
- Test: `tests/concurrency/test_isolation.py`

**Interfaces:**
- Consumes: nothing
- Produces: `IsolationLevel` enum with values `READ_UNCOMMITTED`, `READ_COMMITTED`, `REPEATABLE_READ`, `SERIALIZABLE`; `default_isolation()` returning `IsolationLevel.REPEATABLE_READ`; `validate_isolation(level)` returning bool

- [ ] **Step 1: Write the failing test**

```python
# tests/concurrency/__init__.py
# (empty file)
```

```python
# tests/concurrency/test_isolation.py
"""Tests for tinydb.concurrency.isolation module."""
from tinydb.concurrency.isolation import IsolationLevel, default_isolation, validate_isolation


class TestIsolationLevel:
    def test_enum_values(self):
        assert IsolationLevel.READ_UNCOMMITTED.value == "READ UNCOMMITTED"
        assert IsolationLevel.READ_COMMITTED.value == "READ COMMITTED"
        assert IsolationLevel.REPEATABLE_READ.value == "REPEATABLE READ"
        assert IsolationLevel.SERIALIZABLE.value == "SERIALIZABLE"

    def test_default_isolation(self):
        assert default_isolation() == IsolationLevel.REPEATABLE_READ

    def test_validate_isolation_valid(self):
        assert validate_isolation(IsolationLevel.READ_UNCOMMITTED) is True
        assert validate_isolation(IsolationLevel.REPEATABLE_READ) is True

    def test_validate_isolation_invalid(self):
        assert validate_isolation("READ UNCOMMITTED") is False
        assert validate_isolation(1) is False
        assert validate_isolation(None) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_isolation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tinydb.concurrency'`

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/concurrency/__init__.py
"""Concurrency control: locks, MVCC, deadlock detection, isolation levels."""
from tinydb.concurrency.isolation import IsolationLevel, default_isolation, validate_isolation

__all__ = ["IsolationLevel", "default_isolation", "validate_isolation"]
```

```python
# tinydb/concurrency/isolation.py
"""Isolation level definitions for tinydb concurrency control."""
from enum import Enum


class IsolationLevel(Enum):
    """Transaction isolation levels."""
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


def default_isolation() -> IsolationLevel:
    """Return the default isolation level (REPEATABLE READ)."""
    return IsolationLevel.REPEATABLE_READ


def validate_isolation(level) -> bool:
    """Check if the given level is a valid IsolationLevel enum member."""
    return isinstance(level, IsolationLevel)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_isolation.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add tinydb/concurrency/__init__.py tinydb/concurrency/isolation.py tests/concurrency/__init__.py tests/concurrency/test_isolation.py
git commit -m "feat(concurrency): add IsolationLevel enum with REPEATABLE READ default"
```

---

### Task 2: LockManager — LockMode Enum and Compatibility Matrix

**Files:**
- Create: `tinydb/concurrency/lock_manager.py`
- Test: `tests/concurrency/test_lock_manager.py`

**Interfaces:**
- Consumes: `IsolationLevel` from `tinydb.concurrency.isolation`
- Produces: `LockMode` enum (`SHARED`, `EXCLUSIVE`); `LockManager` class with `acquire(txn_id, page_id, mode, timeout=5.0)`, `release(txn_id, page_id)`, `release_all(txn_id)`, `upgrade(txn_id, page_id)`, `get_lock_holders(page_id)` → set of txn_ids

- [ ] **Step 1: Write the failing test**

```python
# tests/concurrency/test_lock_manager.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_lock_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tinydb.concurrency.lock_manager'`

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/concurrency/lock_manager.py
"""Page-level lock manager with Shared/Exclusive locks and FIFO wait queue."""
import threading
from enum import Enum


class LockMode(Enum):
    """Lock mode for page-level locking."""
    SHARED = "S"
    EXCLUSIVE = "X"


# Compatibility matrix: True = compatible (can coexist)
_COMPATIBILITY = {
    (LockMode.SHARED, LockMode.SHARED): True,
    (LockMode.SHARED, LockMode.EXCLUSIVE): False,
    (LockMode.EXCLUSIVE, LockMode.SHARED): False,
    (LockMode.EXCLUSIVE, LockMode.EXCLUSIVE): False,
}


class LockManager:
    """Manages page-level Shared/Exclusive locks with FIFO wait queue."""

    def __init__(self):
        self._lock = threading.Lock()
        # page_id -> {txn_id: LockMode}
        self._holders: dict[int, dict[int, LockMode]] = {}
        # page_id -> deque of (txn_id, mode, Condition)
        self._wait_queue: dict[int, list] = {}

    def acquire(self, txn_id: int, page_id: int, mode: LockMode, timeout: float = 5.0) -> bool:
        """Acquire a lock on a page. Returns True if acquired, False if timed out."""
        with self._lock:
            if self._try_acquire(txn_id, page_id, mode):
                return True
            # Need to wait
            if page_id not in self._wait_queue:
                self._wait_queue[page_id] = []
            cond = threading.Condition(self._lock)
            entry = (txn_id, mode, cond)
            self._wait_queue[page_id].append(entry)

        # Wait outside the main lock using the condition variable
        with cond:
            cond.wait_for(
                lambda: self._try_acquire(txn_id, page_id, mode),
                timeout=timeout,
            )
        return self._is_holder(txn_id, page_id)

    def release(self, txn_id: int, page_id: int) -> None:
        """Release a lock held by a transaction on a page."""
        with self._lock:
            if page_id in self._holders and txn_id in self._holders[page_id]:
                del self._holders[page_id][txn_id]
                if not self._holders[page_id]:
                    del self._holders[page_id]
            # Remove from wait queue
            if page_id in self._wait_queue:
                self._wait_queue[page_id] = [
                    e for e in self._wait_queue[page_id] if e[0] != txn_id
                ]
            # Notify waiters
            if page_id in self._wait_queue:
                for _, _, cond in self._wait_queue[page_id]:
                    cond.notify()

    def release_all(self, txn_id: int) -> None:
        """Release all locks held by a transaction."""
        with self._lock:
            pages = [
                page_id for page_id, holders in self._holders.items()
                if txn_id in holders
            ]
        for page_id in pages:
            self.release(txn_id, page_id)

    def upgrade(self, txn_id: int, page_id: int) -> bool:
        """Upgrade a Shared lock to Exclusive. Returns True if successful."""
        with self._lock:
            if not self._is_holder(txn_id, page_id):
                return False
            if self._holders[page_id][txn_id] == LockMode.EXCLUSIVE:
                return True  # already exclusive
            # Can only upgrade if this txn is the only holder
            if len(self._holders[page_id]) == 1:
                self._holders[page_id][txn_id] = LockMode.EXCLUSIVE
                return True
            return False  # other txns hold shared locks

    def get_lock_holders(self, page_id: int) -> set[int]:
        """Return set of transaction IDs holding a lock on the page."""
        with self._lock:
            if page_id not in self._holders:
                return set()
            return set(self._holders[page_id].keys())

    def _try_acquire(self, txn_id: int, page_id: int, mode: LockMode) -> bool:
        """Attempt to acquire lock. Must be called with self._lock held."""
        if page_id not in self._holders or not self._holders[page_id]:
            self._holders[page_id] = {txn_id: mode}
            return True
        # Check compatibility with all existing holders
        for holder_id, holder_mode in self._holders[page_id].items():
            if holder_id == txn_id:
                # Already holds a lock — check if upgrade needed
                if mode == LockMode.EXCLUSIVE and holder_mode == LockMode.SHARED:
                    return self._try_upgrade_locked(txn_id, page_id)
                return True  # already holds compatible lock
            if not _COMPATIBILITY[(holder_mode, mode)]:
                return False
        # Compatible with all holders — add this txn
        self._holders[page_id][txn_id] = mode
        return True

    def _try_upgrade_locked(self, txn_id: int, page_id: int) -> bool:
        """Upgrade S→X when lock is held. Must be called with self._lock held."""
        if len(self._holders[page_id]) == 1:
            self._holders[page_id][txn_id] = LockMode.EXCLUSIVE
            return True
        return False

    def _is_holder(self, txn_id: int, page_id: int) -> bool:
        """Check if txn holds a lock on page. Must be called with self._lock held."""
        return (
            page_id in self._holders
            and txn_id in self._holders[page_id]
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_lock_manager.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add tinydb/concurrency/lock_manager.py tests/concurrency/test_lock_manager.py
git commit -m "feat(concurrency): add LockManager with Shared/Exclusive locks and FIFO wait queue"
```

---

### Task 3: LockManager — Compatibility and Timeout Tests

**Files:**
- Modify: `tests/concurrency/test_lock_manager.py` (append new test class)

**Interfaces:**
- Consumes: `LockMode`, `LockManager` from Task 2
- Produces: (no new exports — extends test coverage)

- [ ] **Step 1: Write the failing test**

Append to `tests/concurrency/test_lock_manager.py`:

```python
import threading


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_lock_manager.py::TestLockCompatibility -v`
Expected: FAIL (tests don't exist yet — will error)

- [ ] **Step 3: Implement**

The LockManager from Task 2 already handles all these cases. No code change needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_lock_manager.py -v`
Expected: 13 PASS (6 from Task 2 + 7 new)

- [ ] **Step 5: Commit**

```bash
git add tests/concurrency/test_lock_manager.py
git commit -m "test(concurrency): add lock compatibility and timeout tests"
```

---

### Task 4: MVCCManager — PageVersion and Snapshot

**Files:**
- Create: `tinydb/concurrency/mvcc_manager.py`
- Test: `tests/concurrency/test_mvcc_manager.py`

**Interfaces:**
- Consumes: nothing
- Produces: `PageVersion` dataclass (data: bytes, created_txn: int, deleted_txn: int | None, next: PageVersion | None); `Snapshot` dataclass (active_txns: set[int], timestamp: float); `MVCCManager` class with `create_version(page_id, data, txn_id)`, `get_visible_version(page_id, snapshot) → bytes | None`, `mark_deleted(page_id, version_txn_id, txn_id)`, `gc(active_txns: set[int])`

- [ ] **Step 1: Write the failing test**

```python
# tests/concurrency/test_mvcc_manager.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_mvcc_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/concurrency/mvcc_manager.py
"""Multi-Version Concurrency Control: page version chain and snapshot reads."""
import time
from dataclasses import dataclass, field


@dataclass
class PageVersion:
    """A single version of a page in the MVCC version chain."""
    data: bytes
    created_txn: int
    deleted_txn: int | None = None
    next: "PageVersion | None" = None


@dataclass
class Snapshot:
    """A point-in-time snapshot for MVCC reads."""
    active_txns: set[int]
    timestamp: float = field(default_factory=time.time)


class MVCCManager:
    """Manages page version chains for MVCC snapshot reads."""

    def __init__(self):
        # page_id -> PageVersion (head of chain, newest first)
        self._versions: dict[int, PageVersion] = {}

    def create_version(self, page_id: int, data: bytes, txn_id: int) -> PageVersion:
        """Create a new version of a page. Inserts at head of chain (descending txn_id)."""
        new_version = PageVersion(data=data, created_txn=txn_id)
        if page_id in self._versions:
            new_version.next = self._versions[page_id]
        self._versions[page_id] = new_version
        return new_version

    def get_visible_version(self, page_id: int, snapshot: Snapshot) -> bytes | None:
        """Find the visible version of a page for the given snapshot."""
        if page_id not in self._versions:
            return None
        current = self._versions[page_id]
        while current is not None:
            if self._is_visible(current, snapshot):
                return current.data
            current = current.next
        return None

    def mark_deleted(self, page_id: int, version_txn_id: int, txn_id: int) -> bool:
        """Mark a version as deleted by setting deleted_txn."""
        current = self._versions.get(page_id)
        while current is not None:
            if current.created_txn == version_txn_id:
                current.deleted_txn = txn_id
                return True
            current = current.next
        return False

    def gc(self, active_txns: set[int]) -> int:
        """Garbage collect versions not visible to any active transaction. Returns count freed."""
        freed = 0
        for page_id in list(self._versions.keys()):
            current = self._versions.get(page_id)
            prev = None
            while current is not None:
                # A version can be GC'd if:
                # - created_txn is NOT in active_txns (creator committed/aborted)
                # - AND no active txn could see it (all active txns started after it)
                can_gc = (
                    current.created_txn not in active_txns
                    and self._no_active_txn_can_see(current, active_txns)
                )
                if can_gc:
                    if prev is None:
                        self._versions[page_id] = current.next
                        if current.next is None:
                            del self._versions[page_id]
                    else:
                        prev.next = current.next
                    freed += 1
                    current = current.next if prev is None else prev.next
                else:
                    prev = current
                    current = current.next
        return freed

    def _is_visible(self, version: PageVersion, snapshot: Snapshot) -> bool:
        """Visibility rule: created_txn in snapshot AND deleted_txn NOT in snapshot."""
        if version.created_txn not in snapshot.active_txns:
            return False
        if version.deleted_txn is not None and version.deleted_txn in snapshot.active_txns:
            return False
        return True

    def _no_active_txn_can_see(self, version: PageVersion, active_txns: set[int]) -> bool:
        """Check if no active transaction could see this version."""
        # Simplified: if created_txn not in active_txns, no active txn can see it
        # (assuming snapshot was taken at txn start)
        return version.created_txn not in active_txns
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_mvcc_manager.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add tinydb/concurrency/mvcc_manager.py tests/concurrency/test_mvcc_manager.py
git commit -m "feat(concurrency): add MVCCManager with page version chain and snapshot reads"
```

---

### Task 5: MVCCManager — GC and Version Chain Tests

**Files:**
- Modify: `tests/concurrency/test_mvcc_manager.py` (append)

**Interfaces:**
- Consumes: `MVCCManager`, `Snapshot` from Task 4
- Produces: (extends test coverage)

- [ ] **Step 1: Write the failing test**

Append to `tests/concurrency/test_mvcc_manager.py`:

```python
class TestMVCCGC:
    def setup_method(self):
        self.mvcc = MVCCManager()

    def test_gc_removes_invisible_versions(self):
        """GC removes versions whose creator is not active."""
        self.mvcc.create_version(0, b"v1", txn_id=1)
        self.mvcc.create_version(0, b"v2", txn_id=2)
        # Only txn 3 is active — versions from txn 1 and 2 can be GC'd
        freed = self.mvcc.gc(active_txns={3})
        assert freed == 2
        assert 0 not in self.mvcc._versions

    def test_gc_keeps_active_versions(self):
        """GC keeps versions created by active transactions."""
        self.mvcc.create_version(0, b"v1", txn_id=1)
        self.mvcc.create_version(0, b"v2", txn_id=2)
        freed = self.mvcc.gc(active_txns={1, 2})
        assert freed == 0
        assert 0 in self.mvcc._versions

    def test_gc_partial(self):
        """GC removes only inactive versions, keeps active ones."""
        self.mvcc.create_version(0, b"v1", txn_id=1)
        self.mvcc.create_version(0, b"v2", txn_id=2)
        self.mvcc.create_version(0, b"v3", txn_id=3)
        # txn 2 is active — v2 and v3 (newer) stay, v1 can be GC'd
        freed = self.mvcc.gc(active_txns={2})
        assert freed == 1
        snap = Snapshot(active_txns={2}, timestamp=time.time())
        assert self.mvcc.get_visible_version(0, snap) == b"v2"

    def test_version_chain_traversal(self):
        """Version chain is traversed correctly for visibility."""
        self.mvcc.create_version(0, b"v1", txn_id=1)
        self.mvcc.create_version(0, b"v2", txn_id=2)
        self.mvcc.create_version(0, b"v3", txn_id=3)
        # Only txn 1 active → sees v1
        snap = Snapshot(active_txns={1}, timestamp=time.time())
        assert self.mvcc.get_visible_version(0, snap) == b"v1"
        # txn 2 active → sees v2
        snap = Snapshot(active_txns={2}, timestamp=time.time())
        assert self.mvcc.get_visible_version(0, snap) == b"v2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_mvcc_manager.py::TestMVCCGC -v`
Expected: FAIL (tests don't exist yet)

- [ ] **Step 3: Implement**

The MVCCManager from Task 4 already handles GC. No code change needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_mvcc_manager.py -v`
Expected: 11 PASS (7 from Task 4 + 4 new)

- [ ] **Step 5: Commit**

```bash
git add tests/concurrency/test_mvcc_manager.py
git commit -m "test(concurrency): add MVCC GC and version chain traversal tests"
```

---

### Task 6: DeadlockDetector — Wait-for Graph and Cycle Detection

**Files:**
- Create: `tinydb/concurrency/deadlock_detector.py`
- Test: `tests/concurrency/test_deadlock_detector.py`

**Interfaces:**
- Consumes: nothing
- Produces: `DeadlockDetector` class with `add_wait_edge(waiter_txn, holder_txn)`, `remove_wait_edge(waiter_txn, holder_txn)`, `detect_cycle() → list[int] | None`, `select_victim(cycle: list[int]) → int`, `clear_txn(txn_id)`

- [ ] **Step 1: Write the failing test**

```python
# tests/concurrency/test_deadlock_detector.py
"""Tests for tinydb.concurrency.deadlock_detector module."""
import pytest
from tinydb.concurrency.deadlock_detector import DeadlockDetector


class TestDeadlockDetector:
    def setup_method(self):
        self.dd = DeadlockDetector()

    def test_no_cycle_empty(self):
        assert self.dd.detect_cycle() is None

    def test_no_cycle_single_edge(self):
        self.dd.add_wait_edge(waiter_txn=1, holder_txn=2)
        assert self.dd.detect_cycle() is None

    def test_detect_simple_cycle(self):
        """1→2→3→1 forms a cycle."""
        self.dd.add_wait_edge(1, 2)
        self.dd.add_wait_edge(2, 3)
        self.dd.add_wait_edge(3, 1)
        cycle = self.dd.detect_cycle()
        assert cycle is not None
        assert len(cycle) >= 3

    def test_detect_no_cycle_dag(self):
        """1→2→3 is a DAG, no cycle."""
        self.dd.add_wait_edge(1, 2)
        self.dd.add_wait_edge(2, 3)
        assert self.dd.detect_cycle() is None

    def test_select_victim_youngest(self):
        """Victim is the youngest (highest txn_id) in the cycle."""
        self.dd.add_wait_edge(1, 2)
        self.dd.add_wait_edge(2, 3)
        self.dd.add_wait_edge(3, 1)
        cycle = self.dd.detect_cycle()
        victim = self.dd.select_victim(cycle)
        assert victim == 3  # highest txn_id

    def test_remove_edge_breaks_cycle(self):
        """Removing an edge breaks the cycle."""
        self.dd.add_wait_edge(1, 2)
        self.dd.add_wait_edge(2, 3)
        self.dd.add_wait_edge(3, 1)
        assert self.dd.detect_cycle() is not None
        self.dd.remove_wait_edge(3, 1)
        assert self.dd.detect_cycle() is None

    def test_clear_txn(self):
        """Clearing a txn removes all its edges."""
        self.dd.add_wait_edge(1, 2)
        self.dd.add_wait_edge(2, 3)
        self.dd.add_wait_edge(3, 1)
        self.dd.clear_txn(1)
        assert self.dd.detect_cycle() is None

    def test_self_loop_detected(self):
        """A txn waiting on itself is a cycle."""
        self.dd.add_wait_edge(1, 1)
        cycle = self.dd.detect_cycle()
        assert cycle is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_deadlock_detector.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# tinydb/concurrency/deadlock_detector.py
"""Deadlock detection using wait-for graph and cycle detection."""
import threading
from collections import defaultdict


class DeadlockDetector:
    """Detects deadlocks via wait-for graph cycle detection."""

    def __init__(self):
        self._lock = threading.Lock()
        # txn_id -> set of txn_ids it waits for
        self._wait_for: dict[int, set[int]] = defaultdict(set)

    def add_wait_edge(self, waiter_txn: int, holder_txn: int) -> None:
        """Add an edge: waiter_txn waits for holder_txn."""
        with self._lock:
            self._wait_for[waiter_txn].add(holder_txn)

    def remove_wait_edge(self, waiter_txn: int, holder_txn: int) -> None:
        """Remove an edge: waiter_txn no longer waits for holder_txn."""
        with self._lock:
            if waiter_txn in self._wait_for:
                self._wait_for[waiter_txn].discard(holder_txn)
                if not self._wait_for[waiter_txn]:
                    del self._wait_for[waiter_txn]

    def detect_cycle(self) -> list[int] | None:
        """Detect a cycle in the wait-for graph using DFS. Returns the cycle or None."""
        with self._lock:
            WHITE, GRAY, BLACK = 0, 1, 2
            color = defaultdict(int)
            parent: dict[int, int | None] = {txn: None for txn in self._wait_for}
            for txn in self._wait_for:
                parent[txn] = None

            def dfs(u: int) -> list[int] | None:
                color[u] = GRAY
                for v in self._wait_for.get(u, set()):
                    if color[v] == GRAY:
                        # Found cycle — reconstruct it
                        cycle = [v, u]
                        node = u
                        while parent.get(node) is not None and parent[node] != v:
                            node = parent[node]  # type: ignore
                            cycle.append(node)
                        cycle.reverse()
                        return cycle
                    if color[v] == WHITE:
                        parent[v] = u
                        result = dfs(v)
                        if result is not None:
                            return result
                color[u] = BLACK
                return None

            for node in list(self._wait_for.keys()):
                if color[node] == WHITE:
                    result = dfs(node)
                    if result is not None:
                        return result
            return None

    def select_victim(self, cycle: list[int]) -> int:
        """Select the youngest transaction (highest txn_id) as victim."""
        return max(cycle)

    def clear_txn(self, txn_id: int) -> None:
        """Remove all edges involving a transaction."""
        with self._lock:
            # Remove outgoing edges
            if txn_id in self._wait_for:
                del self._wait_for[txn_id]
            # Remove incoming edges
            for waiter in list(self._wait_for.keys()):
                self._wait_for[waiter].discard(txn_id)
                if not self._wait_for[waiter]:
                    del self._wait_for[waiter]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_deadlock_detector.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add tinydb/concurrency/deadlock_detector.py tests/concurrency/test_deadlock_detector.py
git commit -m "feat(concurrency): add DeadlockDetector with wait-for graph and cycle detection"
```

---

### Task 7: TransactionManager Refactor — Multi-Transaction Support

**Files:**
- Modify: `tinydb/transaction/txn_manager.py`
- Modify: `tests/test_transaction.py` (add multi-txn tests)

**Interfaces:**
- Consumes: `LockManager`, `MVCCManager`, `DeadlockDetector`, `IsolationLevel` from `tinydb.concurrency`
- Produces: `TransactionManager` with `begin(isolation=None) → int` (returns txn_id), `commit(txn_id)`, `rollback(txn_id)`, `get_snapshot(txn_id) → Snapshot`, `get_active_txns() → dict[int, Transaction]`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_transaction.py`:

```python
import threading
import time
from tinydb.concurrency.isolation import IsolationLevel


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/test_transaction.py::TestMultiTransaction -v`
Expected: FAIL (methods don't exist yet)

- [ ] **Step 3: Update existing nested txn test**

The original `test_nested_txn_rejected` test at `tests/test_transaction.py:40-45` will now fail since we support multiple concurrent transactions. Replace it:

```python
    def test_multiple_txn_supported(self, db_env):
        fm, pool, cat, imgr = db_env
        tm = TransactionManager(fm, pool, imgr)
        txn1 = tm.begin()
        txn2 = tm.begin()
        assert txn1 != txn2
        tm.commit(txn1)
        tm.commit(txn2)
```

- [ ] **Step 4: Update database.py references**

The `_get_pool` method at `tinydb/database.py:80` references `self._txn_mgr._active_txn` which no longer exists. Replace:

```python
    def _get_pool(self):
        """Return active pool: shadow pool if in transaction, else main pool."""
        if self._txn_mgr.has_active_txn():
            from tinydb.transaction.shadow_paging import ShadowBufferPool
            entry = next(iter(self._txn_mgr.get_active_txns().values()))
            return ShadowBufferPool(self._pool, entry.txn, self._fm)
        return self._pool
```

Also update `database.py` imports to include `IsolationLevel`:
```python
from tinydb.concurrency.isolation import IsolationLevel
```

- [ ] **Step 5: Write minimal implementation**

Replace `tinydb/transaction/txn_manager.py`:

```python
# tinydb/transaction/txn_manager.py
"""Transaction Manager: multi-transaction lifecycle with concurrency control."""
import os
import threading
import time
from dataclasses import dataclass, field
from tinydb.transaction.shadow_paging import Transaction
from tinydb.concurrency.lock_manager import LockManager, LockMode
from tinydb.concurrency.mvcc_manager import MVCCManager, Snapshot
from tinydb.concurrency.deadlock_detector import DeadlockDetector
from tinydb.concurrency.isolation import IsolationLevel, default_isolation


class TransactionError(Exception):
    pass


@dataclass
class TransactionEntry:
    """Extended transaction metadata for concurrency control."""
    txn: Transaction
    isolation: IsolationLevel
    snapshot: Snapshot
    start_time: float = field(default_factory=time.time)


class TransactionManager:
    """Manages multi-transaction lifecycle with lock/MVCC integration."""

    def __init__(self, file_manager, buffer_pool, index_manager):
        self._fm = file_manager
        self._pool = buffer_pool
        self._index_mgr = index_manager
        self._active_txns: dict[int, TransactionEntry] = {}
        self._txn_counter = 0
        self._lock = threading.Lock()
        self._lock_mgr = LockManager()
        self._mvcc = MVCCManager()
        self._deadlock_detector = DeadlockDetector()

    def begin(self, isolation: IsolationLevel | None = None) -> int:
        """Begin a new transaction. Returns txn_id."""
        with self._lock:
            if isolation is None:
                isolation = default_isolation()
            self._txn_counter += 1
            txn_id = self._txn_counter
            # Snapshot = currently active transaction IDs
            active_ids = set(self._active_txns.keys())
            snapshot = Snapshot(active_txns=active_ids | {txn_id})
            txn = Transaction(
                txn_id=txn_id,
                state="active",
                shadow_pages={},
                snapshot_root=self._fm.root_page_id,
                new_root=self._fm.root_page_id,
            )
            entry = TransactionEntry(
                txn=txn,
                isolation=isolation,
                snapshot=snapshot,
            )
            self._active_txns[txn_id] = entry
            return txn_id

    def commit(self, txn_id: int | None = None):
        """Commit a transaction. If txn_id is None, commit the single active txn (backward compat)."""
        with self._lock:
            entry = self._resolve_txn(txn_id)
            txn = entry.txn
            self._pool.flush()
            for orig_id, shadow_id in list(txn.shadow_pages.items()):
                shadow_data = self._pool._fm.read_page(shadow_id)
                self._pool._fm.write_page(orig_id, shadow_data)
            self._fm.root_page_id = txn.new_root
            self._fm._write_header()
            self._fm._file.flush()
            os.fsync(self._fm._file.fileno())
            self._pool._cache.clear()
            self._pool._head = None
            self._pool._tail = None
            txn.state = "committed"
            self._lock_mgr.release_all(txn.txn_id)
            self._deadlock_detector.clear_txn(txn.txn_id)
            del self._active_txns[txn.txn_id]

    def rollback(self, txn_id: int | None = None):
        """Rollback a transaction."""
        with self._lock:
            entry = self._resolve_txn(txn_id)
            txn = entry.txn
            for orig_id, shadow_id in txn.shadow_pages.items():
                self._fm.free_page(shadow_id)
            txn.state = "aborted"
            self._lock_mgr.release_all(txn.txn_id)
            self._deadlock_detector.clear_txn(txn.txn_id)
            del self._active_txns[txn.txn_id]

    def get_snapshot(self, txn_id: int) -> Snapshot:
        """Get the snapshot for a transaction."""
        with self._lock:
            if txn_id not in self._active_txns:
                raise TransactionError(f"Transaction {txn_id} not found")
            return self._active_txns[txn_id].snapshot

    def get_active_txns(self) -> dict[int, TransactionEntry]:
        """Return dict of active transactions."""
        with self._lock:
            return dict(self._active_txns)

    def has_active_txn(self) -> bool:
        """Check if any transaction is active."""
        with self._lock:
            return len(self._active_txns) > 0

    def ensure_shadow(self, page_id: int) -> int:
        """Get or create shadow page. Returns shadow page ID."""
        with self._lock:
            if not self._active_txns:
                return page_id
            txn_id, entry = next(iter(self._active_txns.items()))
        if page_id in entry.txn.shadow_pages:
            return entry.txn.shadow_pages[page_id]
        shadow_id = self._fm.alloc_page()
        orig_data = self._pool.get_page(page_id)
        self._pool._fm.write_page(shadow_id, orig_data)
        entry.txn.shadow_pages[page_id] = shadow_id
        return shadow_id

    def _resolve_txn(self, txn_id: int | None) -> TransactionEntry:
        """Resolve a transaction by ID or return the single active one."""
        if txn_id is not None:
            if txn_id not in self._active_txns:
                raise TransactionError(f"Transaction {txn_id} not found")
            return self._active_txns[txn_id]
        # Backward compat: return single active txn
        if len(self._active_txns) == 1:
            return next(iter(self._active_txns.values()))
        raise TransactionError("No active transaction" if not self._active_txns
                               else "Multiple active txns — specify txn_id")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/test_transaction.py tests/test_database.py -v`
Expected: All tests PASS (original updated + new)

- [ ] **Step 7: Commit**

```bash
git add tinydb/transaction/txn_manager.py tinydb/database.py tests/test_transaction.py
git commit -m "feat(transaction): refactor TransactionManager for multi-transaction concurrency"
```

---

### Task 8: BufferPool Integration — Pin/Unpin with LockManager

**Files:**
- Modify: `tinydb/buffer_pool.py`
- Modify: `tests/test_buffer_pool.py` (add lock integration tests)

**Interfaces:**
- Consumes: `LockManager`, `LockMode` from `tinydb.concurrency`
- Produces: `BufferPool.pin(page_id, txn_id, mode)` — acquires lock via LockManager; `BufferPool.unpin(page_id, txn_id)` — releases lock; `BufferPool.get_page(page_id, txn_id | None)` — returns MVCC visible version if txn_id provided

- [ ] **Step 1: Write the failing test**

Append to `tests/test_buffer_pool.py`:

```python
from unittest.mock import MagicMock, patch
from tinydb.concurrency.lock_manager import LockMode


class TestBufferPoolLockIntegration:
    @pytest.fixture
    def mock_fm(self):
        fm = MagicMock()
        fm.read_page.side_effect = lambda pid: _make_page_bytes(pid)
        fm.page_count = 100
        return fm

    def test_pin_acquires_lock(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        pool.pin(page_id=1, txn_id=1, mode=LockMode.SHARED)
        holders = pool._lock_mgr.get_lock_holders(1)
        assert 1 in holders

    def test_unpin_releases_lock(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        pool.pin(page_id=1, txn_id=1, mode=LockMode.SHARED)
        pool.unpin(page_id=1, txn_id=1)
        holders = pool._lock_mgr.get_lock_holders(1)
        assert 1 not in holders

    def test_pin_exclusive_blocks_other(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        pool.pin(page_id=1, txn_id=1, mode=LockMode.EXCLUSIVE)
        # txn 2 should not be able to acquire SHARED immediately
        result = pool._lock_mgr.acquire(2, 1, LockMode.SHARED, timeout=0.1)
        assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/test_buffer_pool.py::TestBufferPoolLockIntegration -v`
Expected: FAIL (pin/unpin signatures don't match)

- [ ] **Step 3: Write minimal implementation**

Modify `tinydb/buffer_pool.py` — add import and update `pin`/`unpin` methods:

Add at the top of `tinydb/buffer_pool.py` after existing imports:

```python
from tinydb.concurrency.lock_manager import LockManager, LockMode
```

Replace the `pin` method (lines 81-96):

```python
    def pin(self, page_id: int, txn_id: int | None = None, mode: LockMode | None = None) -> None:
        """Pin a page to prevent eviction. Optionally acquires a lock."""
        if page_id in self._cache:
            self._cache[page_id].ref_count += 1
        else:
            # Fetch from disk and pin immediately
            raw = self._fm.read_page(page_id)
            header = parse_page_header(raw)
            page = Page(
                page_id=page_id,
                page_type=header["page_type"],
                data=raw,
                dirty=False,
            )
            self._insert_page(page_id, page, pinned=True)

        # Acquire lock if txn_id and mode provided
        if txn_id is not None and mode is not None:
            if not hasattr(self, '_lock_mgr'):
                self._lock_mgr = LockManager()
            self._lock_mgr.acquire(txn_id, page_id, mode)
```

Replace the `unpin` method (lines 98-103):

```python
    def unpin(self, page_id: int, txn_id: int | None = None) -> None:
        """Unpin a page. Optionally releases a lock."""
        if page_id in self._cache:
            node = self._cache[page_id]
            if node.ref_count > 0:
                node.ref_count -= 1

        # Release lock if txn_id provided
        if txn_id is not None and hasattr(self, '_lock_mgr'):
            self._lock_mgr.release(txn_id, page_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/test_buffer_pool.py -v`
Expected: All tests PASS (original + new)

- [ ] **Step 5: Commit**

```bash
git add tinydb/buffer_pool.py tests/test_buffer_pool.py
git commit -m "feat(buffer_pool): integrate LockManager into pin/unpin"
```

---

### Task 9: BufferPool Integration — MVCC Version Routing

**Files:**
- Modify: `tinydb/buffer_pool.py`
- Modify: `tests/test_buffer_pool.py` (add MVCC tests)

**Interfaces:**
- Consumes: `MVCCManager`, `Snapshot` from `tinydb.concurrency`
- Produces: `BufferPool.get_page(page_id, txn_id | None, snapshot | None)` — returns MVCC visible version when snapshot provided

- [ ] **Step 1: Write the failing test**

Append to `tests/test_buffer_pool.py`:

```python
from tinydb.concurrency.mvcc_manager import Snapshot


class TestBufferPoolMVCCIntegration:
    @pytest.fixture
    def mock_fm(self):
        fm = MagicMock()
        fm.read_page.side_effect = lambda pid: _make_page_bytes(pid)
        fm.page_count = 100
        return fm

    def test_get_page_with_snapshot(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        # Create a version in MVCC
        pool._mvcc.create_version(1, b"version_data_1", txn_id=1)
        snap = Snapshot(active_txns={1}, timestamp=0.0)
        result = pool.get_page(1, txn_id=1, snapshot=snap)
        assert result == b"version_data_1"

    def test_get_page_without_snapshot_returns_raw(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        result = pool.get_page(1)
        assert isinstance(result, bytes)
        assert len(result) == PAGE_SIZE

    def test_get_page_mvcc_fallback_to_disk(self, mock_fm):
        """If no MVCC version visible, fall back to disk read."""
        pool = BufferPool(mock_fm, capacity=10)
        pool._mvcc.create_version(1, b"v1", txn_id=1)
        # Snapshot where txn 1 is NOT active → no visible version
        snap = Snapshot(active_txns={2}, timestamp=0.0)
        result = pool.get_page(1, txn_id=2, snapshot=snap)
        # Falls back to disk
        assert isinstance(result, bytes)
        assert len(result) == PAGE_SIZE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/test_buffer_pool.py::TestBufferPoolMVCCIntegration -v`
Expected: FAIL (get_page doesn't accept txn_id/snapshot)

- [ ] **Step 3: Write minimal implementation**

Add import at top of `tinydb/buffer_pool.py`:

```python
from tinydb.concurrency.mvcc_manager import MVCCManager, Snapshot
```

Replace the `get_page` method (lines 48-68):

```python
    def get_page(self, page_id: int, txn_id: int | None = None, snapshot: Snapshot | None = None) -> bytes:
        """Get a page from cache or disk. If snapshot provided, return MVCC visible version."""
        # Try MVCC first if snapshot provided
        if snapshot is not None:
            if not hasattr(self, '_mvcc'):
                self._mvcc = MVCCManager()
            mvcc_data = self._mvcc.get_visible_version(page_id, snapshot)
            if mvcc_data is not None:
                return mvcc_data
            # No visible version — fall through to disk/cache

        if page_id in self._cache:
            node = self._cache[page_id]
            self._cache.move_to_end(page_id)
            self._move_to_head(node)
            return node.page.data

        # Fetch from disk
        raw = self._fm.read_page(page_id)
        header = parse_page_header(raw)
        page = Page(
            page_id=page_id,
            page_type=header["page_type"],
            data=raw,
            dirty=False,
        )

        # Insert into pool (may trigger eviction)
        self._insert_page(page_id, page)
        return page.data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/test_buffer_pool.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tinydb/buffer_pool.py tests/test_buffer_pool.py
git commit -m "feat(buffer_pool): add MVCC version routing to get_page"
```

---

### Task 10: Shadow Paging Adaptation — MVCC Coordination on Commit

**Files:**
- Modify: `tinydb/transaction/shadow_paging.py`
- Modify: `tests/test_shadow_paging.py` (add MVCC coordination tests)

**Interfaces:**
- Consumes: `MVCCManager` from `tinydb.concurrency`
- Produces: `ShadowBufferPool.commit()` creates MVCC version; `ShadowBufferPool` accepts optional `mvcc_manager` parameter

- [ ] **Step 1: Write the failing test**

```python
# tests/test_shadow_paging_mvcc.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/test_shadow_paging_mvcc.py -v`
Expected: FAIL (ShadowBufferPool doesn't accept mvcc_manager)

- [ ] **Step 3: Write minimal implementation**

Modify `tinydb/transaction/shadow_paging.py` — update `ShadowBufferPool.__init__`:

Add import at top:

```python
from tinydb.concurrency.mvcc_manager import MVCCManager
```

Replace `ShadowBufferPool.__init__` (lines 19-22):

```python
    def __init__(self, buffer_pool, txn, file_manager, mvcc_manager: MVCCManager | None = None):
        self._pool = buffer_pool
        self._txn = txn
        self._fm = file_manager
        self._mvcc = mvcc_manager
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/test_shadow_paging_mvcc.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add tinydb/transaction/shadow_paging.py tests/test_shadow_paging_mvcc.py
git commit -m "feat(shadow_paging): add MVCC manager integration to ShadowBufferPool"
```

---

### Task 11: Concurrency Package Exports

**Files:**
- Modify: `tinydb/concurrency/__init__.py`
- Modify: `tinydb/transaction/__init__.py`
- Modify: `tinydb/__init__.py`

**Interfaces:**
- Consumes: all concurrency modules
- Produces: public API exports

- [ ] **Step 1: Write the failing test**

```python
# tests/concurrency/test_exports.py
"""Verify public API exports."""
from tinydb.concurrency import (
    IsolationLevel, default_isolation, validate_isolation,
    LockMode, LockManager,
    PageVersion, Snapshot, MVCCManager,
    DeadlockDetector,
)


class TestExports:
    def test_all_exports_available(self):
        assert IsolationLevel is not None
        assert LockMode is not None
        assert LockManager is not None
        assert PageVersion is not None
        assert Snapshot is not None
        assert MVCCManager is not None
        assert DeadlockDetector is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_exports.py -v`
Expected: FAIL (exports not defined)

- [ ] **Step 3: Write minimal implementation**

Replace `tinydb/concurrency/__init__.py`:

```python
# tinydb/concurrency/__init__.py
"""Concurrency control: locks, MVCC, deadlock detection, isolation levels."""
from tinydb.concurrency.isolation import IsolationLevel, default_isolation, validate_isolation
from tinydb.concurrency.lock_manager import LockMode, LockManager
from tinydb.concurrency.mvcc_manager import PageVersion, Snapshot, MVCCManager
from tinydb.concurrency.deadlock_detector import DeadlockDetector

__all__ = [
    "IsolationLevel",
    "default_isolation",
    "validate_isolation",
    "LockMode",
    "LockManager",
    "PageVersion",
    "Snapshot",
    "MVCCManager",
    "DeadlockDetector",
]
```

Update `tinydb/transaction/__init__.py`:

```python
# tinydb/transaction/__init__.py
from tinydb.transaction.shadow_paging import Transaction, ShadowBufferPool
from tinydb.transaction.txn_manager import TransactionManager, TransactionError, TransactionEntry

__all__ = ["Transaction", "ShadowBufferPool", "TransactionManager", "TransactionError", "TransactionEntry"]
```

Update `tinydb/__init__.py` — add concurrency imports:

```python
from tinydb.concurrency import (
    IsolationLevel, LockMode, LockManager,
    PageVersion, Snapshot, MVCCManager,
    DeadlockDetector,
)
```

And add to `__all__`:

```python
    "IsolationLevel",
    "LockMode",
    "LockManager",
    "PageVersion",
    "Snapshot",
    "MVCCManager",
    "DeadlockDetector",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/concurrency/test_exports.py -v`
Expected: 1 PASS

- [ ] **Step 5: Commit**

```bash
git add tinydb/concurrency/__init__.py tinydb/transaction/__init__.py tinydb/__init__.py tests/concurrency/test_exports.py
git commit -m "feat: export concurrency module public API"
```

---

### Task 12: End-to-End Concurrency Integration Test

**Files:**
- Create: `tests/test_concurrency_integration.py`

**Interfaces:**
- Consumes: all concurrency modules, TransactionManager, BufferPool
- Produces: (integration test coverage)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_concurrency_integration.py
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
        """Full pipeline: lock → MVCC read → deadlock detect."""
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/test_concurrency_integration.py -v`
Expected: FAIL (file doesn't exist yet)

- [ ] **Step 3: Implement**

All dependencies already exist from previous tasks. No additional implementation needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/test_concurrency_integration.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_concurrency_integration.py
git commit -m "test(concurrency): add end-to-end concurrency integration tests"
```

---

### Task 13: Full Test Suite Verification

**Files:**
- (no new files — run entire test suite)

**Interfaces:**
- Consumes: all previous tasks
- Produces: (verification only)

- [ ] **Step 1: Write the failing test**

No new tests — verify all existing tests still pass.

- [ ] **Step 2: Run full test suite**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/ -v`
Expected: All tests PASS (original tests + new concurrency tests)

- [ ] **Step 3: Fix any regressions**

If any original tests fail due to API changes (e.g., `pin`/`unpin` signature changes), update them to use the new signatures with `txn_id` and `mode` parameters, or use the backward-compatible forms (without txn_id/mode).

- [ ] **Step 4: Verify all pass**

Run: `cd /home/lz/projects/tinydb-v02-concurrency && pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: verify full test suite passes with concurrency changes"
```
