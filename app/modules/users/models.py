from sqlalchemy import Boolean, CheckConstraint, Enum as SAEnum, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domains.shared.enums import UserRole


def enum_values(enum_cls: type) -> list[str]:
    return [item.value for item in enum_cls]


class UserModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("cpf ~ '^[0-9]{11}$'", name="cpf_must_have_11_digits"),
        Index("uq_users_email_lower", func.lower(text("email")), unique=True),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=UserRole.CLIENT,
        server_default=UserRole.CLIENT.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    created_packages: Mapped[list["TravelPackageModel"]] = relationship(
        back_populates="created_by_user",
        foreign_keys="TravelPackageModel.created_by",
    )
    purchases: Mapped[list["PurchaseModel"]] = relationship(
        back_populates="user", foreign_keys="PurchaseModel.user_id"
    )
