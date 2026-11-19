from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from redis.exceptions import RedisError

from app.core.security import TokenType, TokenValidationError, decode_token
from app.database.connection_sync import get_db
from app.modules.users.models import UserModel
from app.modules.users.repository import UserRepository
from app.redis.connection import redis_client
from app.redis.session_store import RedisSessionStore

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> UserModel:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autenticação necessária ou sessão inválida.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload = decode_token(credentials.credentials, TokenType.ACCESS)
        user_id = UUID(str(payload["sub"]))
        session_id = UUID(str(payload["sid"]))
        access_jti = str(payload["jti"])
    except (TokenValidationError, ValueError, KeyError, TypeError) as exc:
        raise unauthorized from exc

    # Redis é consultado em toda chamada protegida para permitir logout imediato.
    try:
        session = RedisSessionStore(redis_client).get_session(session_id)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de sessões temporariamente indisponível.",
        ) from exc
    if (
        session is None
        or session.user_id != user_id
        or session.access_jti != access_jti
    ):
        raise unauthorized

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise unauthorized

    # A role sempre é lida do PostgreSQL, não confiada ao claim do JWT.
    request.state.auth_session_id = session_id
    return user
