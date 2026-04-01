# ADR-001: FastAPI as the Proxy Framework

| Field       | Value                              |
|-------------|------------------------------------|
| ID          | ADR-001                            |
| Title       | FastAPI as the Proxy Framework     |
| Status      | Accepted                           |
| Date        | 2026-04-01                         |
| Author      | Agent A (architect)                |
| Supersedes  | —                                  |
| Context     | tts-kokoro-v613 Phase 2 — Architecture |

---

## 1. Context

The tts-kokoro-v613 service is a proxy layer that receives TTS synthesis requests from clients and forwards them (after processing) to a Kokoro Docker backend. The proxy must:

1. **Handle concurrent requests**: Multiple clients may issue synthesis requests simultaneously. Each request requires several async I/O operations (Redis lookup, multiple Kokoro HTTP calls, optional ffmpeg conversion).
2. **Expose a structured REST API**: Four endpoints with clear request/response schemas, authentication, and standard HTTP error codes.
3. **Stream large audio responses**: Synthesized audio can be tens of megabytes; the framework must support streaming responses without buffering the entire body in memory.
4. **Integrate with Python async ecosystem**: The processing pipeline uses `asyncio`, `httpx.AsyncClient`, and `aioredis` — all async-native libraries.
5. **Provide automatic API documentation**: For developer adoption, OpenAPI/Swagger docs should be generated automatically from code.
6. **Validate inputs rigorously**: Malformed requests (L1 errors) should be rejected immediately with informative error messages, before any downstream I/O is attempted.

The framework choice has a high impact on the entire codebase — it determines the async model, serialization approach, middleware architecture, and testing strategy.

---

## 2. Decision

**Use FastAPI (with Uvicorn as the ASGI server) as the HTTP proxy framework.**

FastAPI version `>=0.111.0,<0.112` with `uvicorn[standard]` (includes uvloop and httptools for maximum async performance).

The application is structured as follows:

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import router
from app.infrastructure.auth import AuthMiddleware
from app.infrastructure.config_loader import get_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management."""
    # Startup: config is validated here, but no connections are opened
    # (Lazy Init defers connection to first use — see ADR-002)
    config = get_config()
    app.state.config = config
    yield
    # Shutdown: close open connections gracefully
    await app.state.kokoro_client.close()
    await app.state.redis_cache.close()

def create_app() -> FastAPI:
    config = get_config()
    app = FastAPI(
        title="tts-kokoro-v613",
        version=config.version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(AuthMiddleware, config=config)
    app.include_router(router, prefix="/v1/proxy")
    app.include_router(health_router)  # /health, /ready
    return app

app = create_app()
```

Route definitions use dependency injection and Pydantic models:

```python
# app/api/routes.py
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.models.speech import SpeechRequest, VoiceInfo
from app.orchestrator.speech_orchestrator import SpeechOrchestrator

router = APIRouter()

@router.post("/speech")
async def post_speech(
    request: SpeechRequest,
    orchestrator: SpeechOrchestrator = Depends(get_orchestrator),
) -> StreamingResponse:
    audio_bytes = await orchestrator.synthesize(request)
    media_type = "audio/mpeg" if request.response_format == "mp3" else "audio/wav"
    return StreamingResponse(
        iter([audio_bytes]),
        media_type=media_type,
        headers={"Content-Length": str(len(audio_bytes))},
    )

@router.get("/voices", response_model=list[VoiceInfo])
async def get_voices(
    orchestrator: SpeechOrchestrator = Depends(get_orchestrator),
) -> list[VoiceInfo]:
    return await orchestrator.list_voices()
```

---

## 3. Rationale

### 3.1 Why FastAPI over alternatives

| Criterion | FastAPI | Flask | aiohttp | Django REST |
|-----------|---------|-------|---------|-------------|
| Async-native | Native `async def` routes | Requires Quart or workarounds | Native | Via ASGI adapter |
| Input validation | Pydantic v2 (built-in) | Manual / marshmallow | Manual | DRF serializers |
| Auto OpenAPI docs | Built-in | flask-swagger | Manual | drf-spectacular |
| Streaming responses | `StreamingResponse` built-in | Limited | Built-in | Limited |
| Middleware support | ASGI middleware stack | WSGI (blocking) | aiohttp middleware | Django middleware |
| Dependency injection | Built-in `Depends()` | Manual | Manual | Manual |
| Performance (req/s) | ~50k (uvloop) | ~10k (sync) | ~50k | ~8k |
| Python 3.10+ typing | Full support | Partial | Partial | Full |
| Ecosystem maturity | High | Very High | Medium | Very High |
| Learning curve | Low-medium | Low | Medium | High |

FastAPI is the only framework in this comparison that satisfies all of: async-native, built-in Pydantic validation, auto-docs, and streaming responses without additional libraries.

### 3.2 Specific FastAPI features used

- **`StreamingResponse`**: Returns audio bytes without buffering the entire body in the HTTP layer.
- **`Depends()`**: Injects `SpeechOrchestrator` into route handlers, making the DI pattern explicit and testable.
- **Pydantic v2 validators**: `SpeechRequest` enforces field constraints (min/max length, speed range) as L1 input validation before any processing begins.
- **`lifespan` context manager**: Cleanly separates startup (config load) from first-use (Lazy Init), and ensures graceful shutdown of open connections.
- **Exception handlers**: `@app.exception_handler(ExceptionClass)` maps all L1–L4 error classes to appropriate HTTP responses centrally.
- **`BackgroundTasks`**: Used for fire-and-forget cache writes (Redis `SET`) that do not block the audio response.

---

## 4. Consequences

### 4.1 Positive

- **L1 input errors are caught at the framework boundary**: Pydantic validation fires before any application code runs; malformed requests never reach the orchestrator.
- **Testability**: `TestClient` (synchronous) and `AsyncClient` (async) from `httpx` allow full route testing without a running server.
- **OpenAPI documentation auto-generated**: `GET /docs` provides an interactive UI that doubles as a manual testing tool; no separate documentation maintenance.
- **Async throughout**: FastAPI's `async def` routes integrate directly with `await` calls to the orchestrator, Redis, and Kokoro — no thread pool workarounds.
- **Type safety**: Full Python 3.10+ type annotations are enforced at runtime via Pydantic and checked statically by mypy.

### 4.2 Negative / Trade-offs

- **Pydantic v2 migration**: Pydantic v2 introduced breaking changes from v1; care must be taken when reading community examples (many still use v1 syntax).
- **Uvicorn production deployment**: Uvicorn alone is not production-ready (no process management); requires gunicorn with uvicorn workers, or a process supervisor. This is mitigated by the Docker deployment model (one uvicorn process per container, managed by Docker's restart policy).
- **Starlette dependency**: FastAPI is built on Starlette, adding an indirect dependency. This is acceptable and stable.
- **ASGI-only**: Cannot be run with traditional WSGI servers (gunicorn without uvicorn workers). This is not a concern for this project.

### 4.3 Impact on Other Modules

- All route handlers in `app/api/routes.py` must be `async def`.
- All middleware must conform to the ASGI `BaseHTTPMiddleware` interface.
- Exception handlers must be registered on the `FastAPI` app instance in `app/main.py`.
- The `lifespan` function is the only place where startup/shutdown lifecycle hooks are defined.

---

## 5. Alternatives Considered

### 5.1 Flask + Quart

**Rejected.** Quart is a Flask-compatible async framework, but it requires porting Flask extensions to async equivalents. The ecosystem is smaller, and Pydantic integration requires additional setup. FastAPI provides the same result with less code.

### 5.2 aiohttp

**Rejected.** aiohttp is a capable async HTTP server/client library, but lacks FastAPI's built-in Pydantic validation, dependency injection, and auto-documentation. All of these would require additional libraries and manual wiring, increasing complexity without a meaningful performance advantage.

### 5.3 Django REST Framework

**Rejected.** Django's ORM and batteries-included philosophy introduce significant overhead for a stateless proxy service. DRF's serializers are more verbose than Pydantic for this use case. Async support in Django is improving but remains less idiomatic than FastAPI.

### 5.4 Raw ASGI (Starlette only)

**Rejected.** Starlette without FastAPI would require manual route registration, manual Pydantic integration, and manual OpenAPI schema generation. FastAPI is a thin, zero-overhead layer on top of Starlette that provides all of these for free.

---

## 6. Review Notes

- This decision is binding for all route handlers in `app/api/`.
- FastAPI version is pinned to `>=0.111.0,<0.112` to prevent unexpected breaking changes.
- Any change to the ASGI framework requires a new ADR and a full Phase 3 review.

---

*ADR-001 — Accepted — 2026-04-01*
