from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.connection_sync import get_db
from app.modules.users.service import UserService


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)
