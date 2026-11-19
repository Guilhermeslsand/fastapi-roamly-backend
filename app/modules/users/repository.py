import re
from datetime import date
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domains.shared.enums import UserRole
# Carrega os models relacionados antes da configuração dos mappers SQLAlchemy.
from app.modules.destinations.models import DestinationModel as _DestinationModel  # noqa: F401
from app.modules.packages.models import TravelPackageModel as _TravelPackageModel  # noqa: F401
from app.modules.purchases.models import PurchaseModel
from app.modules.users.models import UserModel


class UserRepository:
    """Consultas e persistência de usuários; não contém regras de negócio."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> UserModel | None:
        return self.db.scalar(select(UserModel).where(UserModel.id == user_id))

    def get_client_by_id(self, user_id: UUID) -> UserModel | None:
        return self.db.scalar(
            select(UserModel).where(
                UserModel.id == user_id,
                UserModel.role == UserRole.CLIENT,
            )
        )

    def get_by_email(self, email: str) -> UserModel | None:
        return self.db.scalar(
            select(UserModel).where(func.lower(UserModel.email) == email.lower())
        )

    def email_exists(self, email: str, *, exclude_user_id: UUID | None = None) -> bool:
        statement = select(UserModel.id).where(
            func.lower(UserModel.email) == email.lower()
        )
        if exclude_user_id is not None:
            statement = statement.where(UserModel.id != exclude_user_id)
        return self.db.scalar(statement.limit(1)) is not None

    def cpf_exists(self, cpf: str, *, exclude_user_id: UUID | None = None) -> bool:
        statement = select(UserModel.id).where(UserModel.cpf == cpf)
        if exclude_user_id is not None:
            statement = statement.where(UserModel.id != exclude_user_id)
        return self.db.scalar(statement.limit(1)) is not None

    def create(self, user: UserModel) -> UserModel:
        self.db.add(user)
        self.db.flush()
        return user

    def update(self, user: UserModel) -> UserModel:
        self.db.add(user)
        self.db.flush()
        return user

    def list_clients(
        self,
        *,
        page: int,
        limit: int,
        search: str | None = None,
        is_active: bool | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[UserModel], int]:
        filters = [UserModel.role == UserRole.CLIENT]

        if search:
            normalized_search = search.strip()
            term = f"%{normalized_search}%"
            cpf_digits = re.sub(r"\D", "", normalized_search)
            cpf_term = f"%{cpf_digits or normalized_search}%"
            filters.append(
                or_(
                    UserModel.name.ilike(term),
                    UserModel.email.ilike(term),
                    UserModel.cpf.ilike(cpf_term),
                )
            )
        if is_active is not None:
            filters.append(UserModel.is_active.is_(is_active))
        if created_from is not None:
            filters.append(func.date(UserModel.created_at) >= created_from)
        if created_to is not None:
            filters.append(func.date(UserModel.created_at) <= created_to)

        sortable = {
            "created_at": UserModel.created_at,
            "name": UserModel.name,
            "email": UserModel.email,
        }
        order_column = sortable[sort_by]
        order_expression = order_column.asc() if sort_order == "asc" else order_column.desc()

        statement = (
            select(UserModel)
            .where(*filters)
            .order_by(order_expression, UserModel.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        count_statement = select(func.count()).select_from(UserModel).where(*filters)

        items = list(self.db.scalars(statement).all())
        total = int(self.db.scalar(count_statement) or 0)
        return items, total

    def get_client_detail(self, user_id: UUID) -> tuple[UserModel, int] | None:
        statement = (
            select(UserModel, func.count(PurchaseModel.id).label("purchases_count"))
            .outerjoin(PurchaseModel, PurchaseModel.user_id == UserModel.id)
            .where(UserModel.id == user_id, UserModel.role == UserRole.CLIENT)
            .group_by(UserModel.id)
        )
        row = self.db.execute(statement).one_or_none()
        if row is None:
            return None
        return row[0], int(row[1])
