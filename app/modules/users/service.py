from datetime import date
from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domains.shared.enums import UserRole
from app.modules.auth.schemas import AdminCreateRequest
from app.modules.users.models import UserModel
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    AdminCustomerDetailResponse,
    AdminCustomerListItem,
    AdminCustomerPageResponse,
    UserProfileUpdateRequest,
)


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

    def update_own_profile(
        self, *, user_id: UUID, data: UserProfileUpdateRequest
    ) -> UserModel:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Informe ao menos um campo para atualizar.",
            )

        new_email = changes.get("email")
        if new_email is not None:
            new_email = str(new_email).lower()
            if new_email != user.email.lower() and self.users.email_exists(
                new_email, exclude_user_id=user.id
            ):
                raise HTTPException(status_code=409, detail="Email já cadastrado.")
            changes["email"] = new_email

        new_cpf = changes.get("cpf")
        if new_cpf is not None and new_cpf != user.cpf:
            if self.users.cpf_exists(new_cpf, exclude_user_id=user.id):
                raise HTTPException(status_code=409, detail="CPF já cadastrado.")

        for field, value in changes.items():
            setattr(user, field, value)

        try:
            self.users.update(user)
            self.db.commit()
            self.db.refresh(user)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Email ou CPF já cadastrado.",
            ) from exc
        return user

    def list_customers(
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
    ) -> AdminCustomerPageResponse:
        if created_from and created_to and created_from > created_to:
            raise HTTPException(
                status_code=422,
                detail="created_from não pode ser posterior a created_to.",
            )

        users, total = self.users.list_clients(
            page=page,
            limit=limit,
            search=search,
            is_active=is_active,
            created_from=created_from,
            created_to=created_to,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return AdminCustomerPageResponse(
            items=[AdminCustomerListItem.model_validate(user) for user in users],
            total=total,
            page=page,
            limit=limit,
            pages=ceil(total / limit) if total else 0,
        )

    def get_customer(self, *, user_id: UUID) -> AdminCustomerDetailResponse:
        result = self.users.get_client_detail(user_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Cliente não encontrado.")
        user, purchases_count = result
        return AdminCustomerDetailResponse(
            **AdminCustomerListItem.model_validate(user).model_dump(),
            purchases_count=purchases_count,
        )
