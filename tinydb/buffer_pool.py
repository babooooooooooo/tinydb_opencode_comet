"""Buffer Pool with LRU eviction and pin/unpin support.

Uses OrderedDict for O(1) lookup, insertion, and LRU tracking.
move_to_end() handles LRU ordering; the first item is the eviction candidate.

NOTE: get_page() returns raw bytes (not a Page object) deliberately.
Table-level code works with mutable bytearray views for in-place edits,
so the pool exposes bytes while callers manage their own deserialization.
"""
from collections import OrderedDict

from tinydb.constants import DEFAULT_BUFFER_POOL_CAPACITY
from tinydb.exceptions import PageOutOfRangeError
from tinydb.page import Page, PageType, parse_page_header


def _get_lock_mgr(pool):
    """Lazily initialize and return the pool's LockManager."""
    from tinydb.concurrency.lock_manager import LockManager
    if not hasattr(pool, '_lock_mgr'):
        pool._lock_mgr = LockManager()
    return pool._lock_mgr


def _get_mvcc(pool):
    """Lazily initialize and return the pool's MVCCManager."""
    from tinydb.concurrency.mvcc_manager import MVCCManager
    if not hasattr(pool, '_mvcc'):
        pool._mvcc = MVCCManager()
    return pool._mvcc


class BufferPool:
    """LRU buffer pool with pin/unpin and dirty page management."""

    def __init__(self, file_manager, capacity: int = DEFAULT_BUFFER_POOL_CAPACITY):
        self._fm = file_manager
        self._capacity = capacity
        self._cache: OrderedDict[int, Page] = OrderedDict()
        self._pinned: set[int] = set()

        # Concurrency control
        from tinydb.concurrency.lock_manager import LockManager
        from tinydb.concurrency.mvcc_manager import MVCCManager
        self._lock_mgr = LockManager()
        self._mvcc = MVCCManager()

    @property
    def size(self) -> int:
        return len(self._cache)

    def get_page(self, page_id: int, txn_id: int | None = None, snapshot=None) -> bytes:
        """Get a page from cache or disk. If snapshot provided, return MVCC visible version."""
        from tinydb.concurrency.mvcc_manager import Snapshot
        # Try MVCC first if snapshot provided
        if snapshot is not None:
            mvcc = _get_mvcc(self)
            mvcc_data = mvcc.get_visible_version(page_id, snapshot)
            if mvcc_data is not None:
                return mvcc_data
            # No visible version — fall through to disk/cache

        if page_id in self._cache:
            self._cache.move_to_end(page_id)
            return self._cache[page_id].data

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

    def mark_dirty(self, page_id: int) -> None:
        """Mark a cached page as dirty."""
        if page_id in self._cache:
            self._cache[page_id].dirty = True

    def set_page_data(self, page_id: int, data: bytes) -> None:
        """Update cached page data and mark it dirty."""
        if page_id in self._cache:
            self._cache[page_id].data = data
            self._cache[page_id].dirty = True

    def pin(self, page_id: int, txn_id: int | None = None, mode=None) -> None:
        """Pin a page to prevent eviction. Optionally acquires a lock."""
        from tinydb.concurrency.lock_manager import LockMode
        if page_id not in self._cache:
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
        else:
            self._pinned.add(page_id)
            self._cache.move_to_end(page_id)

        # Acquire lock if txn_id and mode provided
        if txn_id is not None and mode is not None:
            lock_mgr = _get_lock_mgr(self)
            lock_mgr.acquire(txn_id, page_id, mode)

    def unpin(self, page_id: int, txn_id: int | None = None) -> None:
        """Unpin a page. Optionally releases a lock."""
        self._pinned.discard(page_id)

        # Release lock if txn_id provided
        if txn_id is not None and hasattr(self, '_lock_mgr'):
            self._lock_mgr.release(txn_id, page_id)

    def flush(self) -> None:
        """Write all dirty pages to disk."""
        for page in self._cache.values():
            if page.dirty:
                self._fm.write_page(page.page_id, page.data)
                page.dirty = False

    # --- Internal methods ---

    def _insert_page(self, page_id: int, page: Page, pinned: bool = False) -> None:
        """Insert page into cache, evicting if necessary."""
        if pinned:
            self._cache[page_id] = page
            self._cache.move_to_end(page_id)
            self._pinned.add(page_id)
        else:
            # Evict until there's room
            while len(self._cache) >= self._capacity:
                self._evict_one()

            self._cache[page_id] = page
            self._cache.move_to_end(page_id)

    def _evict_one(self) -> None:
        """Evict the LRU page that is not pinned."""
        for pid, page in self._cache.items():
            if pid not in self._pinned:
                if page.dirty:
                    self._fm.write_page(pid, page.data)
                    page.dirty = False
                del self._cache[pid]
                return

        raise PageOutOfRangeError(
            "Buffer pool full and all pages are pinned"
        )
