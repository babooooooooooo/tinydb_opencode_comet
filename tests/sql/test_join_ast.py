# tests/sql/test_join_ast.py
"""Tests for JOIN-related AST nodes."""
from tinydb.sql.ast import TableRef, JoinClause, SelectStatement
from tinydb.sql.expressions import ColumnRef, BinaryOp


class TestTableRef:
    def test_table_ref_no_alias(self):
        ref = TableRef(name="users")
        assert ref.name == "users"
        assert ref.alias is None

    def test_table_ref_with_alias(self):
        ref = TableRef(name="users", alias="u")
        assert ref.name == "users"
        assert ref.alias == "u"


class TestJoinClause:
    def test_inner_join_with_on(self):
        right = TableRef(name="orders", alias="o")
        on = BinaryOp('=', ColumnRef("u.id"), ColumnRef("o.user_id"))
        jc = JoinClause(join_type="INNER", right_table=right, on_condition=on)
        assert jc.join_type == "INNER"
        assert jc.right_table.name == "orders"
        assert jc.on_condition is on
        assert jc.using_columns is None

    def test_cross_join_no_condition(self):
        right = TableRef(name="orders")
        jc = JoinClause(join_type="CROSS", right_table=right)
        assert jc.join_type == "CROSS"
        assert jc.on_condition is None

    def test_natural_join(self):
        right = TableRef(name="orders")
        jc = JoinClause(join_type="NATURAL", right_table=right)
        assert jc.join_type == "NATURAL"
        assert jc.on_condition is None

    def test_join_with_using(self):
        right = TableRef(name="orders")
        jc = JoinClause(join_type="INNER", right_table=right, using_columns=["id"])
        assert jc.using_columns == ["id"]


class TestSelectStatementWithJoins:
    def test_backward_compatible_construction(self):
        """Old-style construction still works."""
        stmt = SelectStatement(columns=["id", "name"], table="users")
        assert stmt.table == "users"
        assert stmt.from_table.name == "users"
        assert stmt.joins == []

    def test_new_style_construction(self):
        from_table = TableRef(name="users", alias="u")
        joins = [JoinClause(join_type="INNER", right_table=TableRef("orders"))]
        stmt = SelectStatement(columns=["id"], table="users", from_table=from_table, joins=joins)
        assert stmt.from_table.alias == "u"
        assert len(stmt.joins) == 1

    def test_default_joins_empty_list(self):
        stmt = SelectStatement(columns=["*"], table="users")
        assert stmt.joins == []


class TestColumnRefWithTable:
    def test_column_ref_without_table(self):
        col = ColumnRef(name="id")
        assert col.name == "id"
        assert col.table is None

    def test_column_ref_with_table(self):
        col = ColumnRef(name="id", table="u")
        assert col.name == "id"
        assert col.table == "u"

    def test_column_ref_evaluate_ignores_table(self):
        """ColumnRef.evaluate uses name only (table is for parser/planner)."""
        col = ColumnRef(name="id", table="u")
        assert col.evaluate({"id": 42}) == 42
