# tests/test_file_header_ext.py
"""Tests for file header extension: root_page_id + version bump."""
import os
import pytest
from tinydb.file_manager import FileManager
from tinydb.constants import FORMAT_VERSION


class TestFileHeaderExtension:
    def test_new_db_has_root_page_id(self, tmp_path):
        """新数据库创建后 root_page_id 可读写"""
        db_path = str(tmp_path / "test.db")
        fm = FileManager(db_path)
        fm.open()
        assert fm.root_page_id == 0
        fm.root_page_id = 5
        fm._write_header()
        fm.close()

        fm2 = FileManager(db_path)
        fm2.open()
        assert fm2.root_page_id == 5
        fm2.close()

    def test_version_bumped_to_2(self, tmp_path):
        """版本号已升级到 2"""
        assert FORMAT_VERSION == 2

    def test_backward_compat_v1(self, tmp_path):
        """向后兼容：读取 version=1 的数据库文件"""
        db_path = str(tmp_path / "v1.db")
        import struct, zlib
        from tinydb.constants import MAGIC_BYTES, PAGE_SIZE
        raw = bytearray(PAGE_SIZE)
        raw[:8] = MAGIC_BYTES
        _V1_FMT = "<IIIIIQ"
        offset = 8
        struct.pack_into(_V1_FMT, raw, offset, 1, PAGE_SIZE, 1, 0, 0, 0)
        header_data = raw[offset:offset + struct.calcsize(_V1_FMT) - 8]
        checksum = zlib.crc32(header_data) & 0xFFFFFFFFFFFFFFFF
        struct.pack_into("<Q", raw, offset + struct.calcsize(_V1_FMT) - 8, checksum)
        with open(db_path, "wb") as f:
            f.write(bytes(raw))

        fm = FileManager(db_path)
        fm.open()
        assert fm.root_page_id == 0
        fm.close()
