from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.modules.destinations.repository import DestinationRepository
from app.modules.packages.repository import PackageRepository
from app.modules.packages.schemas import PackageSearchParams


class _ScalarResult:
    def all(self):
        return []

    def unique(self):
        return self


class _CompileOnlySession:
    """Captura e compila statements sem exigir um PostgreSQL em execução."""

    def __init__(self):
        self.statements = []

    def scalars(self, statement):
        statement.compile(dialect=postgresql.dialect())
        self.statements.append(statement)
        return _ScalarResult()

    def scalar(self, statement):
        statement.compile(dialect=postgresql.dialect())
        self.statements.append(statement)
        return 0


def test_package_search_query_compiles_with_all_filters():
    db = _CompileOnlySession()
    repository = PackageRepository(db)
    params = PackageSearchParams(
        q="Rio",
        origin_id=uuid4(),
        destination_id=uuid4(),
        departure_from=date(2026, 12, 1),
        departure_to=date(2026, 12, 31),
        min_price=Decimal("500.00"),
        max_price=Decimal("3000.00"),
        min_days=3,
        max_days=10,
        page=2,
        limit=10,
        sort_by="price",
        sort_order="asc",
    )

    items, total = repository.search(params, public_only=True)

    assert items == []
    assert total == 0
    assert len(db.statements) == 2


def test_destination_list_query_compiles():
    db = _CompileOnlySession()
    repository = DestinationRepository(db)

    items, total = repository.list_destinations(
        page=1,
        limit=20,
        q="Brasil",
        country="Brasil",
        state="SP",
        is_active=True,
        sort_order="desc",
    )

    assert items == []
    assert total == 0
    assert len(db.statements) == 2
