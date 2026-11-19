from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.authentication import get_current_user
from app.api.dependencies.permissions import require_roles
from app.domains.shared.enums import UserRole
from app.modules.auth.schemas import AdminCreateRequest, UserResponse
from app.modules.users.dependencies import get_user_service
from app.modules.users.models import UserModel
from app.modules.users.schemas import (
    AdminCustomerDetailResponse,
    AdminCustomerPageResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.modules.users.service import UserService

profile_router = APIRouter(prefix="/users", tags=["Users"])
router = APIRouter(prefix="/admin", tags=["Admin users"])


@profile_router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Consultar meu perfil",
)
def get_my_profile(
    current_user: UserModel = Depends(get_current_user),
) -> UserModel:
    return current_user


@profile_router.patch(
    "/me",
    response_model=UserProfileResponse,
    summary="Atualizar meu perfil",
)
def update_my_profile(
    data: UserProfileUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserModel:
    return service.update_own_profile(user_id=current_user.id, data=data)


@router.post(
    "/admins",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar administrador",
)
def create_admin(
    data: AdminCreateRequest,
    _current_admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: UserService = Depends(get_user_service),
) -> UserModel:
    return service.create_admin(data)


@router.get(
    "/users",
    response_model=AdminCustomerPageResponse,
    summary="Listar clientes cadastrados",
)
def list_customers(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, min_length=1, max_length=150),
    is_active: bool | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    sort_by: str = Query(default="created_at", pattern="^(created_at|name|email)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    _current_admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: UserService = Depends(get_user_service),
) -> AdminCustomerPageResponse:
    return service.list_customers(
        page=page,
        limit=limit,
        search=q,
        is_active=is_active,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminCustomerDetailResponse,
    summary="Consultar dados de um cliente",
)
def get_customer(
    user_id: UUID,
    _current_admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: UserService = Depends(get_user_service),
) -> AdminCustomerDetailResponse:
    return service.get_customer(user_id=user_id)
