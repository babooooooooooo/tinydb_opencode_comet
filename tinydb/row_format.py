# tinydb/row_format.py
"""Row serialization format: NULL bitmap + typed column encoding.

Row wire format:
  Header:
    - null_bitmap: ceil(n/8) bytes
    - num_columns: uint16
  Body (in column order):
    - INTEGER: 8 bytes (int64, little-endian)
    - FLOAT:   8 bytes (double, little-endian)
    - BOOLEAN: 1 byte (0 or 1)
    - TEXT:    4 bytes length (uint32) + UTF-8 bytes
"""
import struct
import math
from tinydb.types import DataType, ColumnDef


_HEADER_FMT = "<H"  # num_columns: uint16
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)

_INT_FMT = "<q"     # int64
_FLOAT_FMT = "<d"   # double
_BOOL_FMT = "<?"
_TEXT_LEN_FMT = "<I"  # uint32 for text length


def encode_null_flags(null_flags: list[bool]) -> bytes:
    """Encode a list of NULL flags into a bitmap (1 bit per column)."""
    n = len(null_flags)
    num_bytes = math.ceil(n / 8)
    bitmap = bytearray(num_bytes)

    for i, is_null in enumerate(null_flags):
        if is_null:
            byte_idx = i // 8
            bit_idx = i % 8
            bitmap[byte_idx] |= (1 << bit_idx)

    return bytes(bitmap)


def decode_null_flags(bitmap: bytes, num_columns: int) -> list[bool]:
    """Decode a bitmap into a list of NULL flags."""
    flags = []
    for i in range(num_columns):
        byte_idx = i // 8
        bit_idx = i % 8
        is_null = bool(bitmap[byte_idx] & (1 << bit_idx))
        flags.append(is_null)
    return flags


def serialize_row(values: list, columns: list[ColumnDef]) -> bytes:
    """Serialize a row (list of values) into bytes."""
    n = len(columns)
    null_flags = [v is None for v in values]

    # Header
    result = bytearray()
    result.extend(encode_null_flags(null_flags))
    result.extend(struct.pack(_HEADER_FMT, n))

    # Body: serialize each non-NULL column
    for i, (val, col) in enumerate(zip(values, columns)):
        if val is None:
            continue  # NULL values are only recorded in bitmap

        if col.data_type == DataType.INTEGER:
            result.extend(struct.pack(_INT_FMT, val))
        elif col.data_type == DataType.FLOAT:
            fval = float(val) if isinstance(val, int) else val
            result.extend(struct.pack(_FLOAT_FMT, fval))
        elif col.data_type == DataType.TEXT:
            encoded = val.encode("utf-8")
            result.extend(struct.pack(_TEXT_LEN_FMT, len(encoded)))
            result.extend(encoded)
        elif col.data_type == DataType.BOOLEAN:
            result.extend(struct.pack(_BOOL_FMT, val))

    return bytes(result)


def deserialize_row(data: bytes, columns: list[ColumnDef]) -> list:
    """Deserialize bytes back into a row (list of values)."""
    if not data:
        return []

    # Read bitmap
    n = len(columns)
    num_bitmap_bytes = math.ceil(n / 8)
    bitmap = data[:num_bitmap_bytes]
    null_flags = decode_null_flags(bitmap, n)

    # Read num_columns header
    offset = num_bitmap_bytes
    num_columns = struct.unpack_from(_HEADER_FMT, data, offset)[0]
    offset += _HEADER_SIZE

    # Read values
    result = []
    for i in range(num_columns):
        if null_flags[i]:
            result.append(None)
            continue

        col = columns[i]
        if col.data_type == DataType.INTEGER:
            val = struct.unpack_from(_INT_FMT, data, offset)[0]
            offset += struct.calcsize(_INT_FMT)
        elif col.data_type == DataType.FLOAT:
            val = struct.unpack_from(_FLOAT_FMT, data, offset)[0]
            offset += struct.calcsize(_FLOAT_FMT)
        elif col.data_type == DataType.TEXT:
            text_len = struct.unpack_from(_TEXT_LEN_FMT, data, offset)[0]
            offset += struct.calcsize(_TEXT_LEN_FMT)
            val = data[offset:offset + text_len].decode("utf-8")
            offset += text_len
        elif col.data_type == DataType.BOOLEAN:
            val = struct.unpack_from(_BOOL_FMT, data, offset)[0]
            offset += struct.calcsize(_BOOL_FMT)
        else:
            val = None

        result.append(val)

    return result
