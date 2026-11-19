import pytest
from pydantic import ValidationError

from app.domains.shared.enums import UserRole
from app.modules.users.schemas import (
    AdminCustomerDetailResponse,
    UserProfileUpdateRequest,
    normalize_and_validate_cpf,
)


def test_profile_update_normalizes_fields() -> None:
    payload = UserProfileUpdateRequest(
        name="  Maria Silva  ",
        email="MARIA@EXAMPLE.COM",
        cpf="529.982.247-25",
    )
    assert payload.name == "Maria Silva"
    assert str(payload.email) == "maria@example.com"
    assert payload.cpf == "52998224725"


@pytest.mark.parametrize("cpf", ["1234", "11111111111", "12345678901"])
def test_profile_update_rejects_invalid_cpf(cpf: str) -> None:
    with pytest.raises(ValidationError):
        UserProfileUpdateRequest(cpf=cpf)


def test_profile_update_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        UserProfileUpdateRequest()


def test_profile_update_rejects_null_only_payload() -> None:
    with pytest.raises(ValidationError):
        UserProfileUpdateRequest(name=None)


def test_profile_update_forbids_role_and_other_unexposed_fields() -> None:
    with pytest.raises(ValidationError):
        UserProfileUpdateRequest(name="Maria Silva", role=UserRole.ADMIN)


def test_admin_customer_response_does_not_expose_password_hash() -> None:
    response = AdminCustomerDetailResponse(
        id="b8e673d5-02cb-4836-a51d-8d4a943b4689",
        name="Maria Silva",
        email="maria@example.com",
        cpf="52998224725",
        is_active=True,
        created_at="2026-11-18T12:00:00Z",
        updated_at="2026-11-18T12:00:00Z",
        purchases_count=3,
    )
    assert response.purchases_count == 3
    assert "password_hash" not in response.model_dump()
    assert "role" not in response.model_dump()


def test_cpf_helper_returns_digits_only() -> None:
    assert normalize_and_validate_cpf("529.982.247-25") == "52998224725"
