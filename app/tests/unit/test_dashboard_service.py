from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.modules.dashboard.service import DashboardService


class FakeDB:
    pass


class FakeDashboardRepository:
    def __init__(self, _db):
        self.period_args = None

    def overview(self, *, start_at, end_exclusive):
        self.period_args = (start_at, end_exclusive)
        return {
            "sales_count": 4,
            "revenue": Decimal("1200.00"),
            "units_sold": 7,
            "purchases_without_cost": 0,
            "known_profit": Decimal("350.00"),
            "active_clients": 25,
            "new_clients": 3,
        }

    def revenue_series(self, **kwargs):
        self.period_args = kwargs
        return [{
            "period": date(2026, 11, 1),
            "revenue": Decimal("1200.00"),
            "purchases_without_cost": 0,
            "known_profit": Decimal("350.00"),
        }]

    def sales_series(self, **kwargs):
        self.period_args = kwargs
        return [{"period": date(2026, 11, 1), "sales_count": 4, "units_sold": 7}]

    def top_destinations(self, **kwargs):
        self.period_args = kwargs
        return [{
            "destination_id": "85a7a236-b3ae-4ddc-aae4-cbad9c3d2857",
            "destination_name": "Rio de Janeiro",
            "country": "Brasil",
            "sales_count": 4,
            "units_sold": 7,
            "revenue": Decimal("1200.00"),
        }]

    def top_packages(self, **kwargs):
        self.period_args = kwargs
        return [{
            "package_id": "85a7a236-b3ae-4ddc-aae4-cbad9c3d2857",
            "title": "Fim de semana no Rio",
            "origin": "São Paulo",
            "destination": "Rio de Janeiro",
            "sales_count": 4,
            "units_sold": 7,
            "revenue": Decimal("1200.00"),
            "total_seats": 10,
            "available_seats": 3,
            "occupancy_rate": Decimal("70.00"),
        }]


def build_service(monkeypatch):
    monkeypatch.setattr("app.modules.dashboard.service.DashboardRepository", FakeDashboardRepository)
    monkeypatch.setattr("app.modules.dashboard.service.business_date", lambda: date(2026, 11, 18))
    return DashboardService(FakeDB())


def test_overview_defaults_to_current_month(monkeypatch):
    service = build_service(monkeypatch)
    result = service.overview(start_date=None, end_date=None)
    assert result.period.start_date == date(2026, 11, 1)
    assert result.period.end_date == date(2026, 11, 30)
    assert result.revenue == Decimal("1200.00")
    assert result.gross_profit == Decimal("350.00")
    assert result.average_ticket == Decimal("300.00")
    assert result.units_sold == 7


def test_partial_dashboard_period_is_rejected(monkeypatch):
    service = build_service(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.overview(start_date=date(2026, 11, 1), end_date=None)
    assert exc.value.status_code == 422


def test_revenue_series_maps_aggregated_rows(monkeypatch):
    service = build_service(monkeypatch)
    result = service.revenue_series(
        start_date=date(2026, 11, 1), end_date=date(2026, 11, 30), group_by="month"
    )
    assert result.items[0].period == date(2026, 11, 1)
    assert result.items[0].gross_profit == Decimal("350.00")


def test_daily_series_rejects_period_over_93_days(monkeypatch):
    service = build_service(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.sales_series(
            start_date=date(2026, 1, 1), end_date=date(2026, 4, 10), group_by="day"
        )
    assert exc.value.status_code == 422


def test_top_packages_returns_current_occupancy(monkeypatch):
    service = build_service(monkeypatch)
    result = service.top_packages(
        start_date=date(2026, 11, 1), end_date=date(2026, 11, 30), limit=5
    )
    assert result.items[0].occupancy_rate == Decimal("70.00")


def test_overview_does_not_report_incomplete_profit_as_zero(monkeypatch):
    service = build_service(monkeypatch)
    service.repository.overview = lambda **_: {
        "sales_count": 1,
        "revenue": Decimal("500.00"),
        "units_sold": 1,
        "purchases_without_cost": 1,
        "known_profit": Decimal("0.00"),
        "active_clients": 10,
        "new_clients": 1,
    }
    result = service.overview(start_date=date(2026, 11, 1), end_date=date(2026, 11, 30))
    assert result.gross_profit is None
    assert result.profit_data_complete is False


def test_monthly_series_fills_months_without_sales(monkeypatch):
    service = build_service(monkeypatch)
    service.repository.sales_series = lambda **_: [
        {"period": date(2026, 11, 1), "sales_count": 2, "units_sold": 3}
    ]
    result = service.sales_series(
        start_date=date(2026, 10, 15), end_date=date(2026, 12, 4), group_by="month"
    )
    assert [item.period for item in result.items] == [
        date(2026, 10, 1), date(2026, 11, 1), date(2026, 12, 1)
    ]
    assert [item.sales_count for item in result.items] == [0, 2, 0]
