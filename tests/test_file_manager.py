# tests/test_file_manager.py
"""Tests for tinydb.file_manager module."""
import os
import pytest
from tinydb.file_manager import FileManager
from tinydb.page import create_empty_page, PageType
from tinydb.exceptions import StorageCorruptionError, PageOutOfRangeError
from tinydb.constants import PAGE_SIZE


class TestFileManagerOpen:
    def test_create_new_database(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        assert os.path.exists(db_path)
        assert fm.page_count == 1
        fm.close()

    def test_open_existing_database(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        fm.close()

        fm2 = FileManager(db_path)
        fm2.open()
        assert fm2.page_count == 1
        fm2.close()

    def test_invalid_magic_rejected(self, tmp_path):
        db_path = str(tmp_path / "corrupt.db")
        with open(db_path, "wb") as f:
            f.write(b"NODB\0" + b"\x00" * 100)
        fm = FileManager(db_path)
        with pytest.raises(StorageCorruptionError):
            fm.open()


class TestFileManagerPageIO:
    @pytest.fixture
    def fm(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        yield fm
        fm.close()

    def test_read_page_zero(self, fm):
        page = fm.read_page(0)
        assert isinstance(page, bytes)
        assert len(page) == PAGE_SIZE

    def test_alloc_page(self, fm):
        page_id = fm.alloc_page()
        assert page_id == 1  # page 0 is header, first alloc is page 1
        assert fm.page_count == 2

    def test_alloc_multiple_pages(self, fm):
        ids = [fm.alloc_page() for _ in range(5)]
        assert ids == [1, 2, 3, 4, 5]
        assert fm.page_count == 6

    def test_write_and_read_page(self, fm):
        page = create_empty_page(1, PageType.DATA)
        fm.write_page(page.page_id, page.data)
        data = fm.read_page(1)
        assert len(data) == PAGE_SIZE

    def test_read_out_of_range_page(self, fm):
        with pytest.raises(PageOutOfRangeError):
            fm.read_page(9999)

    def test_free_page(self, fm):
        page_id = fm.alloc_page()
        fm.free_page(page_id)
        # free page should be re-usable
        new_id = fm.alloc_page()
        assert new_id == page_id

    def test_close_flushes_metadata(self, fm):
        fm.alloc_page()
        initial_count = fm.page_count
        fm.close()

        fm2 = FileManager(fm.db_path)
        fm2.open()
        assert fm2.page_count == initial_count
        fm2.close()
