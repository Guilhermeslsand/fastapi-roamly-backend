import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domains.shared.enums import UserRole


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    cpf: str = Field(min_length=11, max_length=18)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Nome deve conter pelo menos 2 caracteres.")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("cpf", mode="before")
    @classmethod
    def normalize_cpf(cls, value: object) -> str:
        digits = re.sub(r"\D", "", str(value))
        if len(digits) != 11 or digits == digits[0] * 11:
            raise ValueError("CPF inválido.")

        numbers = [int(char) for char in digits]
        first_sum = sum(number * weight for number, weight in zip(numbers[:9], range(10, 1, -1)))
        first_digit = (first_sum * 10) % 11
        first_digit = 0 if first_digit == 10 else first_digit

        second_sum = sum(number * weight for number, weight in zip(numbers[:10], range(11, 1, -1)))
        second_digit = (second_sum * 10) % 11
        second_digit = 0 if second_digit == 10 else second_digit

        if numbers[9] != first_digit or numbers[10] != second_digit:
            raise ValueError("CPF inválido.")
        return digits


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class AdminCreateRequest(RegisterRequest):
    """Dados para criação de ADMIN em rota protegida por outro ADMIN."""


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=20, max_length=4096)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    cpf: str
    role: UserRole
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
