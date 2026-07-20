# tinydb/types.py
"""类型系统：DataType 枚举、ColumnDef、Value 包装、类型校验与转换。"""
from dataclasses import dataclass
from enum import Enum

from tinydb.exceptions import SchemaMismatchError


class DataType(Enum):
    """支持的数据类型枚举。"""

    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"


@dataclass
class ColumnDef:
    """列定义，描述表结构中某一列的元数据。"""

    name: str
    data_type: DataType
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "data_type": self.data_type.value,
            "nullable": self.nullable,
            "primary_key": self.primary_key,
            "unique": self.unique,
        }


@dataclass
class Value:
    """带类型的值包装器。"""

    data: object
    data_type: DataType

    @property
    def is_null(self) -> bool:
        """判断该值是否为 NULL。"""
        return self.data is None


def validate_value(value: object, column: ColumnDef) -> None:
    """根据列定义校验值，类型不匹配时抛出 SchemaMismatchError。"""
    if value is None:
        if not column.nullable:
            raise SchemaMismatchError(
                f"Column '{column.name}' is NOT NULL but received NULL"
            )
        return

    col_type = column.data_type

    if col_type == DataType.INTEGER:
        if isinstance(value, bool) or isinstance(value, float):
            raise SchemaMismatchError(
                f"Column '{column.name}' is INTEGER but received {type(value).__name__}: {value}"
            )
        if not isinstance(value, int):
            raise SchemaMismatchError(
                f"Column '{column.name}' is INTEGER but received {type(value).__name__}"
            )

    elif col_type == DataType.FLOAT:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemaMismatchError(
                f"Column '{column.name}' is FLOAT but received {type(value).__name__}"
            )

    elif col_type == DataType.TEXT:
        if not isinstance(value, str):
            raise SchemaMismatchError(
                f"Column '{column.name}' is TEXT but received {type(value).__name__}"
            )

    elif col_type == DataType.BOOLEAN:
        if not isinstance(value, bool):
            raise SchemaMismatchError(
                f"Column '{column.name}' is BOOLEAN but received {type(value).__name__}"
            )


def convert_value(value: object, column: ColumnDef) -> object:
    """校验并将值转换为目标列类型。"""
    validate_value(value, column)

    if value is None:
        return None

    if column.data_type == DataType.FLOAT and isinstance(value, int):
        return float(value)

    return value
