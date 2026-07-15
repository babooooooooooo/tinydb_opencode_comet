"""AST node definitions for SQL statements."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class SelectStatement:
    """SELECT statement AST node."""
    columns: list
    table: str
    where: Optional[object] = None
    order_by: Optional[list] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    group_by: Optional[list] = None


@dataclass
class InsertStatement:
    """INSERT statement AST node."""
    table: str
    columns: Optional[list]
    values: list


@dataclass
class UpdateStatement:
    """UPDATE statement AST node."""
    table: str
    assignments: list
    where: Optional[object] = None


@dataclass
class DeleteStatement:
    """DELETE statement AST node."""
    table: str
    where: Optional[object] = None


@dataclass
class ColumnDefAST:
    """Column definition in CREATE TABLE."""
    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    not_null: bool = False


@dataclass
class CreateTableStatement:
    """CREATE TABLE statement AST node."""
    table: str
    columns: list


@dataclass
class DropTableStatement:
    """DROP TABLE statement AST node."""
    table: str
