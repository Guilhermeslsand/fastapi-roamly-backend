from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DestinationModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "destinations"
    __table_args__ = (
        UniqueConstraint("name", "country", "state", name="uq_destination_location"),
        Index(
            "uq_destinations_location_ci",
            text("lower(name)"),
            text("lower(country)"),
            text("coalesce(lower(state), '')"),
            unique=True,
        ),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    departure_packages: Mapped[list["TravelPackageModel"]] = relationship(
        back_populates="origin",
        foreign_keys="TravelPackageModel.origin_id",
    )
    arrival_packages: Mapped[list["TravelPackageModel"]] = relationship(
        back_populates="destination",
        foreign_keys="TravelPackageModel.destination_id",
    )
