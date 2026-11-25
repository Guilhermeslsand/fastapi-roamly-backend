import logging
import time
from collections.abc import Callable

from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.redis.connection import redis_client

logger = logging.getLogger(__name__)

_FIXED_WINDOW_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit por IP, com janela fixa de 60 segundos armazenada no Redis."""

    def __init__(self, app: ASGIApp, prefix: str = "/api/v1") -> None:
        super().__init__(app)
        self.prefix = prefix.rstrip("/")

    @staticmethod
    def _rule(path: str) -> tuple[str, int]:
        if path.endswith("/auth/login"):
            return "login", settings.rate_limit_login_per_minute
        if path.endswith("/auth/register"):
            return "register", settings.rate_limit_register_per_minute
        if path.endswith("/auth/refresh"):
            return "refresh", settings.rate_limit_refresh_per_minute
        return "general", settings.rate_limit_general_per_minute

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if (
            request.method == "OPTIONS"
            or not (path == self.prefix or path.startswith(f"{self.prefix}/"))
            or path.endswith("/health/live")
            or path.endswith("/health/ready")
        ):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        rule, limit = self._rule(path)
        minute_bucket = int(time.time() // 60)
        redis_key = f"rate-limit:{rule}:{client_ip}:{minute_bucket}"

        try:
            count, ttl = await run_in_threadpool(
                redis_client.eval,
                _FIXED_WINDOW_SCRIPT,
                1,
                redis_key,
                60,
            )
        except RedisError:
            # Rate limit falha aberta para não derrubar endpoints públicos;
            # autenticação continua falhando fechada ao consultar a sessão.
            logger.exception("Redis indisponível durante rate limiting; permitindo requisição")
            return await call_next(request)

        count = int(count)
        ttl = max(int(ttl), 0)
        remaining = max(limit - count, 0)
        if count > limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Limite de requisições excedido. Tente novamente em instantes."},
                headers={
                    "Retry-After": str(ttl),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(ttl)
        return response