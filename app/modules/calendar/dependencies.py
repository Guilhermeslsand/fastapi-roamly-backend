from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.connection_sync import get_db
from app.modules.calendar.service import CalendarService


def get_calendar_service(db: Session = Depends(get_db)) -> CalendarService:
    return CalendarService(db)
