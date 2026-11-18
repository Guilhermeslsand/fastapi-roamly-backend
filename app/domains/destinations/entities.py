from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(slots=True)
class Destination:
    """Destino turístico que pode ser origem ou destino de um pacote."""

    name: str
    country: str
    id: UUID = field(default_factory=uuid4)
    state: str | None = None
    description: str | None = None
    image_url: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.country = self.country.strip()
        if not self.name or not self.country:
            raise ValueError("Nome e país do destino são obrigatórios.")
