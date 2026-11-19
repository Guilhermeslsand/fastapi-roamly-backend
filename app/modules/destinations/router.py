from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.permissions import require_roles
from app.domains.shared.enums import UserRole
from app.modules.destinations.dependencies import get_destination_service
from app.modules.destinations.schemas import (
    DestinationCreateRequest,
    DestinationPageResponse,
    DestinationResponse,
    DestinationUpdateRequest,
)
from app.modules.destinations.service import DestinationService
from app.modules.users.models import UserModel

router = APIRouter(prefix="/destinations", tags=["Destinations"])
admin_router = APIRouter(prefix="/admin/destinations", tags=["Admin - Destinations"])


@router.get("", response_model=DestinationPageResponse, summary="Listar destinos ativos")
def list_destinations(
    q: str | None = Query(default=None, min_length=2, max_length=120),
    country: str | None = Query(default=None, min_length=2, max_length=100),
    state: str | None = Query(default=None, min_length=2, max_length=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    service: DestinationService = Depends(get_destination_service),
) -> DestinationPageResponse:
    return service.list_public(
        page=page, limit=limit, q=q, country=country, state=state, sort_order=sort_order
    )


@router.get("/{destination_id}", response_model=DestinationResponse, summary="Consultar destino")
def get_destination(
    destination_id: UUID,
    service: DestinationService = Depends(get_destination_service),
) -> DestinationResponse:
    return service.get_public(destination_id)


@admin_router.get("", response_model=DestinationPageResponse, summary="Listar destinos para administração")
def list_destinations_admin(
    q: str | None = Query(default=None, min_length=2, max_length=120),
    country: str | None = Query(default=None, min_length=2, max_length=100),
    state: str | None = Query(default=None, min_length=2, max_length=100),
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    _admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: DestinationService = Depends(get_destination_service),
) -> DestinationPageResponse:
    return service.list_admin(
        page=page, limit=limit, q=q, country=country, state=state,
        is_active=is_active, sort_order=sort_order,
    )


@admin_router.get("/{destination_id}", response_model=DestinationResponse, summary="Consultar destino (admin)")
def get_destination_admin(
    destination_id: UUID,
    _admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: DestinationService = Depends(get_destination_service),
) -> DestinationResponse:
    return service.get_admin(destination_id)


@admin_router.post(
    "", response_model=DestinationResponse, status_code=status.HTTP_201_CREATED,
    summary="Cadastrar destino",
)
def create_destination(
    data: DestinationCreateRequest,
    _admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: DestinationService = Depends(get_destination_service),
) -> DestinationResponse:
    return service.create(data)


@admin_router.patch(
    "/{destination_id}", response_model=DestinationResponse,
    summary="Atualizar destino",
)
def update_destination(
    destination_id: UUID,
    data: DestinationUpdateRequest,
    _admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: DestinationService = Depends(get_destination_service),
) -> DestinationResponse:
    return service.update(destination_id, data)


@admin_router.delete(
    "/{destination_id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar destino",
)
def deactivate_destination(
    destination_id: UUID,
    _admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: DestinationService = Depends(get_destination_service),
) -> None:
    service.deactivate(destination_id)
    return None
