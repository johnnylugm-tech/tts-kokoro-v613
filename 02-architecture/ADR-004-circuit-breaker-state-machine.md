# ADR-004: Circuit Breaker State Machine Design

| Field       | Value                                            |
|-------------|--------------------------------------------------|
| ID          | ADR-004                                          |
| Title       | Circuit Breaker State Machine Design             |
| Status      | Accepted                                         |
| Date        | 2026-04-01                                       |
| Author      | Agent A (architect)                              |
| Supersedes  | —                                                |
| Context     | tts-kokoro-v613 Phase 2 — Architecture           |

---

## 1. Context

### 1.1 The Need for a Circuit Breaker

The tts-kokoro-v613 proxy service is entirely dependent on the Kokoro Docker TTS backend for synthesis. If the Kokoro backend becomes unavailable (crash, network partition, OOM kill, restart), the proxy faces a critical decision:

**Without a circuit breaker:**
- Every incoming request fires an HTTP request to the unavailable backend
- Each request waits up to `read_timeout` (30s) before failing
- With 100 concurrent requests: 100 × 30s = 3000 connection-seconds of wasted resources
- The proxy's connection pool exhausts, causing cascading failures
- Memory and CPU spike as coroutines pile up waiting for timeouts
- Recovery is slow: even after Kokoro restarts, the proxy must drain all queued failing requests

**With a circuit breaker:**
- After 3 failures, the breaker opens and immediately rejects subsequent requests (< 1ms per rejection)
- After 10 seconds, the breaker allows one probe request to test recovery
- If the probe succeeds, the breaker closes and full traffic resumes
- If the probe fails, the breaker reopens for another 10 seconds

This directly satisfies:
- **FR-05**: Circuit breaker (fail≥3→Open, 10s→Half-Open, success→Closed)
- **NFR-05**: Error recovery < 10s
- **NFR-07**: Circuit breaker recovery < 10s
- **NFR-04**: API availability ≥99% (prevent cascade failures)

### 1.2 Why asyncio Requires Specific Handling

Standard circuit breaker implementations (e.g., from `pybreaker` or Java libraries) are designed for synchronous, multi-threaded environments. They use thread locks (`threading.Lock`) for state transitions.

In an `asyncio` event loop:
- There is only one OS thread executing Python bytecode
- Blocking on a `threading.Lock` blocks the entire event loop, stalling all other coroutines
- `asyncio.Lock` must be used instead — it yields to the event loop while waiting
- However, `asyncio.Lock` cannot be used from multiple event loops (not an issue in FastAPI's single-loop model)

The circuit breaker must integrate with `asyncio` natively to avoid stalling the event loop.

---

## 2. State Machine Design

### 2.1 States

```
┌─────────────────────────────────────────────────────────────────┐
│                    CIRCUIT BREAKER STATES                        │
│                                                                  │
│  ┌──────────┐                                    ┌───────────┐  │
│  │          │  failure_count >= failure_threshold │           │  │
│  │  CLOSED  │ ──────────────────────────────────► │   OPEN    │  │
│  │          │                                    │           │  │
│  │ Normal   │ ◄─────────────────────────────────  │ Fast-fail │  │
│  │ operation│  probe succeeds (HALF_OPEN→CLOSED) │ all calls │  │
│  └──────────┘                                    └─────┬─────┘  │
│        ▲                                               │         │
│        │                                    elapsed ≥  │         │
│        │                                 recovery_     │         │
│        │   probe succeeds                timeout_s     │         │
│        │   (reset counter)                             │         │
│        │                                               ▼         │
│        │                                    ┌──────────────┐    │
│        └────────────────────────────────────│  HALF_OPEN   │    │
│                                             │              │    │
│                probe fails                  │ Allow one    │    │
│                (HALF_OPEN → OPEN)           │ probe call   │    │
│                                             └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 State Definitions

| State | Description | Behavior on `call()` |
|-------|-------------|----------------------|
| **CLOSED** | Normal operation. Backend is healthy. | Execute coroutine normally. Record success/failure. |
| **OPEN** | Backend is failing. Protect the system. | Immediately raise `CircuitBreakerOpenError`. Do not call backend. |
| **HALF_OPEN** | Recovery probe window. Testing if backend is back. | Allow exactly ONE probe coroutine to execute. All other concurrent calls during the probe raise `CircuitBreakerOpenError`. |

### 2.3 Transition Rules and Threshold Values

FR-05 specifies:
- `fail ≥ 3` → OPEN (failure_threshold = 3)
- `10s elapsed` → HALF_OPEN (recovery_timeout_s = 10.0)
- probe success → CLOSED

Full transition table:

| From State | Event | To State | Action |
|-----------|-------|----------|--------|
| CLOSED | call succeeds | CLOSED | failure_count = 0 |
| CLOSED | call fails | CLOSED | failure_count += 1 |
| CLOSED | failure_count >= 3 | OPEN | record last_failure_time |
| OPEN | call arrives | OPEN | raise CircuitBreakerOpenError immediately |
| OPEN | elapsed >= 10s | HALF_OPEN | set state, allow one probe |
| HALF_OPEN | probe call arrives (first) | HALF_OPEN | execute probe normally |
| HALF_OPEN | concurrent call arrives (not probe) | HALF_OPEN | raise CircuitBreakerOpenError |
| HALF_OPEN | probe succeeds | CLOSED | failure_count = 0 |
| HALF_OPEN | probe fails | OPEN | record last_failure_time, reset probe slot |

### 2.4 What Counts as a Failure

The circuit breaker records a failure for:
- `KokoroConnectionError` — TCP connection refused or unreachable
- `KokoroTimeoutError` — request exceeded `read_timeout`
- `KokoroServerError` (subclass of `KokoroAPIError`) — 5xx server-side errors (500, 502, 503, 504)

The circuit breaker does **NOT** record a failure for:
- `KokoroClientError` (subclass of both `KokoroAPIError` and `ClientSideError`) — 4xx client errors (bad voice name, malformed request); these indicate caller bugs, not backend instability
- Exceptions raised before reaching the backend (e.g., input validation errors)

**Implementation note**: `KokoroClient.synthesize()` raises `KokoroClientError` for
`status_code < 500` and `KokoroServerError` for `status_code >= 500`. The circuit
breaker's `_on_failure()` checks `isinstance(exc, ClientSideError)` — imported from
`app.models.errors` (shared layer) — to skip client errors without a reverse-layer import.

---

## 3. Implementation

### 3.1 Complete State Machine Implementation

```python
# app/infrastructure/circuit_breaker.py
import asyncio
import time
import logging
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")

class CircuitState(str, Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """
    Async circuit breaker for protecting the Kokoro TTS backend.

    FR-05: fail≥3 → Open, 10s → Half-Open, success → Closed
    NFR-05 / NFR-07: recovery < 10s guaranteed by recovery_timeout_s=10.0
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_s: float = 10.0,
        name: str = "kokoro",
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout_s = recovery_timeout_s
        self._name = name

        # State
        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._probe_in_flight: bool = False  # Guards HALF_OPEN single-probe

        # asyncio.Lock for safe concurrent state transitions
        self._lock = asyncio.Lock()

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def seconds_until_half_open(self) -> float:
        """How many seconds remain before OPEN transitions to HALF_OPEN.
        Returns 0.0 if already in HALF_OPEN or CLOSED state."""
        if self._state != CircuitState.OPEN:
            return 0.0
        elapsed = time.monotonic() - self._last_failure_time
        remaining = self._recovery_timeout_s - elapsed
        return max(0.0, remaining)

    async def call(self, coro_factory: Callable[[], Awaitable[T]]) -> T:
        """
        Execute a coroutine through the circuit breaker.

        Args:
            coro_factory: A zero-argument callable that returns a coroutine.
                          Must be a factory (lambda/partial), not a pre-awaited
                          coroutine, because we may need to NOT execute it.

        Usage:
            result = await breaker.call(lambda: client.synthesize(text, voice, speed))

        Raises:
            CircuitBreakerOpenError: When OPEN or when HALF_OPEN and a probe
                                     is already in flight.
        """
        async with self._lock:
            current_state = await self._evaluate_state()

            if current_state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    retry_after=self.seconds_until_half_open,
                    name=self._name,
                )

            if current_state == CircuitState.HALF_OPEN:
                if self._probe_in_flight:
                    # Another probe is already testing — reject this call
                    raise CircuitBreakerOpenError(
                        retry_after=self._recovery_timeout_s,
                        name=self._name,
                    )
                self._probe_in_flight = True

        # Execute outside the lock so we don't block other state evaluations
        try:
            result = await coro_factory()
            await self._on_success()
            return result
        except Exception as exc:
            await self._on_failure(exc)
            raise
        finally:
            async with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    self._probe_in_flight = False

    def get_metrics(self) -> dict[str, Any]:
        """Return current state metrics for /health endpoint."""
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self._failure_threshold,
            "recovery_timeout_s": self._recovery_timeout_s,
            "seconds_until_half_open": self.seconds_until_half_open,
        }

    # ── Private State Transitions ───────────────────────────────────────────

    async def _evaluate_state(self) -> CircuitState:
        """
        Re-evaluate current state, applying timed transitions.
        Must be called while holding self._lock.
        """
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout_s:
                logger.info(
                    "circuit_breaker.half_open",
                    extra={"name": self._name, "elapsed_s": elapsed}
                )
                self._state = CircuitState.HALF_OPEN
        return self._state

    async def _on_success(self) -> None:
        async with self._lock:
            prev_state = self._state
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            if prev_state != CircuitState.CLOSED:
                logger.info(
                    "circuit_breaker.closed",
                    extra={"name": self._name, "prev_state": prev_state.value}
                )

    async def _on_failure(self, exc: Exception) -> None:
        """Record a failure. If threshold reached, open the circuit.

        4xx client errors (KokoroClientError) inherit ClientSideError and are
        skipped — they represent bad requests, not backend instability.
        CircuitBreaker imports from app.models.errors (shared layer), NOT from
        app.backend.kokoro_client, preventing a reverse-layer dependency.
        See: SAD §6.6a, SAD §12.2 Circular Dependency Analysis.
        """
        from app.models.errors import ClientSideError
        if isinstance(exc, ClientSideError):
            return  # Client error — do not count against circuit

        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._failure_count >= self._failure_threshold:
                prev_state = self._state
                self._state = CircuitState.OPEN
                if prev_state != CircuitState.OPEN:
                    logger.warning(
                        "circuit_breaker.open",
                        extra={
                            "name": self._name,
                            "failure_count": self._failure_count,
                            "threshold": self._failure_threshold,
                        }
                    )


class CircuitBreakerOpenError(RuntimeError):
    """Raised when the circuit breaker is in OPEN state (fast-fail)."""
    def __init__(self, retry_after: float, name: str = "backend"):
        self.retry_after = retry_after
        self.name = name
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Retry after {retry_after:.1f}s."
        )
```

### 3.2 Integration with SynthEngine

The circuit breaker wraps **each individual chunk's synthesis call** — not the entire parallel batch. This is important because:

1. Individual chunk failures should trigger the breaker, not just full-batch failures.
2. If the breaker opens mid-batch (after chunk 3 fails), remaining chunks are rejected instantly via `CircuitBreakerOpenError`.

```python
# app/processing/synth_engine.py (relevant excerpt)
async def _synthesize_one(
    self,
    req: SynthesisRequest,
    semaphore: asyncio.Semaphore,
) -> SynthesisResult:
    async with semaphore:
        start = time.perf_counter()
        audio = await self._circuit_breaker.call(
            lambda: self._client.synthesize(req.text, req.voice, req.speed)
        )
        duration_ms = (time.perf_counter() - start) * 1000
        return SynthesisResult(
            audio_bytes=audio,
            chunk_index=req.chunk_index,
            duration_ms=duration_ms,
        )
```

Note: `coro_factory` is a **lambda**, not `await self._client.synthesize(...)`. This is critical — passing a pre-awaited coroutine would start the HTTP request before the circuit breaker can decide whether to allow it.

### 3.3 Integration with asyncio.gather()

```python
# app/processing/synth_engine.py
async def synthesize_chunks(
    self,
    chunks: list[str],
    voice: str,
    speed: float,
    max_concurrency: int = 10,
) -> list[bytes]:
    semaphore = asyncio.Semaphore(max_concurrency)
    requests = [
        SynthesisRequest(text=chunk, voice=voice, speed=speed, chunk_index=i)
        for i, chunk in enumerate(chunks)
    ]

    # return_exceptions=True collects all results/exceptions without cancelling others
    raw_results = await asyncio.gather(
        *[self._synthesize_one(req, semaphore) for req in requests],
        return_exceptions=True,
    )

    # Separate successes from failures
    successes: list[SynthesisResult] = []
    failures: list[int] = []
    circuit_open = False

    for i, result in enumerate(raw_results):
        if isinstance(result, CircuitBreakerOpenError):
            circuit_open = True
        elif isinstance(result, Exception):
            failures.append(i)
        else:
            successes.append(result)

    if circuit_open and not successes:
        # All calls were rejected by the circuit breaker
        cb_err = next(r for r in raw_results if isinstance(r, CircuitBreakerOpenError))
        raise SynthesisUnavailableError(retry_after_seconds=cb_err.retry_after)

    if failures:
        # Some chunks failed, but some succeeded
        partial = [b""] * len(chunks)
        for result in successes:
            partial[result.chunk_index] = result.audio_bytes
        raise SynthesisPartialError(
            partial_results=partial,
            failed_indices=failures,
        )

    # All succeeded — sort by chunk_index and return bytes
    successes.sort(key=lambda r: r.chunk_index)
    return [r.audio_bytes for r in successes]
```

### 3.4 asyncio.Lock Usage — Why It's Needed Here

```
Timeline without lock:

  Coroutine A: reads _state = CLOSED, begins to call coro_factory()
               → hits await, yields to event loop
  Coroutine B: reads _state = CLOSED, begins to call coro_factory()
               → both proceed normally (this is fine in CLOSED state)

  Coroutine A: coro_factory() fails, _on_failure() runs
               → failure_count = 3, _state = OPEN
               → releases lock
  Coroutine B: coro_factory() fails, _on_failure() runs
               → failure_count = 4 (already past threshold — harmless)

Timeline in HALF_OPEN without lock:

  Coroutine A: reads _state = HALF_OPEN, reads _probe_in_flight = False
               → yields to event loop before setting _probe_in_flight = True
  Coroutine B: reads _state = HALF_OPEN, reads _probe_in_flight = False
               → BOTH proceed as probes — violates HALF_OPEN single-probe invariant

  asyncio.Lock prevents this: A holds the lock while reading AND setting
  _probe_in_flight, so B must wait until A has committed its decision.
```

The `async with self._lock` block in `call()` covers only the state-reading and flag-setting phase (microseconds). The actual coroutine execution happens outside the lock, so the lock never blocks I/O.

---

## 4. State Transition Tests

The following integration tests verify state machine correctness:

```python
# tests/test_infrastructure/test_circuit_breaker.py
import asyncio
import pytest
from app.infrastructure.circuit_breaker import (
    CircuitBreaker, CircuitState, CircuitBreakerOpenError
)

async def failing_coro():
    raise RuntimeError("backend error")

async def succeeding_coro():
    return b"audio"

@pytest.mark.asyncio
async def test_opens_after_threshold_failures():
    """After 3 failures, state transitions to OPEN."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_s=10.0)
    assert cb.state == CircuitState.CLOSED

    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.call(failing_coro)

    assert cb.state == CircuitState.OPEN

@pytest.mark.asyncio
async def test_fast_fails_when_open():
    """When OPEN, call() raises CircuitBreakerOpenError without executing coro."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_s=10.0)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.call(failing_coro)

    called = False
    async def probe():
        nonlocal called
        called = True
        return b"ok"

    with pytest.raises(CircuitBreakerOpenError):
        await cb.call(probe)
    assert not called  # Coroutine was never executed

@pytest.mark.asyncio
async def test_transitions_to_half_open_after_timeout(monkeypatch):
    """After recovery_timeout_s, state transitions to HALF_OPEN."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_s=0.1)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.call(failing_coro)
    assert cb.state == CircuitState.OPEN

    await asyncio.sleep(0.15)  # Wait past recovery_timeout_s

    result = await cb.call(succeeding_coro)
    assert result == b"audio"
    assert cb.state == CircuitState.CLOSED

@pytest.mark.asyncio
async def test_stays_open_on_probe_failure():
    """Failed probe in HALF_OPEN returns to OPEN."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_s=0.1)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.call(failing_coro)

    await asyncio.sleep(0.15)
    # State should now evaluate to HALF_OPEN on next call

    with pytest.raises(RuntimeError):
        await cb.call(failing_coro)  # Probe fails

    assert cb.state == CircuitState.OPEN

@pytest.mark.asyncio
async def test_closes_after_successful_probe():
    """Successful probe in HALF_OPEN transitions to CLOSED."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_s=0.1)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.call(failing_coro)

    await asyncio.sleep(0.15)

    result = await cb.call(succeeding_coro)
    assert result == b"audio"
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0
```

---

## 5. Consequences

### 5.1 Positive

- **Fail fast under load**: When Kokoro is down, the proxy returns 503 in < 1ms instead of waiting 30s per request. Under load, this prevents connection pool exhaustion.
- **Automatic recovery**: No human intervention needed to restore service. After 10s, the breaker automatically probes Kokoro. If Kokoro has restarted, the service self-heals.
- **Measurable NFR compliance**: `seconds_until_half_open` is exposed via `/health`, enabling SLO dashboards to verify NFR-05 and NFR-07.
- **asyncio-native**: Uses `asyncio.Lock` throughout; never blocks the event loop.
- **Configurable thresholds**: `failure_threshold` and `recovery_timeout_s` are in `config.yaml` — adjustable without code changes.

### 5.2 Negative / Trade-offs

- **State is in-process only**: In a multi-process deployment (e.g., gunicorn with 4 uvicorn workers), each worker has its own circuit breaker instance with its own failure count. Three failures spread across 4 workers will not trigger any single worker's breaker. Mitigation: use a single-process uvicorn deployment per container (standard for this service type), or externalize state to Redis if multi-process is required in the future.
- **HALF_OPEN rejects concurrent requests**: During the 10-second probe window, only ONE request goes through. All others get an immediate 503. This means the first seconds of recovery appear as 100% error rate even though Kokoro may be healthy. This is the correct trade-off for stability — a gentle ramp-up is preferable to a thundering herd re-hitting a recovering backend.
- **No gradual degradation**: The breaker is binary (CLOSED=full traffic, OPEN=no traffic). A more sophisticated implementation could allow a percentage of traffic through during recovery. This is not needed for this service's scale.

### 5.3 Integration Contract

Any code that calls `KokoroClient` **must** go through `CircuitBreaker.call()`. Direct calls to `KokoroClient.synthesize()` that bypass the circuit breaker are a defect. This is enforced by:

1. `KokoroClient` is not directly accessible from `SpeechOrchestrator` — it is wrapped by `SynthEngine`, which holds the `CircuitBreaker` reference.
2. Code review checklist item: no direct `kokoro_client.synthesize()` call outside `synth_engine.py`.

---

## 6. Alternatives Considered

### 6.1 `pybreaker` Library

The `pybreaker` library provides a circuit breaker implementation for Python.

**Rejected**: `pybreaker` uses `threading.Lock` internally, which is not compatible with asyncio (would block the event loop during state transitions). An async-native implementation is required. Wrapping `pybreaker` in `asyncio.to_thread()` is possible but adds unnecessary complexity when the implementation itself is straightforward.

### 6.2 Hystrix-style Bulkhead Pattern

Add a bulkhead (semaphore limiting total concurrent Kokoro calls) in addition to the circuit breaker.

**Partially adopted**: The `SynthEngine.synthesize_chunks()` already uses `asyncio.Semaphore(max_concurrency)` to cap concurrent Kokoro connections. This is the equivalent of a bulkhead. It is separate from the circuit breaker — both are in effect simultaneously.

### 6.3 Exponential Backoff Without Circuit Breaker

Retry each call up to N times with exponential backoff, without a circuit breaker.

**Rejected as the sole resilience mechanism**: Retry-only approaches still execute the failing call for every retry attempt. Under sustained backend failure, retries multiply the load. The circuit breaker is fundamentally different: it stops calling the backend entirely during the OPEN period, then tests recovery with a single probe.

Retries remain in place at the `KokoroClient` level (3 retries per chunk call when the breaker is CLOSED) — the circuit breaker and retry logic are complementary, not alternatives.

---

*ADR-004 — Accepted — 2026-04-01*
