from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.connection_sync import get_db
from app.modules.auth.service import AuthService
from app.redis.connection import redis_client
from app.redis.session_store import RedisSessionStore


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db=db, sessions=RedisSessionStore(redis_client))
