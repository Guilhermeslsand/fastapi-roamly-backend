from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.domains.shared.enums import PaymentMethod, PaymentStatus, PurchaseStatus
from app.modules.destinations.models import DestinationModel
from app.modules.packages.models import TravelPackageModel
from app.modules.purchases.models import PaymentModel, PurchaseModel
from app.modules.purchases.schemas import CheckoutRequest
from app.modules.purchases.service import PurchaseService


class FakeDB:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakePurchaseRepository:
    def __init__(self, db):
        self.db = db
        origin = DestinationModel(
            id=uuid4(), name="São Paulo", country="Brasil", state="SP"
        )
        destination = DestinationModel(
            id=uuid4(), name="Rio de Janeiro", country="Brasil", state="RJ"
        )
        self.package = TravelPackageModel(
            id=uuid4(),
            title="Rio de Janeiro",
            origin_id=origin.id,
            destination_id=destination.id,
            departure_date=date.today() + timedelta(days=30),
            return_date=date.today() + timedelta(days=35),
            price=Decimal("1250.00"),
            cost_price=Decimal("900.00"),
            total_seats=5,
            available_seats=5,
            is_active=True,
            created_by=uuid4(),
            origin=origin,
            destination=destination,
        )
        self.purchases = []
        self.overlap = False

    def get_by_idempotency_key(self, *, user_id, idempotency_key):
        return next(
            (p for p in self.purchases if p.user_id == user_id and p.idempotency_key == idempotency_key),
            None,
        )

    def get_package_for_update(self, package_id):
        return self.package if package_id == self.package.id else None

    def has_overlapping_confirmed_purchase(self, **kwargs):
        return self.overlap

    def create(self, purchase, payment):
        now = datetime.now(timezone.utc)
        purchase.created_at = now
        purchase.updated_at = now
        purchase.package = self.package
        payment.id = uuid4()
        payment.created_at = now
        payment.updated_at = now
        purchase.payment = payment
        assert payment.purchase_id == purchase.id
        self.purchases.append(purchase)

    def get_for_user(self, *, purchase_id, user_id):
        return next(
            (p for p in self.purchases if p.id == purchase_id and p.user_id == user_id),
            None,
        )

    def get_reference_for_user(self, *, purchase_id, user_id):
        return self.get_for_user(purchase_id=purchase_id, user_id=user_id)

    def get_for_user_for_update(self, *, purchase_id, user_id):
        return self.get_for_user(purchase_id=purchase_id, user_id=user_id)


def make_request(package_id, quantity=1):
    return CheckoutRequest(
        package_id=package_id,
        quantity=quantity,
        card={
            "cardholder_name": "Cliente Teste",
            "card_number": "CARD-SIMULADO",
            "expiry_month": "MM",
            "expiry_year": "YYYY",
            "cvv": "CVV-SIMULADO",
        },
    )


class FakeCache:
    def __init__(self):
        self.invalidated = []

    def invalidate_prefix(self, prefix):
        self.invalidated.append(prefix)


def test_checkout_confirms_payment_and_decrements_inventory(monkeypatch):
    monkeypatch.setattr("app.modules.purchases.service.PurchaseRepository", FakePurchaseRepository)
    db = FakeDB()
    cache = FakeCache()
    service = PurchaseService(db, cache=cache)
    user_id = uuid4()

    result = service.checkout(
        user_id=user_id,
        data=make_request(service.repository.package.id, quantity=2),
        idempotency_key="checkout-intent-0001",
    )

    assert result.status is PurchaseStatus.CONFIRMED
    assert result.total_amount == Decimal("2500.00")
    assert result.payment.status is PaymentStatus.APPROVED
    assert service.repository.package.available_seats == 3
    assert db.commits == 1
    assert result.id == service.repository.purchases[0].id
    assert cache.invalidated == ["packages"]


def test_checkout_replays_same_idempotency_key_without_charging_twice(monkeypatch):
    monkeypatch.setattr("app.modules.purchases.service.PurchaseRepository", FakePurchaseRepository)
    db = FakeDB()
    service = PurchaseService(db)
    user_id = uuid4()
    request = make_request(service.repository.package.id, quantity=1)

    first = service.checkout(user_id=user_id, data=request, idempotency_key="checkout-intent-0002")
    second = service.checkout(user_id=user_id, data=request, idempotency_key="checkout-intent-0002")

    assert first.id == second.id
    assert len(service.repository.purchases) == 1
    assert service.repository.package.available_seats == 4
    assert db.commits == 1


def test_checkout_rejects_idempotency_key_reused_for_different_intent(monkeypatch):
    monkeypatch.setattr("app.modules.purchases.service.PurchaseRepository", FakePurchaseRepository)
    service = PurchaseService(FakeDB())
    user_id = uuid4()
    service.checkout(
        user_id=user_id,
        data=make_request(service.repository.package.id, quantity=1),
        idempotency_key="checkout-intent-0003",
    )

    with pytest.raises(HTTPException) as exc:
        service.checkout(
            user_id=user_id,
            data=make_request(service.repository.package.id, quantity=2),
            idempotency_key="checkout-intent-0003",
        )
    assert exc.value.status_code == 409


def test_checkout_rejects_date_overlap_before_creating_purchase(monkeypatch):
    monkeypatch.setattr("app.modules.purchases.service.PurchaseRepository", FakePurchaseRepository)
    service = PurchaseService(FakeDB())
    service.repository.overlap = True

    with pytest.raises(HTTPException) as exc:
        service.checkout(
            user_id=uuid4(),
            data=make_request(service.repository.package.id),
            idempotency_key="checkout-intent-0004",
        )
    assert exc.value.status_code == 409
    assert service.repository.purchases == []


def test_checkout_rejects_insufficient_seats(monkeypatch):
    monkeypatch.setattr("app.modules.purchases.service.PurchaseRepository", FakePurchaseRepository)
    service = PurchaseService(FakeDB())
    service.repository.package.available_seats = 1

    with pytest.raises(HTTPException) as exc:
        service.checkout(
            user_id=uuid4(),
            data=make_request(service.repository.package.id, quantity=2),
            idempotency_key="checkout-intent-0005",
        )
    assert exc.value.status_code == 409
    assert service.repository.purchases == []


def test_cancel_marks_purchase_and_payment_refunded_and_returns_seats(monkeypatch):
    monkeypatch.setattr("app.modules.purchases.service.PurchaseRepository", FakePurchaseRepository)
    db = FakeDB()
    service = PurchaseService(db)
    user_id = uuid4()
    package = service.repository.package
    now = datetime.now(timezone.utc)
    purchase_id = uuid4()
    purchase = PurchaseModel(
        id=purchase_id,
        user_id=user_id,
        package_id=package.id,
        quantity=2,
        total_amount=Decimal("2500.00"),
        cost_amount=Decimal("1800.00"),
        departure_date=package.departure_date,
        return_date=package.return_date,
        status=PurchaseStatus.CONFIRMED,
        purchased_at=now,
    )
    purchase.created_at = now
    purchase.updated_at = now
    purchase.package = package
    payment = PaymentModel(
        id=uuid4(),
        purchase_id=purchase_id,
        amount=Decimal("2500.00"),
        method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.APPROVED,
        transaction_reference="SIM-TEST",
        paid_at=now,
    )
    payment.created_at = now
    payment.updated_at = now
    purchase.payment = payment
    service.repository.purchases.append(purchase)
    package.available_seats = 3

    result = service.cancel_my_purchase(purchase_id=purchase_id, user_id=user_id)

    assert result.status is PurchaseStatus.CANCELLED
    assert result.payment.status is PaymentStatus.REFUNDED
    assert package.available_seats == 5
    assert db.commits == 1


def test_cancel_rejects_a_trip_that_has_already_started(monkeypatch):
    monkeypatch.setattr("app.modules.purchases.service.PurchaseRepository", FakePurchaseRepository)
    service = PurchaseService(FakeDB())
    user_id = uuid4()
    package = service.repository.package
    now = datetime.now(timezone.utc)
    purchase_id = uuid4()
    purchase = PurchaseModel(
        id=purchase_id,
        user_id=user_id,
        package_id=package.id,
        quantity=1,
        total_amount=Decimal("1250.00"),
        cost_amount=Decimal("900.00"),
        departure_date=date.today(),
        return_date=date.today() + timedelta(days=4),
        status=PurchaseStatus.CONFIRMED,
        purchased_at=now,
    )
    purchase.package = package
    purchase.payment = PaymentModel(
        id=uuid4(), purchase_id=purchase_id, amount=Decimal("1250.00"),
        method=PaymentMethod.CREDIT_CARD, status=PaymentStatus.APPROVED, transaction_reference="SIM-TEST-2", paid_at=now,
    )
    service.repository.purchases.append(purchase)

    with pytest.raises(HTTPException) as exc:
        service.cancel_my_purchase(purchase_id=purchase_id, user_id=user_id)
    assert exc.value.status_code == 409


def test_cancel_does_not_reveal_another_users_purchase(monkeypatch):
    monkeypatch.setattr("app.modules.purchases.service.PurchaseRepository", FakePurchaseRepository)
    service = PurchaseService(FakeDB())

    with pytest.raises(HTTPException) as exc:
        service.cancel_my_purchase(purchase_id=uuid4(), user_id=uuid4())
    assert exc.value.status_code == 404
