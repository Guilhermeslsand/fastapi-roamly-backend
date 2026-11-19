from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from redis.exceptions import RedisError

from app.core.security import (
    TokenType,
    TokenValidationError,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.domains.shared.enums import UserRole
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.users.models import UserModel
from app.modules.users.repository import UserRepository
from app.redis.session_store import RedisSessionStore


class AuthService:
    def __init__(self, db: Session, sessions: RedisSessionStore) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.sessions = sessions

    def register(self, data: RegisterRequest) -> dict[str, object]:
        if self.users.email_exists(str(data.email)):
            raise HTTPException(status_code=409, detail="Email já cadastrado.")
        if self.users.cpf_exists(data.cpf):
            raise HTTPException(status_code=409, detail="CPF já cadastrado.")

        user = UserModel(
            name=data.name,
            email=str(data.email).lower(),
            cpf=data.cpf,
            password_hash=hash_password(data.password),
            role=UserRole.CLIENT,  # A role nunca vem do payload público.
            is_active=True,
        )
        try:
            self.users.create(user)
            self.db.commit()
            self.db.refresh(user)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Email ou CPF já cadastrado.",
            ) from exc

        return self._issue_session(user)

    def login(self, data: LoginRequest) -> dict[str, object]:
        user = self.users.get_by_email(str(data.email))
        # A mesma mensagem impede descobrir se um email está cadastrado.
        if user is None or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha inválidos.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Usuário inativo.")
        return self._issue_session(user)

    def refresh(self, raw_refresh_token: str) -> dict[str, object]:
        try:
            payload = decode_token(raw_refresh_token, TokenType.REFRESH)
            user_id = UUID(str(payload["sub"]))
            session_id = UUID(str(payload["sid"]))
            current_jti = str(payload["jti"])
        except (TokenValidationError, ValueError, KeyError, TypeError) as exc:
            raise self._invalid_refresh() from exc

        user = self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            try:
                self.sessions.revoke_session(session_id=session_id, user_id=user_id)
            except RedisError as exc:
                raise self._session_store_unavailable() from exc
            raise self._invalid_refresh()

        try:
            session = self.sessions.get_session(session_id)
        except RedisError as exc:
            raise self._session_store_unavailable() from exc
        if session is None or session.user_id != user_id:
            raise self._invalid_refresh()

        token_pair = create_token_pair(
            user_id=user.id,
            session_id=session_id,
            role=user.role,
        )
        try:
            rotated = self.sessions.rotate_refresh_token(
                session_id=session_id,
                user_id=user_id,
                current_jti=current_jti,
                next_refresh_jti=str(token_pair["refresh_jti"]),
                next_access_jti=str(token_pair["access_jti"]),
                ttl_seconds=int(token_pair["refresh_expires_in"]),
            )
        except RedisError as exc:
            raise self._session_store_unavailable() from exc
        if not rotated:
            # Reutilização de refresh token: revoga a sessão inteira.
            # O frontend deve usar single-flight para evitar refresh concorrente legítimo.
            try:
                self.sessions.revoke_session(session_id=session_id, user_id=user_id)
            except RedisError as exc:
                raise self._session_store_unavailable() from exc
            raise self._invalid_refresh()

        return self._response_payload(user, token_pair)

    def revoke_current_session(self, *, session_id: UUID, user_id: UUID) -> None:
        try:
            self.sessions.revoke_session(session_id=session_id, user_id=user_id)
        except RedisError as exc:
            raise self._session_store_unavailable() from exc

    def revoke_all_sessions(self, *, user_id: UUID) -> int:
        try:
            return self.sessions.revoke_all_sessions(user_id=user_id)
        except RedisError as exc:
            raise self._session_store_unavailable() from exc

    def _issue_session(self, user: UserModel) -> dict[str, object]:
        session_id = uuid4()
        token_pair = create_token_pair(
            user_id=user.id,
            session_id=session_id,
            role=user.role,
        )
        try:
            self.sessions.create_session(
                session_id=session_id,
                user_id=user.id,
                access_jti=str(token_pair["access_jti"]),
                refresh_jti=str(token_pair["refresh_jti"]),
                ttl_seconds=int(token_pair["refresh_expires_in"]),
            )
        except RedisError as exc:
            raise self._session_store_unavailable() from exc
        return self._response_payload(user, token_pair)

    @staticmethod
    def _response_payload(user: UserModel, pair: dict[str, object]) -> dict[str, object]:
        return {
            "access_token": pair["access_token"],
            "refresh_token": pair["refresh_token"],
            "token_type": "bearer",
            "expires_in": pair["expires_in"],
            "refresh_expires_in": pair["refresh_expires_in"],
            "user": user,
        }

    @staticmethod
    def _session_store_unavailable() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de sessões temporariamente indisponível. Tente novamente.",
        )

    @staticmethod
    def _invalid_refresh() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido, expirado, revogado ou já utilizado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
