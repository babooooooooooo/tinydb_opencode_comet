# tests/test_shadow_paging.py
import pytest
from tinydb.transaction.shadow_paging import Transaction, ShadowBufferPool
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool
from tinydb.page import create_empty_page, PageType


@pytest.fixture
def env(tmp_path):
    db_path = str(tmp_path / "test.db")
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    yield fm, pool
    fm.close()


class TestShadowPaging:
    def test_cow_creates_shadow_page(self, env):
        fm, pool = env
        page = create_empty_page(1, PageType.DATA)
        fm.write_page(1, page.data)
        fm.page_count = 2

        txn = Transaction(txn_id=1, state="active", shadow_pages={},
                          snapshot_root=0, new_root=0)
        shadow = ShadowBufferPool(pool, txn, fm)

        shadow.set_page_data(1, page.data)
        assert 1 in txn.shadow_pages
        assert txn.shadow_pages[1] != 1

    def test_read_sees_shadow(self, env):
        fm, pool = env
        page = create_empty_page(1, PageType.DATA)
        fm.write_page(1, page.data)
        fm.page_count = 2

        txn = Transaction(txn_id=1, state="active", shadow_pages={},
                          snapshot_root=0, new_root=0)
        shadow = ShadowBufferPool(pool, txn, fm)

        modified = bytearray(page.data)
        modified[40] = 0xAB
        shadow.set_page_data(1, bytes(modified))

        result = shadow.get_page(1)
        assert result[40] == 0xAB

    def test_rollback_releases_shadow_pages(self, env):
        fm, pool = env
        page = create_empty_page(1, PageType.DATA)
        fm.write_page(1, page.data)
        fm.page_count = 2

        txn = Transaction(txn_id=1, state="active", shadow_pages={},
                          snapshot_root=0, new_root=0)
        shadow = ShadowBufferPool(pool, txn, fm)
        shadow.set_page_data(1, page.data)

        shadow.rollback()

        assert txn.state == "aborted"
        assert len(txn.shadow_pages) == 0

    def test_commit_flushes_and_updates_root(self, env):
        fm, pool = env
        page = create_empty_page(1, PageType.DATA)
        fm.write_page(1, page.data)
        fm.page_count = 2

        txn = Transaction(txn_id=1, state="active", shadow_pages={},
                          snapshot_root=0, new_root=0)
        shadow = ShadowBufferPool(pool, txn, fm)
        shadow.set_page_data(1, page.data)

        txn.new_root = 5
        shadow.commit()

        assert txn.state == "committed"
        assert fm.root_page_id == 5
