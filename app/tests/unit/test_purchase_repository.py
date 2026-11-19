from datetime import date
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.domains.shared.enums import PurchaseStatus
from app.modules.purchases.repository import PurchaseRepository


class StatementCapture:
    def __init__(self):
        self.statement = None

    def scalar(self, statement):
        self.statement = statement
        return None


def test_overlap_query_uses_inclusive_date_intersection_and_confirmed_statuses():
    db = StatementCapture()
    repository = PurchaseRepository(db)
    repository.has_overlapping_confirmed_purchase(
        user_id=uuid4(),
        departure_date=date(2026, 12, 10),
        return_date=date(2026, 12, 18),
    )
    sql = str(db.statement.compile(dialect=postgresql.dialect()))
    assert "purchases.departure_date <=" in sql
    assert "purchases.return_date >=" in sql
    assert "purchases.status IN" in sql


def test_purchase_model_has_idempotency_unique_constraint():
    from app.modules.purchases.models import PurchaseModel

    constraint_names = {constraint.name for constraint in PurchaseModel.__table__.constraints}
    assert "uq_purchases_user_idempotency_key" in constraint_names


def test_package_lock_uses_for_update():
    from app.modules.packages.repository import PackageRepository

    db = StatementCapture()
    repository = PackageRepository(db)
    repository.get_by_id_for_update(uuid4())
    sql = str(db.statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE OF travel_packages" in sql
