from uuid import uuid4

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    TokenType,
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.domains.shared.enums import UserRole


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    raw_password = "Correct-Horse-Battery-42"
    password_hash = hash_password(raw_password)

    assert password_hash != raw_password
    assert verify_password(raw_password, password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_has_expected_claims() -> None:
    user_id = uuid4()
    session_id = uuid4()
    token, jti = create_access_token(
        user_id=user_id,
        session_id=session_id,
        role=UserRole.CLIENT,
    )

    payload = decode_token(token, TokenType.ACCESS)

    assert payload["sub"] == str(user_id)
    assert payload["sid"] == str(session_id)
    assert payload["jti"] == jti
    assert payload["role"] == UserRole.CLIENT.value


def test_refresh_token_is_not_accepted_as_access_token() -> None:
    token, _ = create_refresh_token(user_id=uuid4(), session_id=uuid4())

    with pytest.raises(TokenValidationError):
        decode_token(token, TokenType.ACCESS)


def test_token_with_wrong_signature_is_rejected() -> None:
    user_id = uuid4()
    session_id = uuid4()
    token, _ = create_access_token(
        user_id=user_id,
        session_id=session_id,
        role=UserRole.ADMIN,
    )
    valid_payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )
    forged = jwt.encode(
        valid_payload,
        "different-secret-key-that-is-also-32-characters",
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(TokenValidationError):
        decode_token(forged, TokenType.ACCESS)
