# tinydb/transaction/shadow_paging.py
"""Shadow Paging: page-level copy-on-write for transaction atomicity."""
import os
from dataclasses import dataclass


from tinydb.concurrency.mvcc_manager import MVCCManager


@dataclass
class Transaction:
    txn_id: int
    state: str
    shadow_pages: dict[int, int]
    snapshot_root: int
    new_root: int


class ShadowBufferPool:
    """BufferPool wrapper that intercepts reads/writes for CoW."""

    def __init__(self, buffer_pool, txn, file_manager, mvcc_manager: MVCCManager | None = None):
        self._pool = buffer_pool
        self._txn = txn
        self._fm = file_manager
        self._mvcc = mvcc_manager

    def get_page(self, page_id: int, txn_id: int | None = None, snapshot=None) -> bytes:
        """Read page, returning shadow version if it exists, else MVCC snapshot."""
        shadow_id = self._txn.shadow_pages.get(page_id)
        if shadow_id is not None:
            return self._pool.get_page(shadow_id)
        return self._pool.get_page(page_id, txn_id=txn_id, snapshot=snapshot)

    def pin(self, page_id: int, txn_id: int | None = None, mode=None) -> None:
        """Pin page (acquires lock on original page ID)."""
        # We pin the original page ID to lock it, even if a shadow exists
        self._pool.pin(page_id, txn_id=txn_id, mode=mode)

    def unpin(self, page_id: int, txn_id: int | None = None) -> None:
        """Unpin page (releases lock on original page ID)."""
        self._pool.unpin(page_id, txn_id=txn_id)

    def set_page_data(self, page_id: int, data: bytes) -> None:
        """Write page data, creating shadow page on first write (CoW)."""
        shadow_id = self._ensure_shadow(page_id)
        self._pool.set_page_data(shadow_id, data)
        self._pool.mark_dirty(shadow_id)

    def mark_dirty(self, page_id: int) -> None:
        """Mark page as dirty."""
        shadow_id = self._txn.shadow_pages.get(page_id, page_id)
        self._pool.mark_dirty(shadow_id)

    def flush(self) -> None:
        """Flush all dirty pages to disk."""
        self._pool.flush()

    def rollback(self) -> None:
        """Release all shadow pages."""
        for orig_id, shadow_id in self._txn.shadow_pages.items():
            self._fm.free_page(shadow_id)
        self._txn.shadow_pages.clear()
        self._txn.state = "aborted"

    def commit(self) -> None:
        """Flush shadow pages and atomically switch root pointer."""
        self._pool.flush()
        self._fm.root_page_id = self._txn.new_root
        self._fm._write_header()
        self._fm._file.flush()
        os.fsync(self._fm._file.fileno())
        self._txn.shadow_pages.clear()
        self._txn.state = "committed"

    def _ensure_shadow(self, page_id: int) -> int:
        """Get or create shadow page for CoW."""
        if page_id in self._txn.shadow_pages:
            return self._txn.shadow_pages[page_id]

        from tinydb.page import Page

        shadow_id = self._fm.alloc_page()
        orig_data = self._pool.get_page(page_id)
        self._fm.write_page(shadow_id, orig_data)
        page = Page(
            page_id=shadow_id,
            page_type=None,
            data=orig_data,
            dirty=False,
        )
        with self._pool._lock:
            self._pool._cache[shadow_id] = page
            self._pool._cache.move_to_end(shadow_id)
        self._txn.shadow_pages[page_id] = shadow_id
        return shadow_id
