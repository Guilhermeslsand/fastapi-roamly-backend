from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.destinations.models import DestinationModel


class DestinationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, destination_id: UUID) -> DestinationModel | None:
        return self.db.scalar(
            select(DestinationModel).where(DestinationModel.id == destination_id)
        )

    def find_duplicate(
        self,
        *,
        name: str,
        country: str,
        state: str | None,
        exclude_id: UUID | None = None,
    ) -> DestinationModel | None:
        statement = select(DestinationModel).where(
            func.lower(DestinationModel.name) == name.lower(),
            func.lower(DestinationModel.country) == country.lower(),
        )
        if state is None:
            statement = statement.where(DestinationModel.state.is_(None))
        else:
            statement = statement.where(func.lower(DestinationModel.state) == state.lower())
        if exclude_id is not None:
            statement = statement.where(DestinationModel.id != exclude_id)
        return self.db.scalar(statement.limit(1))

    def list_destinations(
        self,
        *,
        page: int,
        limit: int,
        q: str | None = None,
        country: str | None = None,
        state: str | None = None,
        is_active: bool | None = True,
        sort_order: str = "asc",
    ) -> tuple[list[DestinationModel], int]:
        statement = select(DestinationModel)
        count_statement = select(func.count()).select_from(DestinationModel)

        filters = []
        if is_active is not None:
            filters.append(DestinationModel.is_active.is_(is_active))
        if q:
            term = f"%{q.strip()}%"
            filters.append(
                or_(
                    DestinationModel.name.ilike(term),
                    DestinationModel.country.ilike(term),
                    DestinationModel.state.ilike(term),
                )
            )
        if country:
            filters.append(DestinationModel.country.ilike(f"%{country.strip()}%"))
        if state:
            filters.append(DestinationModel.state.ilike(f"%{state.strip()}%"))

        if filters:
            statement = statement.where(*filters)
            count_statement = count_statement.where(*filters)

        order_column = DestinationModel.name
        order_expression = order_column.asc() if sort_order == "asc" else order_column.desc()
        statement = (
            statement.order_by(order_expression, DestinationModel.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        items = list(self.db.scalars(statement).all())
        total = int(self.db.scalar(count_statement) or 0)
        return items, total

    def has_active_packages(self, destination_id: UUID) -> bool:
        from app.modules.packages.models import TravelPackageModel

        return self.db.scalar(
            select(TravelPackageModel.id)
            .where(
                TravelPackageModel.is_active.is_(True),
                or_(
                    TravelPackageModel.origin_id == destination_id,
                    TravelPackageModel.destination_id == destination_id,
                ),
            )
            .limit(1)
        ) is not None

    def create(self, destination: DestinationModel) -> DestinationModel:
        self.db.add(destination)
        self.db.flush()
        return destination

    def flush(self) -> None:
        self.db.flush()
