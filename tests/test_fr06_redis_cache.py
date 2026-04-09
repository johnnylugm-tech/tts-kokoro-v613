"""
[FR-06] 測試案例：Redis 快取（可選）。

測試案例（對應 SRS.md#L123-L124）：
- 相同請求第二次 → 直接回傳快取（無後端請求）
- Redis 不可用時 → 正常降級至直接合成

其他驗證：
- make_key 相同輸入產生相同 key，不同輸入產生不同 key
- url=None 時模組完全停用，is_enabled == False
- url 設定但 redis.asyncio 不可用時，is_enabled == True 但 is_available == False
- get / set / ping / close 在停用模式下皆無操作（不回拋例外）
- TTL 預設為 86400 秒（24 小時）

Citations:
    SRS.md#L113-L124 (FR-06 需求描述與測試案例)
    SAD.md#L529-L545 (6.9 Redis Cache — FR-06 API 規格)
    SAD.md#L72       (元件映射表 — RedisCache)
    SAD.md#L183      (元件 table — RedisCache FR-06)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.cache.redis_cache import RedisCache

# ---------------------------------------------------------------------------
# Helpers


class MockRedisConfig(NamedTuple):
    """模擬 RedisConfig（redis.url + redis.ttl_seconds）。"""

    url: str | None = None
    ttl_seconds: int = 86400


class MockAppConfig(NamedTuple):
    """模擬含 redis 欄位的 AppConfig。"""

    redis: MockRedisConfig


# ---------------------------------------------------------------------------
# make_key — 靜態方法，無需實例


class TestMakeKey:
    """[FR-06] make_key 測試。"""

    def test_same_inputs_same_key(self):
        """相同 text/voice/speed 必產生相同 key。"""
        key1 = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        key2 = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        assert key1 == key2

    def test_different_text_different_key(self):
        """不同文字必產生不同 key。"""
        key1 = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        key2 = RedisCache.make_key("再見", "zf_xiaoxiao", 1.0)
        assert key1 != key2

    def test_different_voice_different_key(self):
        """不同音色必產生不同 key。"""
        key1 = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        key2 = RedisCache.make_key("你好", "zf_yunxi", 1.0)
        assert key1 != key2

    def test_different_speed_different_key(self):
        """不同 speed 必產生不同 key。"""
        key1 = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        key2 = RedisCache.make_key("你好", "zf_xiaoxiao", 0.9)
        assert key1 != key2

    def test_speed_format_normalized(self):
        """speed=1.0 與 speed=1.00 產生相同 key（固定 4 位小數）。"""
        key1 = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        key2 = RedisCache.make_key("你好", "zf_xiaoxiao", 1.00)
        assert key1 == key2

    def test_key_has_tts_prefix(self):
        """Key 必須以 'tts:' 前綴開頭。"""
        key = RedisCache.make_key("hello", "voice", 1.0)
        assert key.startswith("tts:")

    def test_key_is_sha256_hex(self):
        """Key 必須為 64 字元 SHA-256 hex 字串（前綴後）。"""
        key = RedisCache.make_key("test", "v", 1.0)
        hex_part = key.removeprefix("tts:")
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)


# ---------------------------------------------------------------------------
# 初始化 — url=None（完全停用）


class TestDisabledMode:
    """[FR-06] url=None 時模組完全停用。"""

    def test_url_none_disabled(self):
        """url=None → is_enabled == False。"""
        cfg = MockAppConfig(redis=MockRedisConfig(url=None))
        cache = RedisCache(cfg)
        assert cache.is_enabled is False

    @pytest.mark.asyncio
    async def test_url_none_get_returns_none(self):
        """停用模式下 get 回傳 None（不嘗試任何 Redis 操作）。"""
        cfg = MockAppConfig(redis=MockRedisConfig(url=None))
        cache = RedisCache(cfg)
        assert cache.is_enabled is False
        result = await cache.get("any-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_url_none_set_noop(self):
        """停用模式下 set 不拋例外。"""
        cfg = MockAppConfig(redis=MockRedisConfig(url=None))
        cache = RedisCache(cfg)
        await cache.set("any-key", b"data")  # must not raise

    @pytest.mark.asyncio
    async def test_url_none_ping_false(self):
        """停用模式下 ping 回傳 False。"""
        cfg = MockAppConfig(redis=MockRedisConfig(url=None))
        cache = RedisCache(cfg)
        result = await cache.ping()
        assert result is False

    @pytest.mark.asyncio
    async def test_url_none_close_noop(self):
        """停用模式下 close 不拋例外。"""
        cfg = MockAppConfig(redis=MockRedisConfig(url=None))
        cache = RedisCache(cfg)
        await cache.close()  # must not raise


# ---------------------------------------------------------------------------
# 初始化 — url 設定但 redis.asyncio 匯入失敗


class TestNoRedisLibrary:
    """[FR-06] url 有設定但 redis.asyncio 不可用。"""

    def test_enabled_but_not_available(self):
        """模組啟用但無 redis.asyncio → is_enabled=True, is_available=False。"""
        cfg = MockAppConfig(redis=MockRedisConfig(url="redis://localhost:6379"))
        with patch("app.cache.redis_cache._REDIS_AVAILABLE", False):
            cache = RedisCache(cfg)
            assert cache.is_enabled is True
            assert cache.is_available is False


# ---------------------------------------------------------------------------
# get / set — 正常操作（mock Redis）


class TestCacheOperations:
    """[FR-06] get / set 核心操作測試。"""

    @pytest.fixture
    def mock_redis(self):
        """提供 mock Redis 執行個體。"""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=b"\x00MP3_DATA")
        mock.set = AsyncMock(return_value=True)
        mock.ping = AsyncMock(return_value=True)
        mock.aclose = AsyncMock()
        return mock

    @pytest.fixture
    def cache_with_redis(self, mock_redis):
        cfg = MockAppConfig(redis=MockRedisConfig(url="redis://localhost:6379"))
        with patch("app.cache.redis_cache._REDIS_AVAILABLE", True):
            cache = RedisCache(cfg)
            cache._redis = mock_redis
            cache._available = True
            yield cache

    @pytest.mark.asyncio
    async def test_get_returns_cached_bytes(self, cache_with_redis, mock_redis):
        """[FR-06] get 命中時回傳 bytes。"""
        key = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        result = await cache_with_redis.get(key)
        assert result == b"\x00MP3_DATA"
        mock_redis.get.assert_called_once_with(key)

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self, cache_with_redis, mock_redis):
        """[FR-06] get 未命中時回傳 None。"""
        mock_redis.get = AsyncMock(return_value=None)
        key = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        result = await cache_with_redis.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_writes_with_default_ttl(self, cache_with_redis, mock_redis):
        """[FR-06] set 使用預設 TTL（86400 秒）。"""
        key = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        await cache_with_redis.set(key, b"mp3-data")
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == key
        assert call_args[0][1] == b"mp3-data"
        assert call_args[1]["ex"] == 86400  # default TTL

    @pytest.mark.asyncio
    async def test_set_custom_ttl(self, cache_with_redis, mock_redis):
        """[FR-06] set 可指定自訂 TTL。"""
        key = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        await cache_with_redis.set(key, b"mp3-data", ttl=3600)
        call_args = mock_redis.set.call_args
        assert call_args[1]["ex"] == 3600

    @pytest.mark.asyncio
    async def test_second_request_returns_cache_hit(self, cache_with_redis, mock_redis):
        """[FR-06] 相同請求第二次 → 直接回傳快取（無後端請求）。

        模擬：第一次 set 後，第二次 get 命中。
        """
        key = RedisCache.make_key("熱門語句", "zf_xiaoxiao", 1.0)
        cached_audio = b"CACHED_AUDIO"
        # 讓 mock.get 回傳設定的值
        mock_redis.get = AsyncMock(return_value=cached_audio)
        # 第一次寫入
        await cache_with_redis.set(key, cached_audio)
        # 第二次讀取（應命中）
        result = await cache_with_redis.get(key)
        assert result == cached_audio

    @pytest.mark.asyncio
    async def test_ping_success(self, cache_with_redis, mock_redis):
        """[FR-06] ping 成功 → is_available = True。"""
        result = await cache_with_redis.ping()
        assert result is True
        assert cache_with_redis.is_available is True

    @pytest.mark.asyncio
    async def test_ping_failure(self, cache_with_redis, mock_redis):
        """[FR-06] ping 失敗 → is_available = False，不拋例外。"""
        mock_redis.ping = AsyncMock(side_effect=ConnectionError("boom"))
        result = await cache_with_redis.ping()
        assert result is False
        assert cache_with_redis.is_available is False

    @pytest.mark.asyncio
    async def test_get_redis_error_degrades_gracefully(self, cache_with_redis, mock_redis):
        """[FR-06] Redis 不可用時 → 正常降級至直接合成（get 回傳 None）。"""
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        key = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        result = await cache_with_redis.get(key)
        assert result is None
        assert cache_with_redis.is_available is False

    @pytest.mark.asyncio
    async def test_set_redis_error_degrades_gracefully(self, cache_with_redis, mock_redis):
        """[FR-06] Redis SET 錯誤時不拋例外，正常降級。"""
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
        key = RedisCache.make_key("你好", "zf_xiaoxiao", 1.0)
        # must not raise
        await cache_with_redis.set(key, b"mp3-data")
        assert cache_with_redis.is_available is False

    @pytest.mark.asyncio
    async def test_close(self, cache_with_redis, mock_redis):
        """[FR-06] close 正確關閉連線。"""
        await cache_with_redis.close()
        mock_redis.aclose.assert_called_once()
        assert cache_with_redis._available is False


# ---------------------------------------------------------------------------
# TTL 驗證


class TestTTL:
    """[FR-06] TTL 為 24 小時（86400 秒）。"""

    def test_default_ttl_is_24h(self):
        """設定檔未指定時，TTL 預設為 86400 秒。"""
        cfg = MockAppConfig(redis=MockRedisConfig(url="redis://localhost"))
        with patch("app.cache.redis_cache._REDIS_AVAILABLE", False):
            cache = RedisCache(cfg)
            assert cache._ttl == 86400

    def test_custom_ttl_from_config(self):
        """可透過 redis.ttl_seconds 自訂 TTL。"""
        cfg = MockAppConfig(redis=MockRedisConfig(url="redis://localhost", ttl_seconds=3600))
        with patch("app.cache.redis_cache._REDIS_AVAILABLE", False):
            cache = RedisCache(cfg)
            assert cache._ttl == 3600
