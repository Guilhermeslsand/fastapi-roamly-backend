from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.domains.shared.enums import PaymentMethod, PaymentStatus, PurchaseStatus


@dataclass(slots=True)
class Purchase:
    """Registro dos valores e período contratados na compra."""

    user_id: UUID
    package_id: UUID
    quantity: int
    total_amount: Decimal
    cost_amount: Decimal | None
    departure_date: date
    return_date: date
    id: UUID = field(default_factory=uuid4)
    status: PurchaseStatus = PurchaseStatus.PENDING
    purchased_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")
        if self.departure_date >= self.return_date:
            raise ValueError("A data de retorno deve ser posterior à partida.")
        if self.total_amount < Decimal("0"):
            raise ValueError("O valor total não pode ser negativo.")
        if self.cost_amount is not None and self.cost_amount < Decimal("0"):
            raise ValueError("O custo total não pode ser negativo.")


@dataclass(slots=True)
class Payment:
    """Pagamento simulado; não armazena número de cartão nem CVV."""

    purchase_id: UUID
    amount: Decimal
    method: PaymentMethod = PaymentMethod.CREDIT_CARD
    status: PaymentStatus = PaymentStatus.PENDING
    id: UUID = field(default_factory=uuid4)
    transaction_reference: str | None = None
    paid_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.amount < Decimal("0"):
            raise ValueError("O valor do pagamento não pode ser negativo.")
