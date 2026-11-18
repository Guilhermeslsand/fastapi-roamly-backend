from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    text,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TravelPackageModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "travel_packages"
    __table_args__ = (
        CheckConstraint("origin_id <> destination_id", name="different_origin_destination"),
        CheckConstraint("departure_date < return_date", name="return_after_departure"),
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("cost_price IS NULL OR cost_price >= 0", name="cost_non_negative"),
        CheckConstraint("total_seats > 0", name="total_seats_positive"),
        CheckConstraint(
            "available_seats >= 0 AND available_seats <= total_seats",
            name="available_seats_in_range",
        ),
    )

    title: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_id: Mapped[UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    destination_id: Mapped[UUID] = mapped_column(
        ForeignKey("destinations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    departure_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    available_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    origin: Mapped["DestinationModel"] = relationship(
        back_populates="departure_packages",
        foreign_keys=[origin_id],
    )
    destination: Mapped["DestinationModel"] = relationship(
        back_populates="arrival_packages",
        foreign_keys=[destination_id],
    )
    created_by_user: Mapped["UserModel"] = relationship(
        back_populates="created_packages", foreign_keys=[created_by]
    )
    purchases: Mapped[list["PurchaseModel"]] = relationship(back_populates="package")
