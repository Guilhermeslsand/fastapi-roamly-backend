from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.dialects import postgresql

from app.modules.dashboard.repository import DashboardRepository


class FakeMappings:
    def one(self):
        return {
            "sales_count": 0,
            "revenue": Decimal("0.00"),
            "units_sold": 0,
            "purchases_without_cost": 0,
            "known_profit": Decimal("0.00"),
        }

    def all(self):
        return []


class FakeResult:
    def mappings(self):
        return FakeMappings()


class CapturingDB:
    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        return FakeResult()

    def scalar(self, statement):
        self.statements.append(statement)
        return 0


def test_dashboard_queries_compile_for_postgresql():
    db = CapturingDB()
    repository = DashboardRepository(db)
    start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    end = datetime(2026, 12, 1, tzinfo=timezone.utc)

    repository.overview(start_at=start, end_exclusive=end)
    repository.revenue_series(start_at=start, end_exclusive=end, group_by="month")
    repository.sales_series(start_at=start, end_exclusive=end, group_by="day")
    repository.top_destinations(start_at=start, end_exclusive=end, limit=5)
    repository.top_packages(start_at=start, end_exclusive=end, limit=10)

    assert len(db.statements) == 7
    for statement in db.statements:
        compiled = str(statement.compile(dialect=postgresql.dialect()))
        assert "purchases" in compiled or "users" in compiled
        assert "FROM" in compiled
