from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from redis.exceptions import RedisError

from app.database.connection_sync import get_db as get_db_sync
from app.redis.connection import redis_client

router = APIRouter(tags=["Health"])

@router.get("/health/live", summary="Verifica se a API está em execução")
def liveness() -> dict[str, str]:
    return {"status":"alive"}

@router.get("/health/ready", summary="Verifica a disponibilidade da infra do sistema")
def readiness(db: Session = Depends(get_db_sync)) -> dict[str,str]:
    try:
        db.execute(text("SELECT 1"))
        redis_client.ping()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API está indisponível, tente novamente mais tarde",
        ) from exc
    return {
        "status":"ready",
        "database":"connect",
        "redis":"connected",
    }