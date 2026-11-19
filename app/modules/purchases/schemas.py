from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.domains.shared.enums import PaymentMethod, PaymentStatus, PurchaseStatus


class CreditCardInput(BaseModel):
    """Dados descartáveis para a simulação; nunca são persistidos ou registrados."""

    model_config = ConfigDict(extra="forbid")

    cardholder_name: str
    card_number: SecretStr
    expiry_month: SecretStr
    expiry_year: SecretStr
    cvv: SecretStr


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: UUID
    quantity: int = Field(default=1, ge=1, le=10)
    card: CreditCardInput


class PurchaseDestinationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    country: str
    state: str | None


class PurchasePackageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    origin: PurchaseDestinationSummary
    destination: PurchaseDestinationSummary


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    method: PaymentMethod
    status: PaymentStatus
    transaction_reference: str | None
    paid_at: datetime | None
    created_at: datetime


class PurchaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    package_id: UUID
    quantity: int
    total_amount: Decimal
    departure_date: date
    return_date: date
    status: PurchaseStatus
    purchased_at: datetime
    created_at: datetime
    updated_at: datetime
    package: PurchasePackageSummary
    payment: PaymentResponse | None


class PurchasePageResponse(BaseModel):
    items: list[PurchaseResponse]
    total: int
    page: int
    limit: int
    pages: int


class CheckoutAcceptedResponse(PurchaseResponse):
    """Resposta de uma compra confirmada pela simulação de pagamento."""


class PurchaseCancellationResponse(PurchaseResponse):
    """Compra cancelada; o pagamento simulado aparece como REFUNDED."""

