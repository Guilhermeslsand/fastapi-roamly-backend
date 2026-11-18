from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domains.destinations.entities import Destination
from app.domains.packages.entities import TravelPackage
from app.domains.shared.enums import UserRole
from app.domains.users.entities import User


def test_user_normalizes_email_and_cpf() -> None:
    user = User(
        name=" Cliente Teste ",
        email="CLIENTE@EXAMPLE.COM ",
        cpf="123.456.789-00",
        password_hash="argon2-hash",
    )
    assert user.email == "cliente@example.com"
    assert user.cpf == "12345678900"
    assert user.role is UserRole.CLIENT


def test_user_rejects_invalid_cpf() -> None:
    with pytest.raises(ValueError, match="11 dígitos"):
        User(name="Cliente", email="a@b.com", cpf="123", password_hash="hash")


def test_destination_requires_name_and_country() -> None:
    with pytest.raises(ValueError, match="Nome e país"):
        Destination(name=" ", country="Brasil")


def test_travel_package_rejects_same_origin_and_destination() -> None:
    destination_id = uuid4()
    with pytest.raises(ValueError, match="Origem e destino"):
        TravelPackage(
            title="Pacote teste",
            origin_id=destination_id,
            destination_id=destination_id,
            departure_date=date(2026, 12, 1),
            return_date=date(2026, 12, 5),
            price=Decimal("1000.00"),
            total_seats=10,
            available_seats=10,
            created_by=uuid4(),
        )


def test_travel_package_rejects_invalid_period() -> None:
    with pytest.raises(ValueError, match="retorno"):
        TravelPackage(
            title="Pacote teste",
            origin_id=uuid4(),
            destination_id=uuid4(),
            departure_date=date(2026, 12, 5),
            return_date=date(2026, 12, 1),
            price=Decimal("1000.00"),
            total_seats=10,
            available_seats=10,
            created_by=uuid4(),
        )
