from datetime import date

from sqlalchemy.dialects import postgresql

from app.modules.users.repository import UserRepository


class ScalarRows:
    def all(self):
        return []


class FakeDB:
    def __init__(self):
        self.statements = []

    def scalars(self, statement):
        self.statements.append(statement)
        statement.compile(dialect=postgresql.dialect())
        return ScalarRows()

    def scalar(self, statement):
        self.statements.append(statement)
        statement.compile(dialect=postgresql.dialect())
        return 0

    def execute(self, statement):
        self.statements.append(statement)
        statement.compile(dialect=postgresql.dialect())
        return type("Result", (), {"one_or_none": lambda self: None})()


def test_customer_list_query_compiles_with_filters_and_pagination():
    db = FakeDB()
    repository = UserRepository(db)

    items, total = repository.list_clients(
        page=2,
        limit=15,
        search="529.982.247-25",
        is_active=True,
        created_from=date(2026, 1, 1),
        created_to=date(2026, 12, 31),
        sort_by="name",
        sort_order="asc",
    )

    assert items == []
    assert total == 0
    assert len(db.statements) == 2


def test_customer_detail_query_compiles_with_purchase_aggregate():
    db = FakeDB()
    repository = UserRepository(db)
    assert repository.get_client_detail(__import__("uuid").uuid4()) is None
    assert len(db.statements) == 1
