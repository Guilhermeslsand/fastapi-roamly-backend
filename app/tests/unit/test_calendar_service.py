from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.domains.shared.enums import PurchaseStatus
from app.modules.calendar.service import CalendarService


class FakeDB:
    pass


class FakeCalendarRepository:
    purchases = []

    def __init__(self, _db):
        self.args = None

    def list_trips(self, **kwargs):
        self.args = kwargs
        return self.purchases


def build_purchase(*, departure, returning, status=PurchaseStatus.CONFIRMED):
    destination_id = uuid4()
    origin_id = uuid4()
    return SimpleNamespace(
        id=uuid4(),
        package=SimpleNamespace(
            id=uuid4(),
            title="Pacote teste",
            origin=SimpleNamespace(id=origin_id, name="São Paulo", country="Brasil", state="SP"),
            destination=SimpleNamespace(id=destination_id, name="Rio de Janeiro", country="Brasil", state="RJ"),
        ),
        departure_date=departure,
        return_date=returning,
        quantity=2,
        total_amount=Decimal("2500.00"),
        status=status,
    )


def build_service(monkeypatch, purchases):
    FakeCalendarRepository.purchases = purchases
    monkeypatch.setattr("app.modules.calendar.service.CalendarRepository", FakeCalendarRepository)
    monkeypatch.setattr("app.modules.calendar.service.business_date", lambda: date(2026, 11, 18))
    return CalendarService(FakeDB())


def test_calendar_marks_each_day_inclusively_and_clips_to_requested_range(monkeypatch):
    purchase = build_purchase(
        departure=date(2026, 11, 15),
        returning=date(2026, 11, 20),
    )
    service = build_service(monkeypatch, [purchase])
    result = service.get_calendar(
        user_id=uuid4(),
        start_date=date(2026, 11, 17),
        end_date=date(2026, 11, 19),
    )
    assert len(result.trips) == 1
    assert result.trips[0].travel_status == "ONGOING"
    assert [item.date for item in result.days] == [
        date(2026, 11, 17), date(2026, 11, 18), date(2026, 11, 19)
    ]
    assert all(item.purchase_ids == [purchase.id] for item in result.days)


def test_calendar_classifies_future_and_completed_trips(monkeypatch):
    future = build_purchase(departure=date(2026, 12, 1), returning=date(2026, 12, 5))
    completed = build_purchase(
        departure=date(2026, 11, 1), returning=date(2026, 11, 5), status=PurchaseStatus.COMPLETED
    )
    service = build_service(monkeypatch, [future, completed])
    result = service.get_calendar(
        user_id=uuid4(), start_date=date(2026, 11, 1), end_date=date(2026, 12, 31)
    )
    assert {trip.travel_status for trip in result.trips} == {"COMPLETED", "UPCOMING"}


def test_calendar_defaults_to_current_month(monkeypatch):
    service = build_service(monkeypatch, [])
    result = service.get_calendar(user_id=uuid4(), start_date=None, end_date=None)
    assert result.start_date == date(2026, 11, 1)
    assert result.end_date == date(2026, 11, 30)


def test_calendar_requires_both_period_boundaries(monkeypatch):
    service = build_service(monkeypatch, [])
    with pytest.raises(HTTPException) as exc:
        service.get_calendar(user_id=uuid4(), start_date=date(2026, 11, 1), end_date=None)
    assert exc.value.status_code == 422


def test_calendar_rejects_period_longer_than_366_days(monkeypatch):
    service = build_service(monkeypatch, [])
    with pytest.raises(HTTPException) as exc:
        service.get_calendar(
            user_id=uuid4(), start_date=date(2026, 1, 1), end_date=date(2027, 1, 2)
        )
    assert exc.value.status_code == 422
