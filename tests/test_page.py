"""Tests for tinydb.page module."""
import pytest
from tinydb.page import (
    Page, PageType, RowId, PAGE_HEADER_FORMAT,
    create_empty_page, parse_page_header, pack_page_header,
    insert_row_into_page, get_row_from_page, delete_row_from_page,
    get_all_rows_from_page, get_free_space,
)
from tinydb.constants import PAGE_SIZE, PAGE_HEADER_SIZE, SLOT_SIZE, MAX_FREE_SPACE


class TestPageType:
    def test_page_type_values(self):
        assert PageType.DATA.value == 1
        assert PageType.CATALOG.value == 2
        assert PageType.INDEX.value == 3


class TestRowId:
    def test_row_id_creation(self):
        rid = RowId(page_id=5, slot_index=3)
        assert rid.page_id == 5
        assert rid.slot_index == 3

    def test_row_id_immutable(self):
        rid = RowId(page_id=5, slot_index=3)
        with pytest.raises(AttributeError):
            rid.page_id = 10


class TestPageHeader:
    def test_pack_unpack_roundtrip(self):
        header = {
            "page_id": 42,
            "page_type": PageType.DATA,
            "slot_count": 3,
            "free_space": 3000,
            "free_offset": 3500,
            "next_page_id": 0,
            "flags": 0,
        }
        data = pack_page_header(**header)
        assert len(data) == PAGE_HEADER_SIZE
        parsed = parse_page_header(data)
        assert parsed["page_id"] == 42
        assert parsed["page_type"] == PageType.DATA
        assert parsed["slot_count"] == 3
        assert parsed["free_space"] == 3000
        assert parsed["free_offset"] == 3500

    def test_header_size_is_32(self):
        assert PAGE_HEADER_SIZE == 32


class TestPageCreation:
    def test_create_empty_data_page(self):
        page = create_empty_page(page_id=1, page_type=PageType.DATA)
        assert isinstance(page, Page)
        assert page.page_id == 1
        assert page.page_type == PageType.DATA
        assert page.slot_count == 0
        assert page.dirty is False
        assert len(page.data) == PAGE_SIZE


class TestPageOperations:
    @pytest.fixture
    def page(self):
        return create_empty_page(page_id=1, page_type=PageType.DATA)

    def test_insert_row(self, page):
        row_data = b"hello world row data"
        slot_idx = insert_row_into_page(page, row_data)
        assert slot_idx == 0
        assert page.slot_count == 1
        assert page.dirty is True

    def test_insert_and_get_row(self, page):
        row_data = b"test data"
        slot_idx = insert_row_into_page(page, row_data)
        retrieved = get_row_from_page(page, slot_idx)
        assert retrieved == row_data

    def test_insert_multiple_rows(self, page):
        rows = [b"row1", b"row2", b"row3"]
        for i, row in enumerate(rows):
            slot_idx = insert_row_into_page(page, row)
            assert slot_idx == i
        assert page.slot_count == 3
        all_rows = get_all_rows_from_page(page)
        assert all_rows == rows

    def test_delete_row(self, page):
        slot_idx = insert_row_into_page(page, b"to be deleted")
        delete_row_from_page(page, slot_idx)
        retrieved = get_row_from_page(page, slot_idx)
        assert retrieved is None

    def test_free_space_decreases_after_insert(self, page):
        initial_free = get_free_space(page)
        insert_row_into_page(page, b"some data that takes space")
        assert get_free_space(page) < initial_free

    def test_get_free_space_initial(self, page):
        # Empty page: free space = MAX_FREE_SPACE
        assert get_free_space(page) == MAX_FREE_SPACE
