"""pytest 共享 fixtures。"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db_path():
    """提供临时目录下的数据库文件路径，测试结束后自动清理。"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "test.db"


@pytest.fixture
def sample_column_data():
    """返回样例列定义原始数据，格式为 (列名, 数据类型字符串)。"""
    return [
        ("id", "INTEGER"),
        ("name", "TEXT"),
        ("score", "FLOAT"),
        ("active", "BOOLEAN"),
    ]
