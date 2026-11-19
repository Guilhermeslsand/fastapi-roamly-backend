from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.connection_sync import get_db
from app.modules.destinations.service import DestinationService
from app.redis.cache import RedisCache
from app.redis.connection import redis_client


def get_destination_service(db: Session = Depends(get_db)) -> DestinationService:
    return DestinationService(db=db, cache=RedisCache(redis_client))
