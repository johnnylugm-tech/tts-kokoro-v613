# ADR-002: Lazy Init Pattern for All External Dependencies

| Field       | Value                                            |
|-------------|--------------------------------------------------|
| ID          | ADR-002                                          |
| Title       | Lazy Init Pattern for All External Dependencies  |
| Status      | Accepted                                         |
| Date        | 2026-04-01                                       |
| Author      | Agent A (architect)                              |
| Supersedes  | —                                                |
| Context     | tts-kokoro-v613 Phase 2 — Architecture           |

---

## 1. Context

### 1.1 The Problem: Import-Time Crashes

The tts-kokoro-v613 service depends on several external systems:

- **Kokoro Docker backend** — an HTTP service at a configurable URL
- **Redis** — an optional caching service
- **ffmpeg binary** — a system tool for audio conversion

A naive implementation would initialize these dependencies at module import time or at class definition time:

```python
# WRONG — Do NOT do this
import redis
import httpx

# This runs at import time — crashes if Redis is not running
_redis_client = redis.Redis.from_url("redis://localhost:6379")

# This runs at import time — httpx client created before config is loaded
_http_client = httpx.AsyncClient(base_url="http://localhost:8880")

class RedisCache:
    def __init__(self):
        self.client = redis.Redis.from_url("redis://localhost:6379")  # Crashes if Redis down
```

This approach causes three categories of problems:

**Problem A — Crash on import during testing**: When unit tests import `app.infrastructure.redis_cache`, Python executes module-level code, attempting a Redis connection. If Redis is not running in the test environment, the import fails with a `ConnectionRefusedError` before any test code runs. This makes it impossible to test modules in isolation.

**Problem B — Crash on startup when optional services are unavailable**: Redis is explicitly optional in FR-06 ("graceful degradation"). If the service crashes on startup because Redis is not configured, it violates the graceful degradation requirement.

**Problem C — Config not yet loaded**: Module-level initialization runs before the application's `lifespan()` function, before `config.yaml` is parsed. Connection parameters (URLs, timeouts, pool sizes) are not yet available at import time.

**Problem D — Circular import risk**: If `KokoroClient` imports from `CircuitBreaker` at module level, and `CircuitBreaker` is imported in `main.py` before `KokoroClient`, the initialization order becomes fragile and import-order-dependent.

### 1.2 Scope

This ADR applies to all modules that hold a connection or resource to an external system:

| Module | External Dependency | Lazy-Init Variable |
|--------|--------------------|--------------------|
| `KokoroClient` | httpx.AsyncClient | `self._client` |
| `RedisCache` | aioredis connection pool | `self._redis` |
| `AudioConverter` | ffmpeg binary path | `self._ffmpeg_path` |

---

## 2. Decision

**Apply the Lazy Init pattern to ALL external dependency connections.**

The rule is: **every attribute that holds a connection to an external resource is initialized to `None` at `__init__` time. The actual connection is established on the first call to an accessor method, and cached thereafter.**

This is enforced as a code review checklist item and verified by the import test suite.

---

## 3. Pattern Definition

### 3.1 Core Pattern

```python
class ExternalDependency:
    def __init__(self, config: SomeConfig) -> None:
        self._config = config
        self._client: SomeClient | None = None  # Lazy Init: starts as None

    async def _get_client(self) -> SomeClient:
        """Return the client, initializing it on first call."""
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> SomeClient:
        """Actual initialization logic — only called once."""
        return SomeClient(url=self._config.url, timeout=self._config.timeout)

    async def do_work(self) -> Result:
        client = await self._get_client()  # Safe: initializes if needed
        return await client.request(...)
```

### 3.2 Thread Safety in Async Context

Because `asyncio` is single-threaded (one event loop), there is no classic race condition between two threads both observing `self._client is None` simultaneously. However, two coroutines could interleave at an `await` boundary during the initialization:

```
Coroutine A: sees _client is None, begins _create_client()
             → hits an await point inside _create_client()
Coroutine B: sees _client is still None (A hasn't finished yet)
             → begins _create_client() a second time
```

This double-initialization is harmless for `httpx.AsyncClient` (creates two clients; only one is retained), but to be safe and explicit, we use an `asyncio.Lock` for the initialization of connection-pooling resources:

```python
class KokoroClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None  # Lazy Init
        self._init_lock = asyncio.Lock()               # Prevents double-init

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._init_lock:
                # Double-check after acquiring lock
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        base_url=self._config.kokoro.base_url,
                        timeout=httpx.Timeout(
                            connect=self._config.kokoro.connect_timeout,
                            read=self._config.kokoro.read_timeout,
                            write=10.0,
                            pool=5.0,
                        ),
                        limits=httpx.Limits(
                            max_connections=self._config.kokoro.max_connections,
                            max_keepalive_connections=self._config.kokoro.max_keepalive,
                        ),
                    )
        return self._client
```

The double-check (`if self._client is None` inside the lock) is the async equivalent of the double-checked locking pattern.

### 3.3 Applied to KokoroClient

```python
# app/backend/kokoro_client.py
import asyncio
import httpx
from app.infrastructure.config_loader import AppConfig

class KokoroClient:
    """HTTP client for Kokoro Docker backend. Lazy Init on first use."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None   # Lazy Init
        self._init_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._init_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        base_url=self._config.kokoro.base_url,
                        timeout=httpx.Timeout(
                            connect=self._config.kokoro.connect_timeout,
                            read=self._config.kokoro.read_timeout,
                            write=10.0,
                            pool=5.0,
                        ),
                        limits=httpx.Limits(
                            max_connections=self._config.kokoro.max_connections,
                        ),
                    )
        return self._client

    async def synthesize(self, text: str, voice: str, speed: float) -> bytes:
        client = await self._get_client()  # Initialize on first call
        response = await client.post(
            "/v1/audio/speech",
            json={"model": "kokoro", "input": text, "voice": voice, "speed": speed, "response_format": "mp3"},
        )
        response.raise_for_status()
        return response.content

    async def close(self) -> None:
        """Called during application shutdown (lifespan teardown)."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
```

### 3.4 Applied to RedisCache (with graceful disable)

```python
# app/infrastructure/redis_cache.py
import asyncio
from typing import Optional
import redis.asyncio as aioredis
from app.infrastructure.config_loader import AppConfig

class RedisCache:
    """Optional Redis cache. If url is None or Redis unreachable, silently degrades."""

    def __init__(self, config: AppConfig) -> None:
        self._url = config.redis.url
        self._ttl = config.redis.ttl_seconds
        self._redis: aioredis.Redis | None = None   # Lazy Init
        self._enabled = self._url is not None
        self._available = False
        self._init_lock = asyncio.Lock()

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        """Return Redis client, or None if disabled/unavailable."""
        if not self._enabled:
            return None  # Never try to connect if url is None

        if self._redis is None:
            async with self._init_lock:
                if self._redis is None:
                    try:
                        client = aioredis.from_url(
                            self._url,
                            socket_timeout=5.0,
                            socket_connect_timeout=5.0,
                            decode_responses=False,
                        )
                        await client.ping()  # Test connection
                        self._redis = client
                        self._available = True
                    except Exception:
                        # L3: graceful degradation — log warning, continue without cache
                        self._available = False
                        return None
        return self._redis

    async def get(self, key: str) -> Optional[bytes]:
        r = await self._get_redis()
        if r is None:
            return None  # Cache miss (degraded)
        try:
            return await r.get(key)
        except Exception:
            return None  # L3: Redis error → treat as cache miss

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        r = await self._get_redis()
        if r is None:
            return  # No-op (degraded)
        try:
            await r.set(key, value, ex=ttl or self._ttl)
        except Exception:
            pass  # L3: Fire-and-forget; failure is non-fatal
```

### 3.5 Applied to AudioConverter

```python
# app/infrastructure/audio_converter.py
import asyncio
import shutil

class AudioConverter:
    """ffmpeg-based audio converter. Lazy Init: locates ffmpeg binary on first use."""

    def __init__(self, ffmpeg_path: str | None = None) -> None:
        # If explicitly provided, use it; otherwise discover lazily
        self._ffmpeg_path: str | None = ffmpeg_path  # Lazy Init if None
        self._init_lock = asyncio.Lock()

    async def _get_ffmpeg(self) -> str:
        if self._ffmpeg_path is None:
            async with self._init_lock:
                if self._ffmpeg_path is None:
                    path = shutil.which("ffmpeg")
                    if path is None:
                        raise AudioConverterNotFoundError(
                            "ffmpeg not found in PATH. Install ffmpeg to enable audio format conversion."
                        )
                    self._ffmpeg_path = path
        return self._ffmpeg_path

    async def convert(self, audio_data: bytes, target_format: str, source_format: str = "mp3") -> bytes:
        if source_format == target_format:
            return audio_data  # No conversion needed
        ffmpeg = await self._get_ffmpeg()
        return await self._run_ffmpeg(
            [ffmpeg, "-f", source_format, "-i", "pipe:0", "-f", target_format, "pipe:1"],
            stdin=audio_data,
        )
```

---

## 4. Testing Implications

The Lazy Init pattern has direct, positive consequences for testing:

### 4.1 Import-safe tests

```python
# tests/test_infrastructure/test_redis_cache.py
# This import now NEVER crashes, even if Redis is not running:
from app.infrastructure.redis_cache import RedisCache
from app.infrastructure.config_loader import AppConfig

def test_cache_disabled_when_url_is_none():
    """RedisCache with url=None should always return None for get()."""
    config = AppConfig()  # url defaults to None
    cache = RedisCache(config)
    import asyncio
    result = asyncio.run(cache.get("any-key"))
    assert result is None  # No connection attempted

async def test_cache_gracefully_degrades_on_unreachable_redis():
    """RedisCache should return None, not raise, when Redis is unreachable."""
    from app.infrastructure.config_loader import RedisConfig
    config = AppConfig(redis=RedisConfig(url="redis://localhost:9999"))  # Bad port
    cache = RedisCache(config)
    result = await cache.get("any-key")
    assert result is None  # Graceful degradation
```

### 4.2 Mock injection without connection

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.backend.kokoro_client import KokoroClient

@pytest.fixture
def mock_kokoro_client():
    """Return a KokoroClient with a pre-initialized mock httpx client.
    No actual HTTP connection is made."""
    from app.infrastructure.config_loader import AppConfig
    client = KokoroClient(AppConfig())
    # Inject mock directly, bypassing Lazy Init
    mock_http = AsyncMock()
    mock_http.post.return_value = MagicMock(content=b"fake-mp3-bytes", status_code=200)
    client._client = mock_http  # Override _client directly for testing
    return client
```

---

## 5. Consequences

### 5.1 Positive

- **Zero crash on import**: All test files can import any module without requiring external services to be running.
- **Optional Redis is truly optional**: Setting `redis.url: null` in config results in a fully functional service that simply skips the cache layer — no startup error.
- **Config is available at init time**: Because `__init__` only stores config references (no connections), the config is fully loaded before any `_get_client()` is called.
- **Clean shutdown**: The `close()` methods on `KokoroClient` and `RedisCache` are idempotent — calling them when `_client is None` (i.e., lazy init never triggered) is a safe no-op.
- **Testability by design**: Tests can inject mock connections directly into `self._client` without subclassing or monkey-patching module-level globals.

### 5.2 Negative / Trade-offs

- **First-request latency**: The first request after startup incurs the connection overhead (TCP handshake, pool creation). For NFR-01 (TTFB < 300ms), this is acceptable because:
  1. `/ready` is called by the orchestrator/load-balancer before traffic is sent
  2. The `/ready` handler explicitly calls `kokoro_client.health_check()`, which triggers Lazy Init before real traffic arrives
  3. Redis connection timeout is capped at 5 seconds; if Redis is unavailable, graceful degradation kicks in rather than blocking the request

- **Slightly more boilerplate**: Each external dependency module requires a `_get_client()` accessor and an `asyncio.Lock`. This is a small, justified cost.

- **`_client` is semi-private**: Direct access to `self._client` is used in test fixtures (to inject mocks). This is acceptable and documented as an intentional testing hook.

### 5.3 Enforcement Rules

The following rules are enforced by code review and static analysis:

1. **No module-level connection instantiation**: No `redis.Redis()`, `httpx.AsyncClient()`, or `shutil.which()` calls at module level.
2. **All `_client` / `_conn` / `_redis` attributes initialized to `None` in `__init__`**.
3. **All `_get_X()` methods are async and use double-checked locking**.
4. **All `close()` methods check `if self._X is not None` before closing**.

---

## 6. Alternatives Considered

### 6.1 Eager Init in `lifespan()`

Initialize all connections in FastAPI's `lifespan()` startup hook rather than lazily:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await aioredis.from_url(config.redis.url)  # Eager
    yield
    await app.state.redis.aclose()
```

**Rejected** for these reasons:
- If Redis fails during startup, the entire application refuses to start — violating FR-06 graceful degradation.
- Unit tests that `import app.main` would trigger connection attempts.
- The `config.yaml` path is not yet known when Python imports the module.

### 6.2 Dependency Injection Framework (e.g., `dependency-injector`)

Use a DI container library that manages object lifecycles explicitly.

**Partially adopted** — FastAPI's `Depends()` is used for route-level DI. However, a full DI container adds significant complexity (registration, container definition, wiring) that is not justified for a service of this scope. The Lazy Init pattern achieves the same goals with standard Python.

### 6.3 Singleton via Module-Level Global with Initialization Guard

```python
# module level
_client = None

def get_client():
    global _client
    if _client is None:
        _client = create_client()
    return _client
```

**Rejected** for async contexts. Module-level globals are process-wide singletons that survive across tests in the same pytest session, causing test pollution. Class-instance attributes (`self._client`) are scoped to the object and can be reset between tests by creating a new instance.

---

*ADR-002 — Accepted — 2026-04-01*
