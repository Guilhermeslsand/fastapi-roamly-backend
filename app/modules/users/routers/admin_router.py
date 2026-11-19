from fastapi import APIRouter, Depends, status

from app.api.dependencies.permissions import require_roles
from app.domains.shared.enums import UserRole
from app.modules.auth.schemas import AdminCreateRequest, UserResponse
from app.modules.users.dependencies import get_user_service
from app.modules.users.models import UserModel
from app.modules.users.service import UserService

router = APIRouter(prefix="/admin", tags=["Admin users"])


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
