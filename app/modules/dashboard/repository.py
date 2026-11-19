from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, cast, func, select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.types import Date

from app.core.config import settings
from app.domains.shared.enums import PaymentStatus, PurchaseStatus, UserRole
from app.modules.destinations.models import DestinationModel
from app.modules.packages.models import TravelPackageModel
from app.modules.purchases.models import PaymentModel, PurchaseModel
from app.modules.users.models import UserModel

SUCCESSFUL_PURCHASE_STATUSES = (PurchaseStatus.CONFIRMED, PurchaseStatus.COMPLETED)


class DashboardRepository:
    """Consultas agregadas do dashboard. Não contém regras de apresentação."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _sales_filters(start_at: datetime, end_exclusive: datetime) -> list:
        return [
            PurchaseModel.purchased_at >= start_at,
            PurchaseModel.purchased_at < end_exclusive,
            PurchaseModel.status.in_(SUCCESSFUL_PURCHASE_STATUSES),
            PaymentModel.status == PaymentStatus.APPROVED,
        ]

    @staticmethod
    def _aggregate_columns():
        missing_cost = case((PurchaseModel.cost_amount.is_(None), 1), else_=0)
        known_profit = case(
            (PurchaseModel.cost_amount.is_not(None), PurchaseModel.total_amount - PurchaseModel.cost_amount),
            else_=Decimal("0.00"),
        )
        return (
            func.count(PurchaseModel.id),
            func.coalesce(func.sum(PurchaseModel.total_amount), Decimal("0.00")),
            func.coalesce(func.sum(PurchaseModel.quantity), 0),
            func.coalesce(func.sum(missing_cost), 0),
            func.coalesce(func.sum(known_profit), Decimal("0.00")),
        )

    def overview(self, *, start_at: datetime, end_exclusive: datetime) -> dict:
        sales_count_col, revenue_col, units_col, missing_cost_col, known_profit_col = self._aggregate_columns()
        statement = (
            select(
                sales_count_col.label("sales_count"),
                revenue_col.label("revenue"),
                units_col.label("units_sold"),
                missing_cost_col.label("purchases_without_cost"),
                known_profit_col.label("known_profit"),
            )
            .select_from(PurchaseModel)
            .join(PaymentModel, PaymentModel.purchase_id == PurchaseModel.id)
            .where(*self._sales_filters(start_at, end_exclusive))
        )
        row = self.db.execute(statement).mappings().one()

        active_clients = self.db.scalar(
            select(func.count(UserModel.id)).where(
                UserModel.role == UserRole.CLIENT,
                UserModel.is_active.is_(True),
            )
        ) or 0
        new_clients = self.db.scalar(
            select(func.count(UserModel.id)).where(
                UserModel.role == UserRole.CLIENT,
                UserModel.created_at >= start_at,
                UserModel.created_at < end_exclusive,
            )
        ) or 0

        revenue = Decimal(row["revenue"] or 0)
        sales_count = int(row["sales_count"] or 0)
        missing_cost = int(row["purchases_without_cost"] or 0)
        return {
            "sales_count": sales_count,
            "revenue": revenue,
            "units_sold": int(row["units_sold"] or 0),
            "purchases_without_cost": missing_cost,
            "known_profit": Decimal(row["known_profit"] or 0),
            "active_clients": int(active_clients),
            "new_clients": int(new_clients),
        }

    def revenue_series(
        self, *, start_at: datetime, end_exclusive: datetime, group_by: str
    ) -> list[dict]:
        period = cast(
            func.date_trunc(
                group_by,
                func.timezone(settings.app_timezone, PurchaseModel.purchased_at),
            ),
            Date,
        ).label("period")
        sales_count_col, revenue_col, _units_col, missing_cost_col, known_profit_col = self._aggregate_columns()
        statement = (
            select(
                period,
                revenue_col.label("revenue"),
                missing_cost_col.label("purchases_without_cost"),
                known_profit_col.label("known_profit"),
            )
            .select_from(PurchaseModel)
            .join(PaymentModel, PaymentModel.purchase_id == PurchaseModel.id)
            .where(*self._sales_filters(start_at, end_exclusive))
            .group_by(period)
            .order_by(period.asc())
        )
        rows = self.db.execute(statement).mappings().all()
        return [dict(row) for row in rows]

    def sales_series(
        self, *, start_at: datetime, end_exclusive: datetime, group_by: str
    ) -> list[dict]:
        period = cast(
            func.date_trunc(
                group_by,
                func.timezone(settings.app_timezone, PurchaseModel.purchased_at),
            ),
            Date,
        ).label("period")
        statement = (
            select(
                period,
                func.count(PurchaseModel.id).label("sales_count"),
                func.coalesce(func.sum(PurchaseModel.quantity), 0).label("units_sold"),
            )
            .select_from(PurchaseModel)
            .join(PaymentModel, PaymentModel.purchase_id == PurchaseModel.id)
            .where(*self._sales_filters(start_at, end_exclusive))
            .group_by(period)
            .order_by(period.asc())
        )
        return [dict(row) for row in self.db.execute(statement).mappings().all()]

    def top_destinations(
        self, *, start_at: datetime, end_exclusive: datetime, limit: int
    ) -> list[dict]:
        statement = (
            select(
                DestinationModel.id.label("destination_id"),
                DestinationModel.name.label("destination_name"),
                DestinationModel.country.label("country"),
                func.count(PurchaseModel.id).label("sales_count"),
                func.coalesce(func.sum(PurchaseModel.quantity), 0).label("units_sold"),
                func.coalesce(func.sum(PurchaseModel.total_amount), Decimal("0.00")).label("revenue"),
            )
            .select_from(PurchaseModel)
            .join(PaymentModel, PaymentModel.purchase_id == PurchaseModel.id)
            .join(TravelPackageModel, TravelPackageModel.id == PurchaseModel.package_id)
            .join(DestinationModel, DestinationModel.id == TravelPackageModel.destination_id)
            .where(*self._sales_filters(start_at, end_exclusive))
            .group_by(DestinationModel.id, DestinationModel.name, DestinationModel.country)
            .order_by(func.sum(PurchaseModel.quantity).desc(), func.sum(PurchaseModel.total_amount).desc())
            .limit(limit)
        )
        return [dict(row) for row in self.db.execute(statement).mappings().all()]

    def top_packages(
        self, *, start_at: datetime, end_exclusive: datetime, limit: int
    ) -> list[dict]:
        origin = aliased(DestinationModel, name="origin_destination")
        destination = aliased(DestinationModel, name="package_destination")
        statement = (
            select(
                TravelPackageModel.id.label("package_id"),
                TravelPackageModel.title.label("title"),
                TravelPackageModel.total_seats.label("total_seats"),
                TravelPackageModel.available_seats.label("available_seats"),
                origin.name.label("origin"),
                destination.name.label("destination"),
                func.count(PurchaseModel.id).label("sales_count"),
                func.coalesce(func.sum(PurchaseModel.quantity), 0).label("units_sold"),
                func.coalesce(func.sum(PurchaseModel.total_amount), Decimal("0.00")).label("revenue"),
            )
            .select_from(PurchaseModel)
            .join(PaymentModel, PaymentModel.purchase_id == PurchaseModel.id)
            .join(TravelPackageModel, TravelPackageModel.id == PurchaseModel.package_id)
            .join(origin, origin.id == TravelPackageModel.origin_id)
            .join(destination, destination.id == TravelPackageModel.destination_id)
            .where(*self._sales_filters(start_at, end_exclusive))
            .group_by(
                TravelPackageModel.id,
                TravelPackageModel.title,
                TravelPackageModel.total_seats,
                TravelPackageModel.available_seats,
                origin.name,
                destination.name,
            )
            .order_by(func.sum(PurchaseModel.quantity).desc(), func.sum(PurchaseModel.total_amount).desc())
            .limit(limit)
        )
        rows = [dict(row) for row in self.db.execute(statement).mappings().all()]
        for row in rows:
            row["occupancy_rate"] = (
                Decimal(row["total_seats"] - row["available_seats"])
                * Decimal("100")
                / Decimal(row["total_seats"])
            ).quantize(Decimal("0.01"))
        return rows
