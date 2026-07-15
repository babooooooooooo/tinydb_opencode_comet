# tinydb/transaction/txn_manager.py
"""Transaction Manager: lifecycle and auto-rollback."""
import os
from tinydb.transaction.shadow_paging import Transaction


class TransactionError(Exception):
    pass


class TransactionManager:
    """Manages transaction lifecycle."""

    def __init__(self, file_manager, buffer_pool, index_manager):
        self._fm = file_manager
        self._pool = buffer_pool
        self._index_mgr = index_manager
        self._active_txn: Transaction | None = None
        self._txn_counter = 0

    def begin(self) -> Transaction:
        if self._active_txn is not None:
            raise TransactionError("Nested transactions not supported")
        self._txn_counter += 1
        txn = Transaction(
            txn_id=self._txn_counter,
            state="active",
            shadow_pages={},
            snapshot_root=self._fm.root_page_id,
            new_root=self._fm.root_page_id,
        )
        self._active_txn = txn
        return txn

    def commit(self):
        if self._active_txn is None:
            raise TransactionError("No active transaction")
        self._pool.flush()
        for orig_id, shadow_id in list(self._active_txn.shadow_pages.items()):
            shadow_data = self._pool._fm.read_page(shadow_id)
            self._pool._fm.write_page(orig_id, shadow_data)
        self._fm.root_page_id = self._active_txn.new_root
        self._fm._write_header()
        self._fm._file.flush()
        os.fsync(self._fm._file.fileno())
        self._pool._cache.clear()
        self._pool._head = None
        self._pool._tail = None
        self._active_txn.state = "committed"
        self._active_txn = None

    def rollback(self):
        if self._active_txn is None:
            raise TransactionError("No active transaction")
        for orig_id, shadow_id in self._active_txn.shadow_pages.items():
            self._fm.free_page(shadow_id)
        self._active_txn.state = "aborted"
        self._active_txn = None

    def ensure_shadow(self, page_id: int) -> int:
        """Get or create shadow page. Returns shadow page ID."""
        if self._active_txn is None:
            return page_id
        if page_id in self._active_txn.shadow_pages:
            return self._active_txn.shadow_pages[page_id]
        shadow_id = self._fm.alloc_page()
        orig_data = self._pool.get_page(page_id)
        self._pool._fm.write_page(shadow_id, orig_data)
        self._active_txn.shadow_pages[page_id] = shadow_id
        return shadow_id

    def has_active_txn(self) -> bool:
        return self._active_txn is not None
