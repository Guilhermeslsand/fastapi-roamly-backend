from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass(slots=True)
class TravelPackage:
    """Pacote comercial com período, preço e quantidade de vagas."""

    title: str
    origin_id: UUID
    destination_id: UUID
    departure_date: date
    return_date: date
    price: Decimal
    total_seats: int
    available_seats: int
    created_by: UUID
    id: UUID = field(default_factory=uuid4)
    description: str | None = None
    cost_price: Decimal | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("Título do pacote é obrigatório.")
        if self.origin_id == self.destination_id:
            raise ValueError("Origem e destino devem ser diferentes.")
        if self.departure_date >= self.return_date:
            raise ValueError("A data de retorno deve ser posterior à data de partida.")
        if self.price < Decimal("0"):
            raise ValueError("O preço não pode ser negativo.")
        if self.cost_price is not None and self.cost_price < Decimal("0"):
            raise ValueError("O custo não pode ser negativo.")
        if self.total_seats <= 0:
            raise ValueError("O pacote deve possuir ao menos uma vaga.")
        if not 0 <= self.available_seats <= self.total_seats:
            raise ValueError("Vagas disponíveis devem estar entre zero e o total de vagas.")
