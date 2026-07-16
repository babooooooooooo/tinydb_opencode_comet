"""Page-level lock manager with Shared/Exclusive locks and FIFO wait queue."""
import threading
from collections import deque
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
        self._wait_queue: dict[int, deque] = {}

    def acquire(self, txn_id: int, page_id: int, mode: LockMode, timeout: float = 5.0) -> bool:
        """Acquire a lock on a page. Returns True if acquired, False if timed out."""
        with self._lock:
            if self._try_acquire(txn_id, page_id, mode):
                return True
            # Need to wait
            if page_id not in self._wait_queue:
                self._wait_queue[page_id] = deque()
            cond = threading.Condition(self._lock)
            entry = (txn_id, mode, cond)
            self._wait_queue[page_id].append(entry)

        # Wait outside the main lock using the condition variable
        with cond:
            result = cond.wait_for(
                lambda: self._try_acquire(txn_id, page_id, mode),
                timeout=timeout,
            )
        if result:
            return True
        # Timeout — remove from wait queue
        with self._lock:
            if page_id in self._wait_queue:
                self._wait_queue[page_id] = deque(
                    e for e in self._wait_queue[page_id] if e[0] != txn_id
                )
        return False

    def release(self, txn_id: int, page_id: int) -> None:
        """Release a lock held by a transaction on a page."""
        with self._lock:
            if page_id in self._holders and txn_id in self._holders[page_id]:
                del self._holders[page_id][txn_id]
                if not self._holders[page_id]:
                    del self._holders[page_id]
            # Remove from wait queue
            if page_id in self._wait_queue:
                self._wait_queue[page_id] = deque(
                    e for e in self._wait_queue[page_id] if e[0] != txn_id
                )
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
