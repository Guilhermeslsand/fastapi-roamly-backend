from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.domains.shared.enums import UserRole


_password_hash = PasswordHash.recommended()


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenValidationError(Exception):
    """Token ausente, inválido, expirado ou destinado a outro fluxo."""


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hash.verify(password, password_hash)
    except Exception:
        # Hash inválido ou com formato desconhecido nunca autentica o usuário.
        return False


def _encode_token(
    *,
    user_id: UUID,
    session_id: UUID,
    token_type: TokenType,
    expires_delta: timedelta,
    role: UserRole | None = None,
) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    payload: dict[str, object] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": jti,
        "type": token_type.value,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + expires_delta,
    }
    if role is not None:
        # Informação útil ao cliente; a autorização sempre consulta a role atual no banco.
        payload["role"] = role.value

    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, jti


def create_access_token(*, user_id: UUID, session_id: UUID, role: UserRole) -> tuple[str, str]:
    return _encode_token(
        user_id=user_id,
        session_id=session_id,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_minutes),
        role=role,
    )


def create_refresh_token(*, user_id: UUID, session_id: UUID) -> tuple[str, str]:
    return _encode_token(
        user_id=user_id,
        session_id=session_id,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.refresh_token_days),
    )


def create_token_pair(*, user_id: UUID, session_id: UUID, role: UserRole) -> dict[str, object]:
    access_token, access_jti = create_access_token(
        user_id=user_id, session_id=session_id, role=role
    )
    refresh_token, refresh_jti = create_refresh_token(
        user_id=user_id, session_id=session_id
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_jti": access_jti,
        "refresh_jti": refresh_jti,
        "expires_in": settings.access_token_minutes * 60,
        "refresh_expires_in": settings.refresh_token_days * 24 * 60 * 60,
    }


def decode_token(token: str, expected_type: TokenType) -> dict[str, object]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "sid", "jti", "type", "iat", "exp", "iss", "aud"]},
        )
    except jwt.InvalidTokenError as exc:
        raise TokenValidationError("Token inválido ou expirado.") from exc

    if payload.get("type") != expected_type.value:
        raise TokenValidationError("Tipo de token inválido para esta operação.")

    try:
        UUID(str(payload["sub"]))
        UUID(str(payload["sid"]))
        UUID(str(payload["jti"]))
    except (ValueError, TypeError, KeyError) as exc:
        raise TokenValidationError("Claims do token inválidas.") from exc

    return payload
