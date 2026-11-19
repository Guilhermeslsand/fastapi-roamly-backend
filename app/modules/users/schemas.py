import re
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.domains.shared.enums import UserRole


def normalize_and_validate_cpf(value: object) -> str:
    """Remove formatação e valida os dígitos verificadores do CPF."""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 11 or digits == digits[0] * 11:
        raise ValueError("CPF inválido.")

    numbers = [int(char) for char in digits]
    first_sum = sum(
        number * weight
        for number, weight in zip(numbers[:9], range(10, 1, -1))
    )
    first_digit = (first_sum * 10) % 11
    first_digit = 0 if first_digit == 10 else first_digit

    second_sum = sum(
        number * weight
        for number, weight in zip(numbers[:10], range(11, 1, -1))
    )
    second_digit = (second_sum * 10) % 11
    second_digit = 0 if second_digit == 10 else second_digit

    if numbers[9] != first_digit or numbers[10] != second_digit:
        raise ValueError("CPF inválido.")
    return digits


class UserProfileUpdateRequest(BaseModel):
    """Campos que o próprio usuário pode alterar no perfil."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    cpf: str | None = Field(default=None, min_length=11, max_length=18)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Nome deve conter pelo menos 2 caracteres.")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).strip().lower() if value is not None else None

    @field_validator("cpf", mode="before")
    @classmethod
    def normalize_cpf(cls, value: object) -> str | None:
        if value is None:
            return None
        return normalize_and_validate_cpf(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "UserProfileUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")
        if all(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Informe ao menos um valor válido para atualizar.")
        return self


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    cpf: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminCustomerListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    cpf: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminCustomerDetailResponse(AdminCustomerListItem):
    purchases_count: int = Field(ge=0)


class AdminCustomerPageResponse(BaseModel):
    items: list[AdminCustomerListItem]
    total: int
    page: int
    limit: int
    pages: int
