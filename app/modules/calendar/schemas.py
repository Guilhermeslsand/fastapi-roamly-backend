from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.domains.shared.enums import PurchaseStatus


class CalendarLocation(BaseModel):
    id: UUID
    name: str
    country: str
    state: str | None


class CalendarTripResponse(BaseModel):
    purchase_id: UUID
    package_id: UUID
    package_title: str
    origin: CalendarLocation
    destination: CalendarLocation
    departure_date: date
    return_date: date
    quantity: int
    total_amount: Decimal
    purchase_status: PurchaseStatus
    travel_status: Literal["UPCOMING", "ONGOING", "COMPLETED"]


class CalendarDayResponse(BaseModel):
    date: date
    purchase_ids: list[UUID]
    trips_count: int


class TravelCalendarResponse(BaseModel):
    start_date: date
    end_date: date
    trips: list[CalendarTripResponse]
    days: list[CalendarDayResponse]
