from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DestinationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=150)
    country: str = Field(min_length=2, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    image_url: str | None = Field(default=None, max_length=2048)

    @field_validator("name", "country")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("O campo deve conter pelo menos 2 caracteres.")
        return normalized

    @field_validator("state", "description", "image_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class DestinationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=150)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    image_url: str | None = Field(default=None, max_length=2048)
    is_active: bool | None = None

    @field_validator("name", "country")
    @classmethod
    def normalize_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("O campo deve conter pelo menos 2 caracteres.")
        return normalized

    @field_validator("state", "description", "image_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_patch(self) -> "DestinationUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualização.")
        for field_name in ("name", "country"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} não pode ser nulo.")
        return self


class DestinationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    country: str
    state: str | None
    description: str | None
    image_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DestinationPageResponse(BaseModel):
    items: list[DestinationResponse]
    total: int
    page: int
    limit: int
    pages: int
