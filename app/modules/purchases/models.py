from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    DateTime,
    CheckConstraint,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domains.shared.enums import PaymentMethod, PaymentStatus, PurchaseStatus


def enum_values(enum_cls: type) -> list[str]:
    return [item.value for item in enum_cls]


class PurchaseModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchases"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("total_amount >= 0", name="total_amount_non_negative"),
        CheckConstraint("cost_amount IS NULL OR cost_amount >= 0", name="cost_amount_non_negative"),
        CheckConstraint("departure_date < return_date", name="return_after_departure"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_purchases_user_idempotency_key"),
        ExcludeConstraint(
            ("user_id", "="),
            (text("daterange(departure_date, return_date, '[]')"), "&&"),
            where=text("status IN ('CONFIRMED', 'COMPLETED')"),
            using="gist",
            name="excl_purchases_user_travel_period",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("travel_packages.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Nullable para preservar compras legadas; todo checkout novo exige Idempotency-Key.
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[PurchaseStatus] = mapped_column(
        SAEnum(
            PurchaseStatus,
            name="purchase_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=PurchaseStatus.PENDING,
        server_default=PurchaseStatus.PENDING.value,
        index=True,
    )
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["UserModel"] = relationship(back_populates="purchases")
    package: Mapped["TravelPackageModel"] = relationship(back_populates="purchases")
    payment: Mapped["PaymentModel | None"] = relationship(
        back_populates="purchase", uselist=False
    )


class PaymentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_non_negative"),
    )

    purchase_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchases.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        SAEnum(
            PaymentMethod,
            name="payment_method",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=PaymentMethod.CREDIT_CARD,
        server_default=PaymentMethod.CREDIT_CARD.value,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(
            PaymentStatus,
            name="payment_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
        index=True,
    )
    transaction_reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    purchase: Mapped["PurchaseModel"] = relationship(back_populates="payment")
