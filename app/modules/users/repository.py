from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.users.models import UserModel


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> UserModel | None:
        return self.db.scalar(select(UserModel).where(UserModel.id == user_id))

    def get_by_email(self, email: str) -> UserModel | None:
        return self.db.scalar(
            select(UserModel).where(func.lower(UserModel.email) == email.lower())
        )

    def email_exists(self, email: str) -> bool:
        return self.db.scalar(
            select(UserModel.id).where(func.lower(UserModel.email) == email.lower()).limit(1)
        ) is not None

    def cpf_exists(self, cpf: str) -> bool:
        return self.db.scalar(
            select(UserModel.id).where(UserModel.cpf == cpf).limit(1)
        ) is not None

    def create(self, user: UserModel) -> UserModel:
        self.db.add(user)
        self.db.flush()
        return user
