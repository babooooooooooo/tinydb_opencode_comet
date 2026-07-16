"""Isolation level definitions for tinydb concurrency control."""
from enum import Enum


class IsolationLevel(Enum):
    """Transaction isolation levels."""
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


def default_isolation() -> IsolationLevel:
    """Return the default isolation level (REPEATABLE READ)."""
    return IsolationLevel.REPEATABLE_READ


def validate_isolation(level) -> bool:
    """Check if the given level is a valid IsolationLevel enum member."""
    return isinstance(level, IsolationLevel)
