from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from redis import Redis


@dataclass(frozen=True, slots=True)
class ActiveSession:
    session_id: UUID
    user_id: UUID
    access_jti: str
    refresh_jti: str
    expires_at: int


# Compare-and-swap: apenas o refresh_jti atual pode ser trocado.
_ROTATE_SESSION_SCRIPT = """
local session_key = KEYS[1]
local user_sessions_key = KEYS[2]
local expected_refresh_jti = ARGV[1]
local next_refresh_jti = ARGV[2]
local next_access_jti = ARGV[3]
local ttl = tonumber(ARGV[4])
local expires_at = tonumber(ARGV[5])

if redis.call('EXISTS', session_key) == 0 then
    return 0
end

local current_jti = redis.call('HGET', session_key, 'refresh_jti')
if current_jti ~= expected_refresh_jti then
    return -1
end

redis.call('HSET', session_key, 'refresh_jti', next_refresh_jti, 'access_jti', next_access_jti, 'expires_at', expires_at)
redis.call('EXPIRE', session_key, ttl)
redis.call('ZADD', user_sessions_key, expires_at, string.sub(session_key, string.len('auth:session:') + 1))
redis.call('EXPIRE', user_sessions_key, ttl)
return 1
"""

_LOGOUT_ALL_SCRIPT = """
local sessions_key = KEYS[1]
local session_prefix = ARGV[1]
local session_ids = redis.call('ZRANGE', sessions_key, 0, -1)
for _, session_id in ipairs(session_ids) do
    redis.call('DEL', session_prefix .. session_id)
end
redis.call('DEL', sessions_key)
return #session_ids
"""


class RedisSessionStore:
    """Persistência de sessões ativas; os JWTs não são armazenados no Redis."""

    SESSION_PREFIX = "auth:session:"
    USER_SESSIONS_PREFIX = "auth:user:"

    def __init__(self, client: Redis) -> None:
        self.client = client

    @classmethod
    def _session_key(cls, session_id: UUID | str) -> str:
        return f"{cls.SESSION_PREFIX}{session_id}"

    @classmethod
    def _user_sessions_key(cls, user_id: UUID | str) -> str:
        return f"{cls.USER_SESSIONS_PREFIX}{user_id}:sessions"

    def create_session(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        access_jti: str,
        refresh_jti: str,
        ttl_seconds: int,
    ) -> None:
        now = int(datetime.now(timezone.utc).timestamp())
        expires_at = now + ttl_seconds
        session_key = self._session_key(session_id)
        user_sessions_key = self._user_sessions_key(user_id)

        with self.client.pipeline(transaction=True) as pipeline:
            pipeline.hset(
                session_key,
                mapping={
                    "user_id": str(user_id),
                    "access_jti": access_jti,
                    "refresh_jti": refresh_jti,
                    "created_at": now,
                    "expires_at": expires_at,
                },
            )
            pipeline.expire(session_key, ttl_seconds)
            pipeline.zremrangebyscore(user_sessions_key, "-inf", now)
            pipeline.zadd(user_sessions_key, {str(session_id): expires_at})
            pipeline.expire(user_sessions_key, ttl_seconds)
            pipeline.execute()

    def get_session(self, session_id: UUID) -> ActiveSession | None:
        data = self.client.hgetall(self._session_key(session_id))
        if not data:
            return None
        try:
            return ActiveSession(
                session_id=session_id,
                user_id=UUID(data["user_id"]),
                access_jti=data["access_jti"],
                refresh_jti=data["refresh_jti"],
                expires_at=int(data["expires_at"]),
            )
        except (KeyError, ValueError, TypeError):
            # Registro inconsistente: falha fechada e remove a sessão inválida.
            self.revoke_session(session_id=session_id, user_id=data.get("user_id", ""))
            return None

    def rotate_refresh_token(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        current_jti: str,
        next_refresh_jti: str,
        next_access_jti: str,
        ttl_seconds: int,
    ) -> bool:
        now = int(datetime.now(timezone.utc).timestamp())
        result = self.client.eval(
            _ROTATE_SESSION_SCRIPT,
            2,
            self._session_key(session_id),
            self._user_sessions_key(user_id),
            current_jti,
            next_refresh_jti,
            next_access_jti,
            ttl_seconds,
            now + ttl_seconds,
        )
        return int(result) == 1

    def revoke_session(self, *, session_id: UUID, user_id: UUID | str) -> None:
        with self.client.pipeline(transaction=True) as pipeline:
            pipeline.delete(self._session_key(session_id))
            if user_id:
                pipeline.zrem(self._user_sessions_key(user_id), str(session_id))
            pipeline.execute()

    def revoke_all_sessions(self, *, user_id: UUID) -> int:
        return int(
            self.client.eval(
                _LOGOUT_ALL_SCRIPT,
                1,
                self._user_sessions_key(user_id),
                self.SESSION_PREFIX,
            )
        )
