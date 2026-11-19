from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.domains.shared.enums import UserRole
from app.modules.purchases.service import PurchaseService


class FakeDB:
    pass


class FakeUserRepository:
    def __init__(self, _db):
        self.customer_id = None

    def get_client_by_id(self, user_id):
        return object() if user_id == self.customer_id else None


class FakePurchaseRepository:
    def __init__(self, _db):
        self.args = None

    def list_for_user(self, **kwargs):
        self.args = kwargs
        return [], 0


def build_service(monkeypatch):
    monkeypatch.setattr("app.modules.purchases.service.UserRepository", FakeUserRepository)
    monkeypatch.setattr("app.modules.purchases.service.PurchaseRepository", FakePurchaseRepository)
    service = PurchaseService(FakeDB())
    service.users.customer_id = uuid4()
    return service


def test_admin_can_list_customer_purchase_history(monkeypatch):
    service = build_service(monkeypatch)
    result = service.list_customer_purchases(
        customer_id=service.users.customer_id,
        page=2,
        limit=10,
        departure_from=date(2026, 12, 1),
    )
    assert result.total == 0
    assert result.pages == 0
    assert service.repository.args["page"] == 2
    assert service.repository.args["departure_from"] == date(2026, 12, 1)


def test_admin_purchase_history_hides_non_client_ids(monkeypatch):
    service = build_service(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.list_customer_purchases(customer_id=uuid4(), page=1, limit=20)
    assert exc.value.status_code == 404


def test_admin_purchase_history_validates_departure_filter(monkeypatch):
    service = build_service(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.list_customer_purchases(
            customer_id=service.users.customer_id,
            page=1,
            limit=20,
            departure_from=date(2026, 12, 10),
            departure_to=date(2026, 12, 1),
        )
    assert exc.value.status_code == 422
