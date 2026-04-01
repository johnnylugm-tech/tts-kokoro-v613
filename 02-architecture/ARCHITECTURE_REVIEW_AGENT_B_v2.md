# Architecture Re-Review — Agent B (Reviewer) v2

| Field        | Value                                                  |
|--------------|--------------------------------------------------------|
| Document     | ARCHITECTURE_REVIEW_AGENT_B_v2.md                     |
| Reviewing    | SAD.md v2.0.0 (updated) + ADR-003 (updated) + ADR-004 (updated) |
| Phase        | 2 — Architecture Review re-check (methodology-v2 v6.13) |
| Date         | 2026-04-01                                             |
| Reviewer     | Agent B — reviewer role                                |
| Prior review | ARCHITECTURE_REVIEW_AGENT_B.md (6 BLOCK issues)        |
| Session ID   | agent:claude:agentb:reviewer:phase2-review-v2          |

---

## Section 1: BLOCK Issue Resolution Summary

| Issue | Description | Status |
|-------|-------------|--------|
| BLOCK-01 | FR-03 chunking algorithm deviation from SRS must be documented in ADR-003 | **RESOLVED** |
| BLOCK-02 | `circuit_breaker.py` must not import `KokoroAPIError` from `kokoro_client.py` | **RESOLVED** |
| BLOCK-03 | `_on_failure()` signature must accept `exc: Exception` parameter | **RESOLVED** |
| BLOCK-04 | `get_orchestrator()` FastAPI dependency factory must be defined | **RESOLVED** |
| BLOCK-05 | `SynthEngine.__init__` must accept `circuit_breaker` parameter | **RESOLVED** |
| BLOCK-06 | `KokoroClient._get_client()` and `AudioConverter._get_ffmpeg()` must use `asyncio.Lock` with double-checked locking | **RESOLVED** |

**All 6 BLOCK issues are resolved. Proceed to detailed findings.**

---

## Section 2: Detailed BLOCK Findings

---

### BLOCK-01 — FR-03 Chunking SRS Deviation

**What was fixed**: ADR-003 §1.4 now contains an explicit "SRS Deviation Notice — Deliberate Algorithm Divergence from FR-03" section. It provides a full comparison table covering all three divergences identified in the original review:

- Level 2 boundary chars: `。；：` (SRS) vs `，；：,;:` (ADR-003) — rationale: `。` is already consumed at Level 1; `，` is the correct Chinese clause separator.
- Level 3 boundary chars: `，` (SRS) vs linguistic particles + whitespace (ADR-003) — rationale: after Level 2 splits on `，`, no commas remain; particles are the true Level 3 boundaries.
- Recursion trigger threshold: >100 chars (SRS) vs >250 chars (ADR-003) — rationale: 100-char intermediate threshold would produce unnecessarily short fragments degrading synthesis quality.

The deviation section explicitly states: *"This deviation is deliberate and approved. Phase 3 developers must implement the ADR-003 specification, not the SRS FR-03 literal specification."*

**Assessment**: Fully sufficient. The deviation is documented, justified, and authoritative. RESOLVED.

---

### BLOCK-02 — Circular Dependency / Reverse-Layer Import

**What was fixed**: The fix is comprehensive and well-engineered:

1. A new **§6.6a** (`app/models/errors.py`) defines `ClientSideError` as a marker base class in the shared models layer, accessible to both Layer 4 (`kokoro_client.py`) and Layer 5 (`circuit_breaker.py`) without creating a cycle.

2. **ADR-004 §2.4** and **§3.1** are updated to confirm that `_on_failure()` uses `from app.models.errors import ClientSideError` — explicitly noting "imported from `app.models.errors` (shared layer), NOT from `app.backend.kokoro_client`, preventing a reverse-layer import."

3. **SAD §6.6** `KokoroClientError` is defined as inheriting from both `KokoroAPIError` and `ClientSideError`, creating the correct mixin.

4. **SAD §12.2** dependency table is updated: the `circuit_breaker → kokoro_client` entry is marked **RESOLVED**.

**Residual issue found — NEW-01 (BLOCK-level)**: In the SAD §6.6 code block for `app/backend/kokoro_client.py`, the file-level imports are:
```python
import httpx
import asyncio
from app.infrastructure.config_loader import AppConfig
```
But line 741 defines:
```python
class KokoroClientError(KokoroAPIError, ClientSideError):
```
`ClientSideError` is used in the class definition but **is not imported** anywhere in the §6.6 code block. A Phase 3 developer implementing this file literally would get a `NameError: name 'ClientSideError' is not defined`. The missing import is:
```python
from app.models.errors import ClientSideError
```
This must be added to the imports section of §6.6. The fix for BLOCK-02 is architecturally correct but introduces an incomplete code sample. See NEW-01 below.

---

### BLOCK-03 — `_on_failure()` Signature Consistency

**What was fixed**: SAD §6.7 `CircuitBreaker._on_failure()` now correctly declares:
```python
async def _on_failure(self, exc: Exception) -> None:
```
The implementation shown includes the `isinstance(exc, ClientSideError)` guard and the explicit note that `ClientSideError` is imported from `app.models.errors`. This is consistent with ADR-004 §3.1.

**Assessment**: Fully resolved. The signatures are now identical between SAD §6.7 and ADR-004 §3.1. RESOLVED.

---

### BLOCK-04 — `get_orchestrator()` Dependency Factory

**What was fixed**: A new **§6.14** (`app/api/dependencies.py`) is now defined with:

1. `create_orchestrator()` — builds the full dependency graph, instantiating CircuitBreaker, RedisCache, AudioConverter (Layer 5), KokoroClient (Layer 4), SSMLParser, LexiconMapper, TextChunker, SynthEngine (Layer 3), and finally SpeechOrchestrator (Layer 2). All constructor arguments are shown, including the `circuit_breaker` and `kokoro_client` being passed into `SynthEngine`.

2. `get_orchestrator(request: Request) -> SpeechOrchestrator` — the FastAPI `Depends()` factory that returns `request.app.state.orchestrator`.

3. A `lifespan` context manager for `app/main.py` showing where `create_orchestrator()` is called at startup and how shutdown cleanup is handled.

4. A note explaining why `app.state` is preferred over `@lru_cache` (asyncio event loop readiness at import time).

**Assessment**: Fully sufficient. The wiring is complete, the singleton lifecycle is correct, and the `Depends()` pattern is properly shown. RESOLVED.

**Minor observation (INFO-level only)**: The `CircuitBreakerConfig` in §6.10 does not have a `name` field, but `create_orchestrator()` in §6.14 passes `name=config.circuit_breaker.name`. This is an inconsistency between the Pydantic model and the factory code — `config.circuit_breaker.name` would raise `AttributeError`. Recommend adding `name: str = "kokoro"` to `CircuitBreakerConfig`. This does not block Phase 3 (the default `"kokoro"` in `CircuitBreaker.__init__` would be used if the field is absent) but is a clean code issue.

---

### BLOCK-05 — `SynthEngine.__init__` Missing `circuit_breaker` Parameter

**What was fixed**: SAD §6.5 `SynthEngine.__init__` now accepts both parameters:
```python
def __init__(
    self,
    kokoro_client: "KokoroClient",
    circuit_breaker: "CircuitBreaker",
) -> None:
    self._client = kokoro_client
    self._circuit_breaker = circuit_breaker
```
The docstring explains the injection pattern and the intended usage (`await self._circuit_breaker.call(lambda: ...)`).

**Assessment**: Fully resolved. The interface is complete and implementable. RESOLVED.

---

### BLOCK-06 — `asyncio.Lock` for Lazy Init in `KokoroClient` and `AudioConverter`

**What was fixed**:

**KokoroClient (§6.6)**: `_get_client()` now implements full double-checked locking:
```python
def __init__(self, config: AppConfig) -> None:
    ...
    self._init_lock = asyncio.Lock()  # Guards double-initialization race

async def _get_client(self) -> httpx.AsyncClient:
    if self._client is None:                       # First check (no lock)
        async with self._init_lock:
            if self._client is None:               # Second check (under lock)
                self._client = httpx.AsyncClient(...)
    return self._client
```

**AudioConverter (§6.9)**: `_get_ffmpeg()` now implements identical double-checked locking:
```python
def __init__(self) -> None:
    self._ffmpeg_path: str | None = None
    self._init_lock = asyncio.Lock()  # Guards double-initialization race

async def _get_ffmpeg(self) -> str:
    if self._ffmpeg_path is None:                  # First check (no lock)
        async with self._init_lock:
            if self._ffmpeg_path is None:          # Second check (under lock)
                path = shutil.which("ffmpeg")
                if path is None:
                    raise AudioConverterError(...)
                self._ffmpeg_path = path
    return self._ffmpeg_path
```

Both implementations match the ADR-002 §3.2 canonical pattern with `self._init_lock = asyncio.Lock()` in `__init__` and proper double-checked locking.

**Assessment**: Fully resolved and consistent with ADR-002. RESOLVED.

---

## Section 3: WARN Fix Status

| Issue | Description | Status |
|-------|-------------|--------|
| WARN-01 | `synth_engine.py` path inconsistency (`app/processing/` vs `app/synth/`) | **PARTIAL** |
| WARN-05 | `RedisCache.__init__` should accept `config: AppConfig` | **RESOLVED** |
| WARN-08 | `health_router` should be defined with `/health` and `/ready` endpoints | **RESOLVED** |

---

### WARN-01 — `synth_engine.py` Path: PARTIAL

**What was fixed**: The §3 Architecture Layers text now correctly reads:
```
• app/synth/synth_engine.py  (FR-04) ← async I/O, own subdir
```
With an explanatory comment distinguishing it from `app/processing/`.

The Module Boundary Map (§4), §6.14 dependencies.py import, and §10 Directory Structure all consistently use `app/synth/synth_engine.py`.

**Residual issue**: Two locations still have the wrong path:

1. **§6.5 section header** reads: `### 6.5 Synthesis Engine (app/processing/synth_engine.py)` — the section heading still names the wrong directory. The code comment inside (`# app/synth/synth_engine.py`) is correct, but the heading creates an immediate contradiction for any developer reading the table of contents.

2. **§6.13 orchestrator import** reads: `from app.processing.synth_engine import SynthEngine` — this is a broken import. The correct import should be `from app.synth.synth_engine import SynthEngine` (which is what §6.14 uses). This is a directly incorrect Python statement that would cause an `ImportError`.

**Assessment**: PARTIAL. The §3 fix is correct, but two concrete errors remain. The §6.13 wrong import path is the more serious issue as it produces broken Python code.

---

### WARN-05 — `RedisCache.__init__` Signature: RESOLVED

SAD §6.8 now defines:
```python
def __init__(self, config: "AppConfig") -> None:
```
with a docstring explicitly noting "Follows ADR-002 §3.4: constructor accepts AppConfig, not raw fields." The implementation correctly reads `config.redis.url`, `config.redis.ttl_seconds`. Consistent with ADR-002 §3.4 and with §6.14 `create_orchestrator()`. RESOLVED.

---

### WARN-08 — `health_router` Definition: RESOLVED

SAD §6.15 now defines `app/api/health.py` containing `health_router = APIRouter(tags=["health"])` with both:
- `GET /health` → `HealthResponse` (liveness probe, circuit breaker metrics)
- `GET /ready` → `ReadyResponse` (readiness probe, Kokoro + Redis connectivity check)

The registration in `app/main.py` is also shown. Both models are defined. The `EXEMPT_PATHS` in `AuthMiddleware` already includes `/health` and `/ready`. RESOLVED.

---

## Section 4: New Issues Discovered During Re-Review

---

### NEW-01 — Missing `ClientSideError` Import in `kokoro_client.py` Code Sample (BLOCK-level)

**SAD Section**: SAD §6.6 (`app/backend/kokoro_client.py`)

**Issue**: The code block for `kokoro_client.py` uses `ClientSideError` as a base class for `KokoroClientError`:
```python
class KokoroClientError(KokoroAPIError, ClientSideError):
    """L4 sub: Kokoro returned 4xx — client error, NOT counted by CircuitBreaker."""
    pass
```
But the imports section for that file only contains:
```python
import httpx
import asyncio
from app.infrastructure.config_loader import AppConfig
```
`ClientSideError` is never imported. A Phase 3 developer implementing `kokoro_client.py` from this spec would get:
```
NameError: name 'ClientSideError' is not defined
```
The missing line is:
```python
from app.models.errors import ClientSideError
```
This must be added to the imports in §6.6. The architectural design is correct — the fix is a one-line addition to the code sample.

**Severity**: BLOCK — a Phase 3 developer implementing this module verbatim would produce broken code.

---

### NEW-02 — `CircuitBreakerConfig` Pydantic Model Missing `name` Field (WARN-level)

**SAD Section**: SAD §6.10 `CircuitBreakerConfig` vs SAD §6.14 `create_orchestrator()`

**Issue**: `CircuitBreakerConfig` in §6.10 is:
```python
class CircuitBreakerConfig(BaseModel):
    failure_threshold: int = 3
    recovery_timeout_s: float = 10.0
```
But `create_orchestrator()` in §6.14 calls:
```python
circuit_breaker = CircuitBreaker(
    failure_threshold=config.circuit_breaker.failure_threshold,
    recovery_timeout_s=config.circuit_breaker.recovery_timeout_s,
    name=config.circuit_breaker.name,   # ← AttributeError: 'CircuitBreakerConfig' has no field 'name'
)
```
`config.circuit_breaker.name` would raise `AttributeError` at runtime. Fix: add `name: str = "kokoro"` to `CircuitBreakerConfig`.

**Severity**: WARN (non-blocking because `CircuitBreaker.__init__` defaults to `name="kokoro"` — a Phase 3 developer would likely catch this during first run and fix it; however it is still incorrect code in the SAD).

---

### NEW-03 — §6.5 Section Header Path Still Wrong (WARN-level, residual from WARN-01)

**SAD Section**: SAD §6.5 section heading

**Issue**: As noted in WARN-01 above, the section heading `### 6.5 Synthesis Engine (app/processing/synth_engine.py)` is wrong. The correct path is `app/synth/synth_engine.py`. This is a documentation consistency error, not a logic error.

**Severity**: WARN (same severity as original WARN-01 — affects developer understanding but the code comment inside the block is correct).

---

### NEW-04 — §6.13 Orchestrator Import Path Wrong (BLOCK-level)

**SAD Section**: SAD §6.13 (`app/orchestrator/speech_orchestrator.py`)

**Issue**: The imports in §6.13 include:
```python
from app.processing.synth_engine import SynthEngine
```
The correct path is `app/synth/synth_engine.py`, so the correct import is:
```python
from app.synth.synth_engine import SynthEngine
```
This is confirmed by §6.14 which correctly uses `from app.synth.synth_engine import SynthEngine`. The §6.13 import is a broken Python statement that would cause `ModuleNotFoundError` if implemented as written.

**Severity**: BLOCK — directly broken import in the orchestrator definition. A Phase 3 developer using §6.13 as their orchestrator template would produce a module that fails to start.

---

## Section 5: Final Verdict

### Consolidated status

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| BLOCK-01 | ADR-003 SRS deviation note | BLOCK (original) | RESOLVED |
| BLOCK-02 | Circular dependency / reverse-layer import | BLOCK (original) | RESOLVED |
| BLOCK-03 | `_on_failure(exc)` signature | BLOCK (original) | RESOLVED |
| BLOCK-04 | `get_orchestrator()` factory definition | BLOCK (original) | RESOLVED |
| BLOCK-05 | `SynthEngine.__init__` circuit_breaker param | BLOCK (original) | RESOLVED |
| BLOCK-06 | `asyncio.Lock` double-checked locking | BLOCK (original) | RESOLVED |
| WARN-01 | synth_engine path (§3 text) | WARN (original) | PARTIAL |
| WARN-05 | `RedisCache(config: AppConfig)` | WARN (original) | RESOLVED |
| WARN-08 | `health_router` defined with both endpoints | WARN (original) | RESOLVED |
| **NEW-01** | Missing `ClientSideError` import in §6.6 code | **BLOCK (new)** | **OPEN** |
| **NEW-02** | `CircuitBreakerConfig` missing `name` field | WARN (new) | OPEN |
| **NEW-03** | §6.5 section header wrong path | WARN (new, residual) | OPEN |
| **NEW-04** | §6.13 orchestrator import wrong path | **BLOCK (new)** | **OPEN** |

### Verdict: REJECT (targeted — 2 new BLOCKs must be fixed)

The core architecture is sound and all 6 original BLOCK issues have been correctly resolved. The fixes for BLOCK-02 through BLOCK-06 are high quality and the dependency injection wiring in §6.14 is particularly well done. However, the BLOCK-02 fix for `ClientSideError` introduced NEW-01 (missing import in §6.6), and the partial WARN-01 fix left NEW-04 (wrong import path in §6.13).

**Two targeted fixes required before Phase 3 can start:**

1. **NEW-01**: Add `from app.models.errors import ClientSideError` to the imports in §6.6 (`kokoro_client.py` code block). One line fix.

2. **NEW-04**: Change `from app.processing.synth_engine import SynthEngine` to `from app.synth.synth_engine import SynthEngine` in §6.13. One line fix.

**Two WARN items to fix in the same pass (recommended, not strictly blocking):**

3. **NEW-02**: Add `name: str = "kokoro"` to `CircuitBreakerConfig` in §6.10.

4. **NEW-03**: Update the §6.5 section heading from `app/processing/synth_engine.py` to `app/synth/synth_engine.py`.

These are all mechanical corrections — none require architectural rethinking. Once these four items are addressed, the SAD will be internally consistent and fully approvable. A third review cycle should not be necessary if Agent A fixes all four items listed above.

---

## Section 6: Sign-off

| Field | Value |
|-------|-------|
| **Reviewer** | Agent B — reviewer |
| **Role** | Critical architecture reviewer ("挑刺") |
| **Session ID** | agent:claude:agentb:reviewer:phase2-review-v2 |
| **Methodology** | methodology-v2 v6.13 — Phase 2 Architecture Review |
| **Date** | 2026-04-01 |
| **Verdict** | REJECT — 2 new BLOCK issues (NEW-01, NEW-04); all 6 original BLOCKs resolved |
| **Re-review required** | Yes — targeted; only 4 line-level fixes needed |

---

*ARCHITECTURE_REVIEW_AGENT_B_v2.md — Agent B reviewer — 2026-04-01*

---

## Final Verdict (v2 re-check)

**Date:** 2026-04-01
**Session ID:** agent:claude:agentb:reviewer:phase2-review-v2

### Targeted Fix Verification

| Issue | Fix Applied | Verified |
|-------|-------------|----------|
| NEW-01 | `from app.models.errors import ClientSideError` import added to §6.6 `kokoro_client.py` code block (line 659) | RESOLVED |
| NEW-02 | `name: str = "kokoro"` field added to `CircuitBreakerConfig` in §6.10 (line 1050) | RESOLVED |
| NEW-03 | §6.5 section heading corrected to `app/synth/synth_engine.py` (line 562) | RESOLVED |
| NEW-04 | Orchestrator import corrected to `from app.synth.synth_engine import SynthEngine` in §6.13 (line 1184) | RESOLVED |

### Confirmation

All 4 issues raised in the v2 review are confirmed resolved:

- **NEW-01**: `§6.6` code block now correctly imports `ClientSideError` from `app.models.errors` on the first import line, with an inline comment explaining the architectural intent.
- **NEW-02**: `CircuitBreakerConfig` in `§6.10` now includes `name: str = "kokoro"` as a third field, matching the circuit breaker constructor signature used in §6.13.
- **NEW-03**: `§6.5` section heading reads `### 6.5 Synthesis Engine (`app/synth/synth_engine.py`)` — correct path, no longer `app/processing/`.
- **NEW-04**: `§6.13` orchestrator import reads `from app.synth.synth_engine import SynthEngine` — correct module path, with inline comment confirming the subdir.

All 6 original BLOCK issues (BLOCK-01 through BLOCK-06) were already confirmed resolved in the second review and remain unaffected.

### Final Verdict

✅ APPROVE — Phase 3 can begin.

SAD.md is internally consistent, all import paths are correct, the circular-dependency resolution via `app/models/errors.py` is properly documented throughout, and all config models match their usage in wiring code.

---

*Final sign-off: Agent B — agent:claude:agentb:reviewer:phase2-review-v2 — 2026-04-01*
