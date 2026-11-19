import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import RegisterRequest
from app.domains.shared.enums import UserRole


def test_register_normalizes_email_and_cpf() -> None:
    payload = RegisterRequest(
        name="  Maria Silva  ",
        email="MARIA@EXAMPLE.COM",
        cpf="529.982.247-25",
        password="correct-horse-42",
    )
    assert payload.name == "Maria Silva"
    assert payload.email == "maria@example.com"
    assert payload.cpf == "52998224725"
    assert not hasattr(payload, "role")


@pytest.mark.parametrize("cpf", ["1234", "11111111111", "12345678901"])
def test_register_rejects_invalid_cpf(cpf: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            name="Maria Silva",
            email="maria@example.com",
            cpf=cpf,
            password="correct-horse-42",
        )


def test_register_forbids_client_from_sending_role_admin() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            name="Maria Silva",
            email="maria@example.com",
            cpf="12345678901",
            password="correct-horse-42",
            role=UserRole.ADMIN,
        )
