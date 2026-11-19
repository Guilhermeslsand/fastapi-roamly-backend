import hashlib
import json
import logging
from typing import Any

from redis import Redis

logger = logging.getLogger(__name__)


class RedisCache:
    """Cache JSON best-effort; PostgreSQL continua sendo a fonte da verdade."""

    def __init__(self, client: Redis) -> None:
        self.client = client

    @staticmethod
    def build_key(namespace: str, payload: dict[str, Any] | None = None) -> str:
        if not payload:
            return f"cache:{namespace}"
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"cache:{namespace}:{digest}"

    def get_json(self, key: str) -> Any | None:
        raw_value = self.client.get(key)
        if raw_value is None:
            return None
        try:
            return json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Entrada inválida removida do cache: %s", key)
            self.client.delete(key)
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
        self.client.set(key, serialized, ex=ttl_seconds)

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove chaves por SCAN, evitando o bloqueio de Redis causado por KEYS."""
        pattern = f"cache:{prefix}:*"
        removed = 0
        batch: list[str] = []
        for key in self.client.scan_iter(match=pattern, count=200):
            batch.append(key)
            if len(batch) >= 200:
                removed += int(self.client.unlink(*batch))
                batch.clear()
        if batch:
            removed += int(self.client.unlink(*batch))
        return removed
