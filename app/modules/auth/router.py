from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies.authentication import get_current_user
from app.modules.auth.dependencies import get_auth_service
from app.modules.auth.schemas import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.auth.service import AuthService
from app.modules.users.models import UserModel

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar cliente",
)
def register(
    data: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, object]:
    return service.register(data)


@router.post("/login", response_model=TokenResponse, summary="Autenticar usuário")
def login(
    data: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, object]:
    return service.login(data)


@router.post("/refresh", response_model=TokenResponse, summary="Rotacionar tokens")
def refresh(
    data: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, object]:
    return service.refresh(data.refresh_token)


@router.post("/logout", response_model=MessageResponse, summary="Encerrar sessão atual")
def logout(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    # O sid foi validado e vinculado ao usuário pela dependência de autenticação.
    session_id: UUID = request.state.auth_session_id
    service.revoke_current_session(session_id=session_id, user_id=current_user.id)
    return {"message": "Sessão encerrada com sucesso."}


@router.post("/logout-all", response_model=MessageResponse, summary="Encerrar todas as sessões")
def logout_all(
    current_user: UserModel = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    revoked = service.revoke_all_sessions(user_id=current_user.id)
    return {"message": f"{revoked} sessão(ões) encerrada(s)."}


@router.get("/me", response_model=UserResponse, summary="Consultar usuário autenticado")
def me(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    return current_user
