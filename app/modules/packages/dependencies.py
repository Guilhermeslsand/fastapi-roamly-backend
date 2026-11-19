from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.connection_sync import get_db
from app.modules.packages.service import PackageService
from app.redis.cache import RedisCache
from app.redis.connection import redis_client


def get_package_service(db: Session = Depends(get_db)) -> PackageService:
    return PackageService(db=db, cache=RedisCache(redis_client))
