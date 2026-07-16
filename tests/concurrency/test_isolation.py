"""Tests for tinydb.concurrency.isolation module."""
from tinydb.concurrency.isolation import IsolationLevel, default_isolation, validate_isolation


class TestIsolationLevel:
    def test_enum_values(self):
        assert IsolationLevel.READ_UNCOMMITTED.value == "READ UNCOMMITTED"
        assert IsolationLevel.READ_COMMITTED.value == "READ COMMITTED"
        assert IsolationLevel.REPEATABLE_READ.value == "REPEATABLE READ"
        assert IsolationLevel.SERIALIZABLE.value == "SERIALIZABLE"

    def test_default_isolation(self):
        assert default_isolation() == IsolationLevel.REPEATABLE_READ

    def test_validate_isolation_valid(self):
        assert validate_isolation(IsolationLevel.READ_UNCOMMITTED) is True
        assert validate_isolation(IsolationLevel.REPEATABLE_READ) is True

    def test_validate_isolation_invalid(self):
        assert validate_isolation("READ UNCOMMITTED") is False
        assert validate_isolation(1) is False
        assert validate_isolation(None) is False
