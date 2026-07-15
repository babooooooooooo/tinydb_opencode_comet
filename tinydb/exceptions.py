"""存储引擎异常体系。"""


class StorageError(Exception):
    """存储引擎所有异常的基类。"""


class StorageCorruptionError(StorageError):
    """检测到数据损坏时抛出。"""


class StorageFullError(StorageError):
    """存储空间不足时抛出。"""


class PageOutOfRangeError(StorageError):
    """访问超出文件范围的页号时抛出。"""


class TableExistsError(StorageError):
    """创建已存在的表时抛出。"""


class TableNotFoundError(StorageError):
    """访问不存在的表时抛出。"""


class SchemaMismatchError(StorageError):
    """表结构与操作不匹配时抛出。"""
