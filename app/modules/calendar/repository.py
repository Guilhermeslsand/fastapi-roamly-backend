from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domains.shared.enums import PurchaseStatus
from app.modules import models as _registered_models  # noqa: F401 — registra todos os relacionamentos ORM
from app.modules.packages.models import TravelPackageModel
from app.modules.purchases.models import PurchaseModel


class CalendarRepository:
    """Consultas de compras que ocupam um intervalo do calendário do cliente."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_trips(
        self, *, user_id: UUID, start_date: date, end_date: date
    ) -> list[PurchaseModel]:
        statement = (
            select(PurchaseModel)
            .options(
                selectinload(PurchaseModel.package).selectinload(TravelPackageModel.origin),
                selectinload(PurchaseModel.package).selectinload(TravelPackageModel.destination),
            )
            .where(
                PurchaseModel.user_id == user_id,
                PurchaseModel.status.in_([PurchaseStatus.CONFIRMED, PurchaseStatus.COMPLETED]),
                PurchaseModel.departure_date <= end_date,
                PurchaseModel.return_date >= start_date,
            )
            .order_by(PurchaseModel.departure_date.asc(), PurchaseModel.id.asc())
        )
        return list(self.db.scalars(statement).unique().all())
