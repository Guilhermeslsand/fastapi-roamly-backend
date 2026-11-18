from dataclasses import dataclass, field
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4
import re

from app.domains.shared.enums import UserRole

_CPF_PATTERN = re.compile(r"\d{11}$")

@dataclass(slots=True)
class User:
    """Entidade de domínio de usuário, independente do SQLAlchemy."""

    name: str
    email: str
    cpf: str
    password_hash: str
    role: UserRole = UserRole.CLIENT
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.email = self.email.strip().lower()
        self.cpf = re.sub(r"\D", "", self.cpf)

        if not self.name:
            raise ValueError("Nome do usuário é obrigatório.")
        if not self.email:
            raise ValueError("Email do usuário é obrigatório.")
        if not _CPF_PATTERN.fullmatch(self.cpf):
            raise ValueError("CPF deve conter exatamente 11 dígitos.")
        if not self.password_hash:
            raise ValueError("Password hash é obrigatório.")
