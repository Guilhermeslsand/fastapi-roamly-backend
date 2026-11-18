from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import configure_mappers

from app.database.base import Base
from app.modules import models as _models  # noqa: F401


def test_all_domain_models_are_registered() -> None:
    configure_mappers()
    assert set(Base.metadata.tables) == {
        "users",
        "destinations",
        "travel_packages",
        "purchases",
        "payments",
    }


def test_purchase_has_database_overlap_constraint() -> None:
    purchase_table = Base.metadata.tables["purchases"]
    constraints = [c for c in purchase_table.constraints if isinstance(c, ExcludeConstraint)]
    assert len(constraints) == 1
    assert constraints[0].name == "excl_purchases_user_travel_period"
