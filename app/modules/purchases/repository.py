from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domains.shared.enums import PurchaseStatus
from app.modules.packages.models import TravelPackageModel
from app.modules.purchases.models import PaymentModel, PurchaseModel


class PurchaseRepository:
    """Persistência de compras; não contém regras de negócio."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _purchase_options():
        return (
            selectinload(PurchaseModel.payment),
            selectinload(PurchaseModel.package).selectinload(TravelPackageModel.origin),
            selectinload(PurchaseModel.package).selectinload(TravelPackageModel.destination),
        )

    def get_package_for_update(self, package_id: UUID) -> TravelPackageModel | None:
        statement = (
            select(TravelPackageModel)
            .where(TravelPackageModel.id == package_id)
            .with_for_update(of=TravelPackageModel)
        )
        return self.db.scalar(statement)

    def get_by_idempotency_key(
        self, *, user_id: UUID, idempotency_key: str
    ) -> PurchaseModel | None:
        statement = (
            select(PurchaseModel)
            .options(*self._purchase_options())
            .where(
                PurchaseModel.user_id == user_id,
                PurchaseModel.idempotency_key == idempotency_key,
            )
        )
        return self.db.scalar(statement)

    def has_overlapping_confirmed_purchase(
        self,
        *,
        user_id: UUID,
        departure_date: date,
        return_date: date,
    ) -> bool:
        statement = select(PurchaseModel.id).where(
            PurchaseModel.user_id == user_id,
            PurchaseModel.status.in_([PurchaseStatus.CONFIRMED, PurchaseStatus.COMPLETED]),
            PurchaseModel.departure_date <= return_date,
            PurchaseModel.return_date >= departure_date,
        ).limit(1)
        return self.db.scalar(statement) is not None

    def create(self, purchase: PurchaseModel, payment: PaymentModel) -> None:
        self.db.add(purchase)
        self.db.add(payment)
        self.db.flush()

    def get_for_user(self, *, purchase_id: UUID, user_id: UUID) -> PurchaseModel | None:
        statement = (
            select(PurchaseModel)
            .options(*self._purchase_options())
            .where(PurchaseModel.id == purchase_id, PurchaseModel.user_id == user_id)
        )
        return self.db.scalar(statement)

    def get_for_user_for_update(
        self, *, purchase_id: UUID, user_id: UUID
    ) -> PurchaseModel | None:
        statement = (
            select(PurchaseModel)
            .options(*self._purchase_options())
            .where(PurchaseModel.id == purchase_id, PurchaseModel.user_id == user_id)
            .with_for_update(of=PurchaseModel)
        )
        return self.db.scalar(statement)

    def get_reference_for_user(
        self, *, purchase_id: UUID, user_id: UUID
    ) -> PurchaseModel | None:
        return self.db.scalar(
            select(PurchaseModel).where(
                PurchaseModel.id == purchase_id,
                PurchaseModel.user_id == user_id,
            )
        )

    def list_for_user(
        self,
        *,
        user_id: UUID,
        page: int,
        limit: int,
        status: PurchaseStatus | None,
    ) -> tuple[list[PurchaseModel], int]:
        filters = [PurchaseModel.user_id == user_id]
        if status is not None:
            filters.append(PurchaseModel.status == status)

        statement = (
            select(PurchaseModel)
            .options(*self._purchase_options())
            .where(*filters)
            .order_by(PurchaseModel.purchased_at.desc(), PurchaseModel.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        count_statement = select(func.count()).select_from(PurchaseModel).where(*filters)
        items = list(self.db.scalars(statement).unique().all())
        total = int(self.db.scalar(count_statement) or 0)
        return items, total
