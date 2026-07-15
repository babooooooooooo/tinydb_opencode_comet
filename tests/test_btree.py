# tests/test_btree.py
import pytest
from tinydb.index.btree import BTreeIndex, encode_key, decode_key
from tinydb.types import DataType
from tinydb.page import RowId
from tinydb.file_manager import FileManager
from tinydb.buffer_pool import BufferPool


@pytest.fixture
def env(tmp_path):
    db_path = str(tmp_path / "test.db")
    fm = FileManager(db_path)
    fm.open()
    pool = BufferPool(fm, capacity=100)
    yield fm, pool
    fm.close()


class TestKeyEncoding:
    def test_integer_encoding(self):
        data = encode_key(42, DataType.INTEGER)
        assert decode_key(data, DataType.INTEGER) == 42
        neg = encode_key(-1, DataType.INTEGER)
        zero = encode_key(0, DataType.INTEGER)
        pos = encode_key(1, DataType.INTEGER)
        assert neg < zero < pos

    def test_float_encoding(self):
        data = encode_key(3.14, DataType.FLOAT)
        assert abs(decode_key(data, DataType.FLOAT) - 3.14) < 1e-10

    def test_boolean_encoding(self):
        assert decode_key(encode_key(True, DataType.BOOLEAN), DataType.BOOLEAN) is True
        assert decode_key(encode_key(False, DataType.BOOLEAN), DataType.BOOLEAN) is False

    def test_text_encoding(self):
        data = encode_key("hello", DataType.TEXT)
        assert decode_key(data, DataType.TEXT) == "hello"


class TestBTreeIndex:
    def test_empty_tree(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        assert btree.search(42) == []

    def test_insert_and_search(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        btree.insert(10, RowId(page_id=1, slot_index=0))
        btree.insert(20, RowId(page_id=1, slot_index=1))
        btree.insert(30, RowId(page_id=2, slot_index=0))

        result = btree.search(20)
        assert len(result) == 1
        assert result[0].page_id == 1
        assert result[0].slot_index == 1

    def test_search_not_found(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        btree.insert(10, RowId(page_id=1, slot_index=0))
        assert btree.search(99) == []

    def test_range_scan(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        for i in range(1, 11):
            btree.insert(i, RowId(page_id=1, slot_index=i-1))

        results = btree.range_scan(start=3, end=7)
        assert len(results) == 5
        keys_found = sorted([r.slot_index + 1 for r in results])
        assert keys_found == [3, 4, 5, 6, 7]

    def test_delete(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        btree.insert(10, RowId(page_id=1, slot_index=0))
        btree.delete(10, RowId(page_id=1, slot_index=0))
        assert btree.search(10) == []

    def test_persistence(self, env):
        fm, pool = env
        btree = BTreeIndex(pool, key_type=DataType.INTEGER)
        btree.insert(42, RowId(page_id=5, slot_index=3))
        root_page = btree.root_page
        pool.flush()

        btree2 = BTreeIndex(pool, key_type=DataType.INTEGER, root_page=root_page)
        result = btree2.search(42)
        assert len(result) == 1
        assert result[0].page_id == 5
        assert result[0].slot_index == 3
