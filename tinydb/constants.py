"""存储引擎全局常量定义。"""

PAGE_SIZE = 4096
"""每页的字节数，固定为 4096。"""

PAGE_HEADER_SIZE = 32
"""每页头部占用的字节数。"""

SLOT_SIZE = 4
"""页内槽位目录每个条目的字节数。"""

MAGIC_BYTES = b"TINYDB\0"
"""数据库文件的魔数标识。"""

FORMAT_VERSION = 1
"""数据库文件格式版本号。"""

DEFAULT_BUFFER_POOL_CAPACITY = 100
"""BufferPool 默认可容纳的页数。"""

MAX_FREE_SPACE = PAGE_SIZE - PAGE_HEADER_SIZE
"""每页可用于存储数据的最大空间，即 4064 字节。"""

NULL_BITMAP_BYTES = 8
"""NULL 位图默认字节数（对应最多 64 列）。"""

INTEGER_SIZE = 8
"""INTEGER 类型占用的字节数（int64）。"""

FLOAT_SIZE = 8
"""FLOAT 类型占用的字节数（double）。"""

BOOLEAN_SIZE = 1
"""BOOLEAN 类型占用的字节数。"""

TEXT_LENGTH_SIZE = 4
"""TEXT 类型长度前缀占用的字节数。"""
