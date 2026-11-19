from datetime import date
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.modules.calendar.repository import CalendarRepository


class FakeScalarResult:
    def unique(self):
        return self

    def all(self):
        return []


class CapturingDB:
    statement = None

    def scalars(self, statement):
        self.statement = statement
        return FakeScalarResult()


def test_calendar_query_compiles_for_postgresql_and_filters_by_owner_and_overlap():
    db = CapturingDB()
    repository = CalendarRepository(db)
    user_id = uuid4()
    repository.list_trips(
        user_id=user_id,
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 30),
    )
    compiled = str(db.statement.compile(dialect=postgresql.dialect()))
    assert "purchases.user_id" in compiled
    assert "purchases.departure_date" in compiled
    assert "purchases.return_date" in compiled
    assert "status" in compiled
    assert "status" in compiled
    assert any("CONFIRMED" in str(value) or "COMPLETED" in str(value) for value in db.statement.compile(dialect=postgresql.dialect()).params.values())
