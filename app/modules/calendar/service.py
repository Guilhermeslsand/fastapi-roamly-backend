from calendar import monthrange
from datetime import date, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.calendar.repository import CalendarRepository
from app.domains.shared.enums import PurchaseStatus
from app.modules.calendar.schemas import (
    CalendarDayResponse,
    CalendarLocation,
    CalendarTripResponse,
    TravelCalendarResponse,
)
from app.modules.purchases.service import business_date


class CalendarService:
    def __init__(self, db: Session) -> None:
        self.repository = CalendarRepository(db)

    @staticmethod
    def resolve_period(start_date: date | None, end_date: date | None) -> tuple[date, date]:
        today = business_date()
        if start_date is None and end_date is None:
            start_date = today.replace(day=1)
            end_date = date(today.year, today.month, monthrange(today.year, today.month)[1])
        elif start_date is None or end_date is None:
            raise HTTPException(
                status_code=422,
                detail="Informe start_date e end_date juntos, ou omita ambos para consultar o mês atual.",
            )
        if start_date is None or end_date is None:
            raise HTTPException(status_code=422, detail="Período inválido.")
        if start_date > end_date:
            raise HTTPException(status_code=422, detail="start_date não pode ser posterior a end_date.")
        if (end_date - start_date).days > 365:
            raise HTTPException(status_code=422, detail="O calendário aceita períodos de até 366 dias.")
        return start_date, end_date

    def get_calendar(
        self, *, user_id: UUID, start_date: date | None, end_date: date | None
    ) -> TravelCalendarResponse:
        start, end = self.resolve_period(start_date, end_date)
        purchases = self.repository.list_trips(
            user_id=user_id,
            start_date=start,
            end_date=end,
        )
        today = business_date()
        trips: list[CalendarTripResponse] = []
        day_map: dict[date, list[UUID]] = {}

        for purchase in purchases:
            package = purchase.package
            if purchase.return_date < today or purchase.status == PurchaseStatus.COMPLETED:
                travel_status = "COMPLETED"
            elif purchase.departure_date <= today <= purchase.return_date:
                travel_status = "ONGOING"
            else:
                travel_status = "UPCOMING"

            trips.append(
                CalendarTripResponse(
                    purchase_id=purchase.id,
                    package_id=package.id,
                    package_title=package.title,
                    origin=CalendarLocation(
                        id=package.origin.id,
                        name=package.origin.name,
                        country=package.origin.country,
                        state=package.origin.state,
                    ),
                    destination=CalendarLocation(
                        id=package.destination.id,
                        name=package.destination.name,
                        country=package.destination.country,
                        state=package.destination.state,
                    ),
                    departure_date=purchase.departure_date,
                    return_date=purchase.return_date,
                    quantity=purchase.quantity,
                    total_amount=purchase.total_amount,
                    purchase_status=purchase.status,
                    travel_status=travel_status,
                )
            )

            day = max(start, purchase.departure_date)
            last_day = min(end, purchase.return_date)
            while day <= last_day:
                day_map.setdefault(day, []).append(purchase.id)
                day += timedelta(days=1)

        days = [
            CalendarDayResponse(date=day, purchase_ids=ids, trips_count=len(ids))
            for day, ids in sorted(day_map.items())
        ]
        return TravelCalendarResponse(
            start_date=start,
            end_date=end,
            trips=trips,
            days=days,
        )
