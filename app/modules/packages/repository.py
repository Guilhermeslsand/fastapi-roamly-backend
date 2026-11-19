from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.modules.destinations.models import DestinationModel
from app.modules.packages.models import TravelPackageModel
from app.modules.packages.schemas import PackageAdminSearchParams, PackageSearchParams


class PackageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _with_destinations(statement):
        return statement.options(
            selectinload(TravelPackageModel.origin),
            selectinload(TravelPackageModel.destination),
        )

    def get_by_id(self, package_id: UUID) -> TravelPackageModel | None:
        statement = self._with_destinations(
            select(TravelPackageModel).where(TravelPackageModel.id == package_id)
        )
        return self.db.scalar(statement)

    def get_public_by_id(self, package_id: UUID) -> TravelPackageModel | None:
        # Os dois relacionamentos usam a mesma tabela; os predicados são aplicados
        # separadamente via EXISTS para evitar joins ambíguos.
        statement = select(TravelPackageModel).where(
            TravelPackageModel.id == package_id,
            TravelPackageModel.is_active.is_(True),
            TravelPackageModel.origin.has(DestinationModel.is_active.is_(True)),
            TravelPackageModel.destination.has(DestinationModel.is_active.is_(True)),
        )
        return self.db.scalar(self._with_destinations(statement))

    def active_destinations_exist(self, destination_ids: set[UUID]) -> bool:
        if len(destination_ids) != 2:
            return False
        found = self.db.scalars(
            select(DestinationModel.id).where(
                DestinationModel.id.in_(destination_ids),
                DestinationModel.is_active.is_(True),
            )
        ).all()
        return len(set(found)) == 2

    def search(
        self,
        params: PackageSearchParams | PackageAdminSearchParams,
        *,
        public_only: bool,
    ) -> tuple[list[TravelPackageModel], int]:
        statement = select(TravelPackageModel)
        count_statement = select(func.count()).select_from(TravelPackageModel)
        filters = []

        if public_only:
            filters.extend(
                [
                    TravelPackageModel.is_active.is_(True),
                    TravelPackageModel.origin.has(DestinationModel.is_active.is_(True)),
                    TravelPackageModel.destination.has(DestinationModel.is_active.is_(True)),
                ]
            )
        elif getattr(params, "is_active", None) is not None:
            filters.append(TravelPackageModel.is_active.is_(params.is_active))

        if params.origin_id:
            filters.append(TravelPackageModel.origin_id == params.origin_id)
        if params.destination_id:
            filters.append(TravelPackageModel.destination_id == params.destination_id)
        if params.departure_from:
            filters.append(TravelPackageModel.departure_date >= params.departure_from)
        if params.departure_to:
            filters.append(TravelPackageModel.departure_date <= params.departure_to)
        if params.min_price is not None:
            filters.append(TravelPackageModel.price >= params.min_price)
        if params.max_price is not None:
            filters.append(TravelPackageModel.price <= params.max_price)

        # Dias de calendário: inclui tanto a data de partida quanto a de retorno.
        duration_expression = (
            TravelPackageModel.return_date - TravelPackageModel.departure_date + 1
        )
        if params.min_days is not None:
            filters.append(duration_expression >= params.min_days)
        if params.max_days is not None:
            filters.append(duration_expression <= params.max_days)

        if params.q:
            origin_alias = aliased(DestinationModel)
            destination_alias = aliased(DestinationModel)
            statement = statement.join(
                origin_alias, TravelPackageModel.origin_id == origin_alias.id
            ).join(
                destination_alias, TravelPackageModel.destination_id == destination_alias.id
            )
            count_statement = count_statement.join(
                origin_alias, TravelPackageModel.origin_id == origin_alias.id
            ).join(
                destination_alias, TravelPackageModel.destination_id == destination_alias.id
            )
            term = f"%{params.q.strip()}%"
            filters.append(
                or_(
                    TravelPackageModel.title.ilike(term),
                    TravelPackageModel.description.ilike(term),
                    origin_alias.name.ilike(term),
                    destination_alias.name.ilike(term),
                )
            )

        if filters:
            statement = statement.where(*filters)
            count_statement = count_statement.where(*filters)

        sort_columns = {
            "departure_date": TravelPackageModel.departure_date,
            "return_date": TravelPackageModel.return_date,
            "price": TravelPackageModel.price,
            "created_at": TravelPackageModel.created_at,
            "title": TravelPackageModel.title,
        }
        sort_column = sort_columns[params.sort_by]
        sort_expression = sort_column.asc() if params.sort_order == "asc" else sort_column.desc()

        statement = self._with_destinations(statement.order_by(sort_expression, TravelPackageModel.id.asc()))
        statement = statement.offset((params.page - 1) * params.limit).limit(params.limit)

        items = list(self.db.scalars(statement).unique().all())
        total = int(self.db.scalar(count_statement) or 0)
        return items, total

    def has_purchases(self, package_id: UUID) -> bool:
        from app.modules.purchases.models import PurchaseModel

        return self.db.scalar(
            select(PurchaseModel.id).where(PurchaseModel.package_id == package_id).limit(1)
        ) is not None

    def create(self, package: TravelPackageModel) -> TravelPackageModel:
        self.db.add(package)
        self.db.flush()
        return package

    def flush(self) -> None:
        self.db.flush()
