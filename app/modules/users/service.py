from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domains.shared.enums import UserRole
from app.modules.auth.schemas import AdminCreateRequest
from app.modules.users.models import UserModel
from app.modules.users.repository import UserRepository


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def create_admin(self, data: AdminCreateRequest) -> UserModel:
        if self.users.email_exists(str(data.email)):
            raise HTTPException(status_code=409, detail="Email já cadastrado.")
        if self.users.cpf_exists(data.cpf):
            raise HTTPException(status_code=409, detail="CPF já cadastrado.")

        admin = UserModel(
            name=data.name,
            email=str(data.email).lower(),
            cpf=data.cpf,
            password_hash=hash_password(data.password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        try:
            self.users.create(admin)
            self.db.commit()
            self.db.refresh(admin)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Email ou CPF já cadastrado.",
            ) from exc
        return admin
