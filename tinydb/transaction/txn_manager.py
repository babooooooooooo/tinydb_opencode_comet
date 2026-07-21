# tinydb/transaction/txn_manager.py
"""Transaction Manager: multi-transaction lifecycle with concurrency control."""
import os
import threading
import time
from dataclasses import dataclass, field
from tinydb.transaction.shadow_paging import Transaction
from tinydb.concurrency.lock_manager import LockManager
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
        self._deadlock_detector = DeadlockDetector()
        self._lock_mgr = LockManager(deadlock_detector=self._deadlock_detector)
        self._mvcc = MVCCManager()

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
            txn.state = "committed"
            self._lock_mgr.release_all(txn.txn_id)
            self._deadlock_detector.clear_txn(txn.txn_id)
            active_ids = set(self._active_txns.keys()) - {txn.txn_id}
            self._mvcc.gc(active_ids)
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
            # Record MVCC version for snapshot reads
            self._mvcc.create_version(page_id, orig_data, txn_id)
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

    def get_active_context(self) -> "ExecutionContext | None":
        """Return execution context for the single active transaction, or None."""
        if len(self._active_txns) == 1:
            entry = next(iter(self._active_txns.values()))
            return ExecutionContext(
                txn_id=entry.txn.txn_id,
                isolation=entry.isolation,
                snapshot=entry.snapshot,
                lock_mgr=self._lock_mgr,
                mvcc=self._mvcc,
            )
        return None

    def release_read_locks(self, txn_id: int) -> None:
        """Release all shared locks held by a transaction (for snapshot reads)."""
        self._lock_mgr.release_all(txn_id)


@dataclass
class ExecutionContext:
    """Runtime context for SQL execution within a transaction."""
    txn_id: int
    isolation: IsolationLevel
    snapshot: Snapshot
    lock_mgr: LockManager
    mvcc: MVCCManager
