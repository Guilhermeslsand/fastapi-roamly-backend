from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.api.dependencies.authentication import get_current_user
from app.domains.shared.enums import UserRole
from app.modules.users.models import UserModel


def require_roles(*allowed_roles: UserRole) -> Callable[..., UserModel]:
    """Cria uma dependência RBAC; a role atual vem do banco via get_current_user."""

    def role_dependency(
        current_user: UserModel = Depends(get_current_user),
    ) -> UserModel:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não possui permissão para acessar este recurso.",
            )
        return current_user

    return role_dependency


def require_admin(current_user: UserModel = Depends(require_roles(UserRole.ADMIN))) -> UserModel:
    return current_user


def require_client(current_user: UserModel = Depends(require_roles(UserRole.CLIENT))) -> UserModel:
    return current_user
