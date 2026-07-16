"""AST node definitions for SQL statements."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TableRef:
    """Table reference with optional alias."""
    name: str
    alias: str | None = None


@dataclass
class JoinClause:
    """JOIN clause AST node."""
    join_type: str  # INNER, LEFT, RIGHT, FULL, CROSS, NATURAL
    right_table: TableRef
    on_condition: Optional[object] = None
    using_columns: Optional[list] = None


@dataclass
class SelectStatement:
    """SELECT statement AST node."""
    columns: list
    table: str
    from_table: TableRef = None
    joins: list = field(default_factory=list)
    where: Optional[object] = None
    order_by: Optional[list] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    group_by: Optional[list] = None

    def __post_init__(self):
        if self.from_table is None:
            self.from_table = TableRef(name=self.table)


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
