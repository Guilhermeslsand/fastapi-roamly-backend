from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.connection_sync import get_db
from app.modules.purchases.service import PurchaseService
from app.redis.cache import RedisCache
from app.redis.connection import redis_client


def get_purchase_service(db: Session = Depends(get_db)) -> PurchaseService:
    return PurchaseService(db=db, cache=RedisCache(redis_client))
