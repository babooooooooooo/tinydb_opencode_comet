"""Buffer Pool with LRU eviction and pin/unpin support.

Two-layer design for educational clarity:
  1. OrderedDict layer: provides O(1) lookup and move_to_end
  2. Doubly-linked list layer: explicit LRU for teaching purposes

The doubly-linked list is the "source of truth" for eviction order.
OrderedDict provides fast membership checks.

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


class LRU_Node:
    """Doubly-linked list node for LRU tracking."""

    def __init__(self, page_id: int, page: Page):
        self.page_id = page_id
        self.page = page
        self.prev: "LRU_Node | None" = None
        self.next: "LRU_Node | None" = None
        self.ref_count: int = 0  # pin count


class BufferPool:
    """LRU buffer pool with pin/unpin and dirty page management."""

    def __init__(self, file_manager, capacity: int = DEFAULT_BUFFER_POOL_CAPACITY):
        self._fm = file_manager
        self._capacity = capacity
        self._cache: OrderedDict[int, LRU_Node] = OrderedDict()

        # Doubly-linked list boundaries
        self._head: LRU_Node | None = None  # most recently used
        self._tail: LRU_Node | None = None  # least recently used

    @property
    def size(self) -> int:
        return len(self._cache)

    def get_page(self, page_id: int) -> bytes:
        """Get a page from cache or disk."""
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

    def mark_dirty(self, page_id: int) -> None:
        """Mark a cached page as dirty."""
        if page_id in self._cache:
            self._cache[page_id].page.dirty = True

    def set_page_data(self, page_id: int, data: bytes) -> None:
        """Update cached page data and mark it dirty."""
        if page_id in self._cache:
            self._cache[page_id].page.data = data
            self._cache[page_id].page.dirty = True

    def pin(self, page_id: int, txn_id: int | None = None, mode=None) -> None:
        """Pin a page to prevent eviction. Optionally acquires a lock."""
        from tinydb.concurrency.lock_manager import LockMode
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
            lock_mgr = _get_lock_mgr(self)
            lock_mgr.acquire(txn_id, page_id, mode)

    def unpin(self, page_id: int, txn_id: int | None = None) -> None:
        """Unpin a page. Optionally releases a lock."""
        if page_id in self._cache:
            node = self._cache[page_id]
            if node.ref_count > 0:
                node.ref_count -= 1

        # Release lock if txn_id provided
        if txn_id is not None and hasattr(self, '_lock_mgr'):
            self._lock_mgr.release(txn_id, page_id)

    def flush(self) -> None:
        """Write all dirty pages to disk."""
        for node in self._cache.values():
            if node.page.dirty:
                self._fm.write_page(node.page_id, node.page.data)
                node.page.dirty = False

    # --- Internal doubly-linked list operations ---

    def _insert_page(self, page_id: int, page: Page, pinned: bool = False) -> None:
        """Insert page into cache, evicting if necessary."""
        if pinned:
            node = LRU_Node(page_id, page)
            node.ref_count = 1
            self._cache[page_id] = node
            self._insert_head(node)
        else:
            # Evict until there's room
            while len(self._cache) >= self._capacity:
                self._evict_one()

            node = LRU_Node(page_id, page)
            self._cache[page_id] = node
            self._insert_head(node)

    def _evict_one(self) -> None:
        """Evict the LRU page that is not pinned."""
        # Find eviction candidate from tail upward
        candidate = self._tail
        while candidate is not None and candidate.ref_count > 0:
            candidate = candidate.prev

        if candidate is None:
            # All pages pinned — cannot evict
            raise PageOutOfRangeError(
                "Buffer pool full and all pages are pinned"
            )

        # Flush dirty page
        if candidate.page.dirty:
            self._fm.write_page(candidate.page_id, candidate.page.data)
            candidate.page.dirty = False

        # Remove from linked list
        self._remove_node(candidate)

        # Remove from cache
        del self._cache[candidate.page_id]

    def _insert_head(self, node: LRU_Node) -> None:
        """Insert node at head (most recently used)."""
        node.prev = None
        node.next = self._head
        if self._head:
            self._head.prev = node
        self._head = node
        if self._tail is None:
            self._tail = node

    def _remove_node(self, node: LRU_Node) -> None:
        """Remove node from linked list."""
        if node.prev:
            node.prev.next = node.next
        else:
            self._head = node.next

        if node.next:
            node.next.prev = node.prev
        else:
            self._tail = node.prev

        node.prev = None
        node.next = None

    def _move_to_head(self, node: LRU_Node) -> None:
        """Move an existing node to head (mark as recently used)."""
        if node is self._head:
            return
        self._remove_node(node)
        self._insert_head(node)
