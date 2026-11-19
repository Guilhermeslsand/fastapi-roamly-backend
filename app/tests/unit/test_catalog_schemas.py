from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.destinations.schemas import (
    DestinationCreateRequest,
    DestinationUpdateRequest,
)
from app.modules.packages.schemas import PackageCreateRequest, PackageSearchParams, PackageUpdateRequest


def test_destination_create_normalizes_text() -> None:
    payload = DestinationCreateRequest(name="  São Paulo ", country=" Brasil ")
    assert payload.name == "São Paulo"
    assert payload.country == "Brasil"


def test_destination_patch_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        DestinationUpdateRequest()


def test_destination_patch_rejects_null_name() -> None:
    with pytest.raises(ValidationError):
        DestinationUpdateRequest(name=None)


def test_package_create_validates_dates_and_route() -> None:
    with pytest.raises(ValidationError):
        PackageCreateRequest(
            title="Viagem",
            origin_id=uuid4(),
            destination_id=uuid4(),
            departure_date=date(2026, 12, 10),
            return_date=date(2026, 12, 10),
            price=Decimal("100.00"),
            total_seats=10,
        )


def test_package_search_validates_filter_ranges() -> None:
    with pytest.raises(ValidationError):
        PackageSearchParams(min_price=Decimal("500"), max_price=Decimal("100"))


def test_package_update_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        PackageUpdateRequest()


def test_package_duration_counts_both_departure_and_return_dates() -> None:
    from app.modules.packages.schemas import PackageResponse

    package = PackageResponse.model_construct(
        departure_date=date(2026, 12, 1),
        return_date=date(2026, 12, 12),
    )
    assert package.duration_days == 12
    assert package.duration_nights == 11
