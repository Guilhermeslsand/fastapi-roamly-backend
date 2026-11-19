from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies.permissions import require_roles
from app.domains.shared.enums import UserRole
from app.modules.packages.dependencies import get_package_service
from app.modules.packages.schemas import (
    PackageAdminPageResponse,
    PackageAdminResponse,
    PackageAdminSearchParams,
    PackageCreateRequest,
    PackagePageResponse,
    PackageResponse,
    PackageSearchParams,
    PackageUpdateRequest,
)
from app.modules.packages.service import PackageService
from app.modules.users.models import UserModel

router = APIRouter(prefix="/packages", tags=["Travel Packages"])
admin_router = APIRouter(prefix="/admin/packages", tags=["Admin - Travel Packages"])


@router.get("", response_model=PackagePageResponse, summary="Pesquisar pacotes ativos")
def search_packages(
    params: PackageSearchParams = Depends(),
    service: PackageService = Depends(get_package_service),
) -> PackagePageResponse:
    return service.search_public(params)


@router.get("/{package_id}", response_model=PackageResponse, summary="Consultar pacote")
def get_package(
    package_id: UUID,
    service: PackageService = Depends(get_package_service),
) -> PackageResponse:
    return service.get_public(package_id)


@admin_router.get("", response_model=PackageAdminPageResponse, summary="Listar pacotes para administração")
def search_packages_admin(
    params: PackageAdminSearchParams = Depends(),
    _admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: PackageService = Depends(get_package_service),
) -> PackageAdminPageResponse:
    return service.search_admin(params)


@admin_router.get("/{package_id}", response_model=PackageAdminResponse, summary="Consultar pacote (admin)")
def get_package_admin(
    package_id: UUID,
    _admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: PackageService = Depends(get_package_service),
) -> PackageAdminResponse:
    return service.get_admin(package_id)


@admin_router.post(
    "", response_model=PackageAdminResponse, status_code=status.HTTP_201_CREATED,
    summary="Criar pacote de viagem",
)
def create_package(
    data: PackageCreateRequest,
    current_admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: PackageService = Depends(get_package_service),
) -> PackageAdminResponse:
    return service.create(data, admin_id=current_admin.id)


@admin_router.patch(
    "/{package_id}", response_model=PackageAdminResponse,
    summary="Atualizar pacote de viagem",
)
def update_package(
    package_id: UUID,
    data: PackageUpdateRequest,
    _admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: PackageService = Depends(get_package_service),
) -> PackageAdminResponse:
    return service.update(package_id, data)


@admin_router.delete(
    "/{package_id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar pacote de viagem",
)
def deactivate_package(
    package_id: UUID,
    _admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: PackageService = Depends(get_package_service),
) -> None:
    service.deactivate(package_id)
    return None
