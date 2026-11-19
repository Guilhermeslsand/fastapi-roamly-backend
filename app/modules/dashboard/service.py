from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import (
    DashboardOverviewResponse,
    ReportPeriod,
    RevenuePoint,
    RevenueSeriesResponse,
    SalesPoint,
    SalesSeriesResponse,
    TopDestinationItem,
    TopDestinationsResponse,
    TopPackageItem,
    TopPackagesResponse,
)
from app.modules.purchases.service import business_date


class DashboardService:
    """Regras e composição dos indicadores administrativos."""

    def __init__(self, db: Session) -> None:
        self.repository = DashboardRepository(db)

    @staticmethod
    def resolve_period(start_date: date | None, end_date: date | None) -> tuple[date, date, datetime, datetime]:
        today = business_date()
        if start_date is None and end_date is None:
            start_date = today.replace(day=1)
            if today.month == 12:
                next_month = date(today.year + 1, 1, 1)
            else:
                next_month = date(today.year, today.month + 1, 1)
            end_date = next_month - timedelta(days=1)
        elif start_date is None or end_date is None:
            raise HTTPException(
                status_code=422,
                detail="Informe start_date e end_date juntos, ou omita ambos para utilizar o mês atual.",
            )

        if start_date is None or end_date is None:
            raise HTTPException(status_code=422, detail="Período inválido.")
        if start_date > end_date:
            raise HTTPException(status_code=422, detail="start_date não pode ser posterior a end_date.")
        if (end_date - start_date).days > 366 * 5:
            raise HTTPException(status_code=422, detail="O período máximo permitido é de cinco anos.")

        tz = ZoneInfo(settings.app_timezone)
        start_at = datetime.combine(start_date, time.min, tzinfo=tz)
        end_exclusive = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
        return start_date, end_date, start_at, end_exclusive

    def overview(self, *, start_date: date | None, end_date: date | None) -> DashboardOverviewResponse:
        start, end, start_at, end_exclusive = self.resolve_period(start_date, end_date)
        data = self.repository.overview(start_at=start_at, end_exclusive=end_exclusive)
        revenue = data["revenue"]
        sales_count = data["sales_count"]
        incomplete = data["purchases_without_cost"] > 0
        gross_profit = None if incomplete else data["known_profit"]
        average_ticket = (
            (revenue / sales_count).quantize(Decimal("0.01"))
            if sales_count
            else Decimal("0.00")
        )
        return DashboardOverviewResponse(
            period=ReportPeriod(start_date=start, end_date=end),
            revenue=revenue,
            gross_profit=gross_profit,
            profit_data_complete=not incomplete,
            purchases_without_cost=data["purchases_without_cost"],
            sales_count=sales_count,
            units_sold=data["units_sold"],
            average_ticket=average_ticket,
            active_clients=data["active_clients"],
            new_clients=data["new_clients"],
        )

    def revenue_series(
        self, *, start_date: date | None, end_date: date | None, group_by: str
    ) -> RevenueSeriesResponse:
        start, end, start_at, end_exclusive = self.resolve_period(start_date, end_date)
        self._validate_granularity(start, end, group_by)
        rows = self.repository.revenue_series(
            start_at=start_at, end_exclusive=end_exclusive, group_by=group_by
        )
        rows_by_period = {row["period"]: row for row in rows}
        items = []
        for bucket in self._period_buckets(start, end, group_by):
            row = rows_by_period.get(bucket)
            missing_cost = int(row["purchases_without_cost"] or 0) if row else 0
            items.append(
                RevenuePoint(
                    period=bucket,
                    revenue=Decimal(row["revenue"] or 0) if row else Decimal("0.00"),
                    gross_profit=(
                        None
                        if missing_cost
                        else (Decimal(row["known_profit"] or 0) if row else Decimal("0.00"))
                    ),
                    purchases_without_cost=missing_cost,
                )
            )
        return RevenueSeriesResponse(
            period=ReportPeriod(start_date=start, end_date=end), group_by=group_by, items=items
        )

    def sales_series(
        self, *, start_date: date | None, end_date: date | None, group_by: str
    ) -> SalesSeriesResponse:
        start, end, start_at, end_exclusive = self.resolve_period(start_date, end_date)
        self._validate_granularity(start, end, group_by)
        rows = self.repository.sales_series(
            start_at=start_at, end_exclusive=end_exclusive, group_by=group_by
        )
        rows_by_period = {row["period"]: row for row in rows}
        items = [
            SalesPoint(
                period=bucket,
                sales_count=int(rows_by_period[bucket]["sales_count"]) if bucket in rows_by_period else 0,
                units_sold=int(rows_by_period[bucket]["units_sold"]) if bucket in rows_by_period else 0,
            )
            for bucket in self._period_buckets(start, end, group_by)
        ]
        return SalesSeriesResponse(
            period=ReportPeriod(start_date=start, end_date=end),
            group_by=group_by,
            items=items,
        )

    def top_destinations(
        self, *, start_date: date | None, end_date: date | None, limit: int
    ) -> TopDestinationsResponse:
        start, end, start_at, end_exclusive = self.resolve_period(start_date, end_date)
        rows = self.repository.top_destinations(
            start_at=start_at, end_exclusive=end_exclusive, limit=limit
        )
        return TopDestinationsResponse(
            period=ReportPeriod(start_date=start, end_date=end),
            items=[TopDestinationItem(**row) for row in rows],
        )

    def top_packages(
        self, *, start_date: date | None, end_date: date | None, limit: int
    ) -> TopPackagesResponse:
        start, end, start_at, end_exclusive = self.resolve_period(start_date, end_date)
        rows = self.repository.top_packages(
            start_at=start_at, end_exclusive=end_exclusive, limit=limit
        )
        return TopPackagesResponse(
            period=ReportPeriod(start_date=start, end_date=end),
            items=[TopPackageItem(**row) for row in rows],
        )

    @staticmethod
    def _period_buckets(start: date, end: date, group_by: str) -> list[date]:
        """Gera todos os dias/meses do intervalo, inclusive períodos sem vendas."""
        if group_by == "day":
            return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]

        cursor = date(start.year, start.month, 1)
        last = date(end.year, end.month, 1)
        buckets: list[date] = []
        while cursor <= last:
            buckets.append(cursor)
            if cursor.month == 12:
                cursor = date(cursor.year + 1, 1, 1)
            else:
                cursor = date(cursor.year, cursor.month + 1, 1)
        return buckets

    @staticmethod
    def _validate_granularity(start: date, end: date, group_by: str) -> None:
        if group_by not in {"day", "month"}:
            raise HTTPException(status_code=422, detail="group_by deve ser 'day' ou 'month'.")
        if group_by == "day" and (end - start).days > 92:
            raise HTTPException(
                status_code=422,
                detail="A granularidade diária aceita períodos de até 93 dias; utilize group_by=month.",
            )
