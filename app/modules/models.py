"""Importa todos os models para registrar as tabelas no Base.metadata.

Este módulo deve ser importado pelo Alembic e pelos testes de metadata.
"""

from app.modules.destinations.models import DestinationModel
from app.modules.packages.models import TravelPackageModel
from app.modules.purchases.models import PaymentModel, PurchaseModel
from app.modules.users.models import UserModel

__all__ = [
    "UserModel",
    "DestinationModel",
    "TravelPackageModel",
    "PurchaseModel",
    "PaymentModel",
]
