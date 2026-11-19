from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


class PackageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=10000)
    origin_id: UUID
    destination_id: UUID
    departure_date: date
    return_date: date
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    total_seats: int = Field(gt=0, le=10000)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_package(self) -> "PackageCreateRequest":
        if not self.title.strip():
            raise ValueError("O título do pacote é obrigatório.")
        if self.origin_id == self.destination_id:
            raise ValueError("Origem e destino devem ser diferentes.")
        if self.departure_date >= self.return_date:
            raise ValueError("A data de retorno deve ser posterior à data de partida.")
        return self


class PackageUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=10000)
    origin_id: UUID | None = None
    destination_id: UUID | None = None
    departure_date: date | None = None
    return_date: date | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    total_seats: int | None = Field(default=None, gt=0, le=10000)
    is_active: bool | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def validate_patch(self) -> "PackageUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualização.")

        non_nullable = {
            "title", "origin_id", "destination_id", "departure_date",
            "return_date", "price", "total_seats", "is_active",
        }
        for field_name in non_nullable:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} não pode ser nulo.")

        if self.title is not None and not self.title.strip():
            raise ValueError("O título do pacote é obrigatório.")
        return self


class PackageSearchParams(BaseModel):
    """Filtros compartilhados pela pesquisa pública e pela listagem administrativa.

    min_days/max_days contam os dias de calendário incluindo partida e retorno.
    """

    q: str | None = Field(default=None, min_length=2, max_length=120)
    origin_id: UUID | None = None
    destination_id: UUID | None = None
    departure_from: date | None = None
    departure_to: date | None = None
    min_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    max_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    min_days: int | None = Field(default=None, ge=1, le=365)
    max_days: int | None = Field(default=None, ge=1, le=365)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    sort_by: Literal["departure_date", "return_date", "price", "created_at", "title"] = "departure_date"
    sort_order: Literal["asc", "desc"] = "asc"

    @field_validator("q")
    @classmethod
    def normalize_query(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def validate_ranges(self) -> "PackageSearchParams":
        if self.departure_from and self.departure_to and self.departure_from > self.departure_to:
            raise ValueError("departure_from não pode ser posterior a departure_to.")
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price não pode ser maior que max_price.")
        if self.min_days is not None and self.max_days is not None and self.min_days > self.max_days:
            raise ValueError("min_days não pode ser maior que max_days.")
        return self


class PackageAdminSearchParams(PackageSearchParams):
    """Filtros adicionais disponíveis somente para administradores."""

    is_active: bool | None = None


class DestinationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    country: str
    state: str | None
    image_url: str | None


class PackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    origin_id: UUID
    destination_id: UUID
    origin: DestinationSummary
    destination: DestinationSummary
    departure_date: date
    return_date: date
    price: Decimal
    total_seats: int
    available_seats: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def duration_days(self) -> int:
        """Quantidade de dias de calendário, incluindo partida e retorno."""
        return (self.return_date - self.departure_date).days + 1

    @computed_field
    @property
    def duration_nights(self) -> int:
        return (self.return_date - self.departure_date).days


class PackageAdminResponse(PackageResponse):
    cost_price: Decimal | None
    created_by: UUID


class PackagePageResponse(BaseModel):
    items: list[PackageResponse]
    total: int
    page: int
    limit: int
    pages: int


class PackageAdminPageResponse(BaseModel):
    items: list[PackageAdminResponse]
    total: int
    page: int
    limit: int
    pages: int
