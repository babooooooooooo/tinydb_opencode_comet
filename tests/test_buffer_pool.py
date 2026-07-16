# tests/test_buffer_pool.py
"""Tests for tinydb.buffer_pool module."""
import pytest
from unittest.mock import MagicMock
from tinydb.buffer_pool import BufferPool, LRU_Node
from tinydb.page import create_empty_page, PageType, parse_page_header
from tinydb.constants import PAGE_SIZE


class TestLRUNode:
    def test_node_creation(self):
        node = LRU_Node(page_id=1, page=None)
        assert node.page_id == 1
        assert node.page is None
        assert node.prev is None
        assert node.next is None
        assert node.ref_count == 0


class TestBufferPool:
    @pytest.fixture
    def mock_fm(self):
        """A mock FileManager that returns synthetic pages."""
        fm = MagicMock()
        fm.read_page.side_effect = lambda pid: _make_page_bytes(pid)
        fm.page_count = 100
        return fm

    def test_get_page_not_in_cache(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        data = pool.get_page(1)
        assert isinstance(data, bytes)
        assert len(data) == PAGE_SIZE
        mock_fm.read_page.assert_called_once_with(1)

    def test_get_page_cache_hit(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        pool.get_page(1)
        mock_fm.read_page.assert_called_once_with(1)
        # Second access should be cached
        pool.get_page(1)
        mock_fm.read_page.assert_called_once()  # still only 1 read

    def test_eviction_when_full(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=3)
        pool.get_page(1)
        pool.get_page(2)
        pool.get_page(3)
        # Pool is full. Accessing page 4 should evict the LRU (page 1)
        pool.get_page(4)
        # page 1 should have been evicted
        assert 1 not in pool._cache
        assert 4 in pool._cache

    def test_access_marks_as_recently_used(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=3)
        pool.get_page(1)
        pool.get_page(2)
        pool.get_page(3)
        # Access page 1 to make it recently used
        pool.get_page(1)
        # Now add page 4, should evict page 2 (oldest)
        pool.get_page(4)
        assert 2 not in pool._cache
        assert 1 in pool._cache

    def test_pin_prevents_eviction(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=3)
        pool.get_page(1)
        pool.get_page(2)
        pool.get_page(3)
        pool.pin(4)
        pool.get_page(4)  # pin also fetches
        # Pool has 4 entries but capacity=3, yet pin prevents eviction
        assert 4 in pool._cache
        # Add page 5, LRU (page 1) should be evicted, not page 4
        pool.get_page(5)
        assert 1 not in pool._cache
        assert 4 in pool._cache

    def test_unpin_allows_eviction(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=3)
        pool.get_page(1)
        pool.get_page(2)
        pool.get_page(3)
        pool.unpin(1)
        # Access page 4, should evict page 1 (now unpinned, LRU)
        pool.get_page(4)
        assert 1 not in pool._cache

    def test_flush_writes_dirty_pages(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=10)
        # Mark a page as dirty
        pool.get_page(1)
        pool.mark_dirty(1)
        pool.flush()
        mock_fm.write_page.assert_called()

    def test_evict_dirty_page_flushes_first(self, mock_fm):
        pool = BufferPool(mock_fm, capacity=2)
        pool.get_page(1)
        pool.mark_dirty(1)
        pool.get_page(2)
        # Pool full. Access page 3, must evict page 1 (dirty) — should flush
        mock_fm.write_page.reset_mock()
        pool.get_page(3)
        mock_fm.write_page.assert_called_once()


class TestBufferPoolLockIntegration:
    @pytest.fixture
    def mock_fm(self):
        fm = MagicMock()
        fm.read_page.side_effect = lambda pid: _make_page_bytes(pid)
        fm.page_count = 100
        return fm

    def test_pin_acquires_lock(self, mock_fm):
        from tinydb.concurrency.lock_manager import LockMode
        pool = BufferPool(mock_fm, capacity=10)
        pool.pin(page_id=1, txn_id=1, mode=LockMode.SHARED)
        holders = pool._lock_mgr.get_lock_holders(1)
        assert 1 in holders

    def test_unpin_releases_lock(self, mock_fm):
        from tinydb.concurrency.lock_manager import LockMode
        pool = BufferPool(mock_fm, capacity=10)
        pool.pin(page_id=1, txn_id=1, mode=LockMode.SHARED)
        pool.unpin(page_id=1, txn_id=1)
        holders = pool._lock_mgr.get_lock_holders(1)
        assert 1 not in holders

    def test_pin_exclusive_blocks_other(self, mock_fm):
        from tinydb.concurrency.lock_manager import LockMode
        pool = BufferPool(mock_fm, capacity=10)
        pool.pin(page_id=1, txn_id=1, mode=LockMode.EXCLUSIVE)
        # txn 2 should not be able to acquire SHARED immediately
        result = pool._lock_mgr.acquire(2, 1, LockMode.SHARED, timeout=0.1)
        assert result is False


def _make_page_bytes(page_id: int) -> bytes:
    """Helper to create valid page bytes for mock read_page."""
    data = bytearray(PAGE_SIZE)
    # Write a minimal valid header
    from tinydb.page import pack_page_header
    header = pack_page_header(
        page_id=page_id,
        page_type=PageType.DATA,
        slot_count=0,
        free_space=PAGE_SIZE - 32,
        free_offset=PAGE_SIZE,
        next_page_id=0,
        flags=0,
    )
    data[:len(header)] = header
    return bytes(data)
