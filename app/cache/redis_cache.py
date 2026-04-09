"""
[FR-06] Redis 快取模組 — 可選熱門語句快取，SHA-256 key，TTL=24h，優雅降級。

設計要點：
- Key = SHA-256(text + "|" + voice + "|" + str(speed))  前綴 "tts:"
- TTL = 86400 秒（24 小時），可透過 redis.ttl_seconds 覆寫
- url=None 時全模組禁用（無操作模式），不拋例外
- url 設定但 Redis 實際連不上時，get/set 皆無操作（L3 優雅降級）

測試案例（對應 SRS.md#L123-L124）：
- 相同請求第二次 → 直接回傳快取（無後端請求）
- Redis 不可用時 → 正常降級至直接合成

Citations:
    SRS.md#L113-L124 (FR-06 需求描述與測試案例)
    SAD.md#L72      (元件映射表 — RedisCache → app/infrastructure/redis_cache.py)
    SAD.md#L183     (元件 table — RedisCache FR-06)
    SAD.md#L529-L545 (6.9 Redis Cache — FR-06 API 規格)
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

try:
    import redis.asyncio as redis_async
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    redis_async = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API


class RedisCache:
    """[FR-06] 選配非同步 Redis 快取，優雅降級。

    Args:
        config: 應用程式設定物件，需具備 config.redis.url 與
            config.redis.ttl_seconds 兩個屬性。
            - url=None  → 模組完全停用（is_enabled == False）
            - url 設定   → 嘗試連線，連不上僅記錄警告不拋例外

    Attributes:
        is_enabled: url 有設定且模組啟用時為 True。
        is_available: url 有設定且 Redis 實際可用時為 True。
    """

    _PREFIX = "tts:"

    def __init__(self, config) -> None:
        self._url: str | None = getattr(config, "redis", None) and config.redis.url
        self._ttl: int = (
            getattr(config, "redis", None) and config.redis.ttl_seconds
        ) or 86400
        self._redis: Optional[redis_async.Redis] = None
        self._enabled: bool = self._url is not None
        self._available: bool = False

        if self._enabled and _REDIS_AVAILABLE:
            self._redis = redis_async.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=False,
            )
        elif self._enabled and not _REDIS_AVAILABLE:
            logger.warning(
                "[FR-06] redis.asyncio not installed; caching permanently disabled. "
                "Install with: pip install redis[hiored]"
            )

    # ------------------------------------------------------------------
    # Key generation

    @staticmethod
    def make_key(text: str, voice: str, speed: float) -> str:
        """[FR-06] 產生快取 Key。

        Key = "tts:" + SHA-256(text + "|" + voice + "|" + f"{speed:.4f}")
        固定 4 位小數確保相同 speed 不同表示（1.0 vs 1.00）產生相同 key。
        """
        raw = f"{text}|{voice}|{speed:.4f}"
        return RedisCache._PREFIX + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Cache operations

    async def get(self, key: str) -> Optional[bytes]:
        """[FR-06] 嘗試從 Redis 取得快取。

        Returns:
            bytes: 快取命中（HIT）。
            None:  快取未命中（MISS）或模組已禁用/Redis 不可用。

        Raises:
            任何 Redis 連線錯誤會被內部捕獲並降級，不向外傳播。
        """
        if not self._enabled or not self._available:
            return None
        try:
            return await self._redis.get(key)  # type: ignore[union-attr]
        except Exception as exc:  # pragma: no cover — L3 graceful degradation
            logger.warning("[FR-06] Redis GET failed, degrading: %s", exc)
            self._available = False
            return None

    async def set(
        self, key: str, value: bytes, ttl: Optional[int] = None
    ) -> None:
        """[FR-06] 寫入 Redis 快取，TTL 預設 24 小時。

        Args:
            key:  快取 Key（通常由 make_key 產生）。
            value: MP3 或其他二進位音色資料。
            ttl:  秒數，None 時使用設定檔中的預設值（86400）。

        Raises:
            任何 Redis 連線錯誤會被內部捕獲並降級，不向外傳播。
        """
        if not self._enabled:
            return
        try:
            await self._redis.set(  # type: ignore[union-attr]
                key,
                value,
                ex=(ttl if ttl is not None else self._ttl),
            )
            self._available = True
        except Exception as exc:  # pragma: no cover — L3 graceful degradation
            logger.warning("[FR-06] Redis SET failed, degrading: %s", exc)
            self._available = False

    # ------------------------------------------------------------------
    # Health-check

    async def ping(self) -> bool:
        """[FR-06] 探測 Redis 是否可達。

        成功 PING → is_available = True；失敗 → is_available = False。
        url=None 時永遠回傳 False。

        Returns:
            bool: Redis 目前可達時回傳 True。
        """
        if not self._enabled:
            return False
        try:
            await self._redis.ping()  # type: ignore[union-attr]
            self._available = True
            return True
        except Exception as exc:  # pragma: no cover
            logger.debug("[FR-06] Redis PING failed: %s", exc)
            self._available = False
            return False

    async def close(self) -> None:
        """[FR-06] 關閉 Redis 連線，釋放資源。"""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        self._available = False

    # ------------------------------------------------------------------
    # Properties

    @property
    def is_enabled(self) -> bool:
        """[FR-06] 是否啟用（url 已設定）。"""
        return self._enabled

    @property
    def is_available(self) -> bool:
        """[FR-06] Redis 目前是否可達。"""
        return self._available
