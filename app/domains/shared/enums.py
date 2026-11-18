from enum import StrEnum


class UserRole(StrEnum):
    CLIENT = "CLIENT"
    ADMIN = "ADMIN"


class PurchaseStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class PaymentMethod(StrEnum):
    CREDIT_CARD = "CREDIT_CARD"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    REFUNDED = "REFUNDED"
