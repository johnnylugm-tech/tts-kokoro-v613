# Architecture Review — Agent B (Reviewer)

| Field        | Value                                              |
|--------------|----------------------------------------------------|
| Document     | ARCHITECTURE_REVIEW_AGENT_B.md                     |
| Reviewing    | SAD.md v2.0.0 + ADR-001 through ADR-004            |
| Phase        | 2 — Architecture Review (methodology-v2 v6.13)     |
| Date         | 2026-04-01                                         |
| Reviewer     | Agent B — reviewer role                            |
| SRS Ref      | Phase 1 SRS v6.13.1 (`01-requirements/SRS.md`)     |
| Session ID   | agent:claude:agentb:reviewer:phase2-review         |

---

## Section 1: 逐項審查結果 (5-Dimension Checklist)

### Dimension 1 — 需求覆蓋完整性
*All FR/NFR in SRS have corresponding modules in SAD*

| Item | Check | Notes |
|------|-------|-------|
| FR-01 Taiwan Lexicon → `LexiconMapper` (app/processing/lexicon_mapper.py) | ✅ | Module defined, ≥50 entry requirement noted |
| FR-02 SSML Parsing → `SSMLParser` (app/processing/ssml_parser.py) | ✅ | All 6 SRS tags covered; fallback pure-text on parse failure mentioned |
| FR-03 Chunking ≤250 chars → `TextChunker` (app/processing/text_chunker.py) | ⚠️ | **Algorithm diverges from SRS spec — see Problem #1** |
| FR-04 Parallel synthesis + direct MP3 concat → `SynthEngine` | ✅ | asyncio.gather() + `b"".join()` both shown |
| FR-05 Circuit Breaker (fail≥3→Open, 10s→Half-Open) → `CircuitBreaker` | ✅ | Exact thresholds preserved in config defaults |
| FR-06 Redis cache, 24h TTL, graceful degradation → `RedisCache` | ✅ | Lazy Init + None-return on unavailability shown |
| FR-07 CLI tool `tts-v610` → `app/cli/main.py` | ⚠️ | **CLI interface has partial mismatch with SRS — see Problem #2** |
| FR-08 ffmpeg MP3↔WAV → `AudioConverter` | ✅ | Lazy Init with PATH discovery |
| NFR-01 TTFB < 300ms | ✅ | Cache hit path + async pipeline described |
| NFR-02 Reliability / fallback | ✅ | SSML fallback, circuit breaker, graceful Redis degrade all documented |
| NFR-03 Security (Auth, Authz, TLS, Data Protection) | ⚠️ | **Authorization (voice/model access control) missing — see Problem #3** |
| NFR-04 Maintainability / test coverage ≥80% | ✅ | pytest-cov gate, per-module test files, type annotations |
| NFR-05/07 Error recovery < 10s | ✅ | recovery_timeout_s=10.0 default, metric exposed |
| NFR-06 Unit test coverage ≥80% | ✅ | Coverage gate in pytest.ini |

**Dimension 1 Verdict**: ⚠️ 11/14 clean; 3 items require attention.

---

### Dimension 2 — 模組設計品質
*Module boundaries clear, no responsibility overlap, unidirectional dependencies*

| Item | Check | Notes |
|------|-------|-------|
| Single responsibility per module | ✅ | Each module owns exactly one FR |
| No Layer N importing Layer N-1 | ✅ | Explicitly stated and CI-enforced |
| SynthEngine in `app/synth/` directory | ⚠️ | **Directory mismatch: Section 3 says `app/processing/synth_engine.py`; Section 10 shows `app/synth/synth_engine.py` — see Problem #4** |
| Orchestrator does not import from API layer | ✅ | Prohibited cycle listed in §12.2 |
| ConfigLoader has zero app-module imports | ✅ | Explicitly prohibited in §12.2 |
| No circular dependencies | ✅ | §12.2 table covers all candidate cycles |
| `circuit_breaker` imports `KokoroAPIError` from `kokoro_client` | 🔴 | **Reverse-layer import creates a hidden circular dependency — see Problem #5** |
| `RedisCache` constructor signature inconsistency | ⚠️ | **See Problem #6** |

**Dimension 2 Verdict**: ⚠️/🔴 — Two structural issues found.

---

### Dimension 3 — 錯誤處理完整性
*L1-L4 mapped to modules, Retry/Fallback with specific params, Circuit Breaker conditions*

| Item | Check | Notes |
|------|-------|-------|
| L1 errors → 4xx, no retry | ✅ | ValidationError→422, SSMLParseError→422, 401/403 shown |
| L2 errors → retry 3× with backoff | ⚠️ | `AudioConverterError` says "3× retry" in §7.2 table but **no backoff timing is specified anywhere — see Problem #7** |
| L3 errors → graceful degrade | ✅ | RedisError → no-op, SynthesisPartialError → 206 partial |
| L4 errors → CB + 503 | ✅ | KokoroConnectionError/APIError/TimeoutError all route to CB |
| Circuit Breaker fail≥3→Open matches FR-05 | ✅ | failure_threshold=3 in config default |
| Circuit Breaker 10s→Half-Open matches FR-05 | ✅ | recovery_timeout_s=10.0 in config default |
| CB only counts 5xx, not 4xx | ✅ | Explicitly stated in ADR-004 §2.4 |
| Retry-After header on 503 | ✅ | `retry_after` in ErrorResponse model |
| `_on_failure()` signature inconsistency — SAD vs ADR | 🔴 | **See Problem #8** |
| SSML fallback behaviour not wired in orchestrator code | ⚠️ | **See Problem #9** |

**Dimension 3 Verdict**: ⚠️/🔴 — 3 items need resolution.

---

### Dimension 4 — 技術選型合理性
*All tech choices have ADR, no hallucinated frameworks, all external deps use Lazy Init*

| Item | Check | Notes |
|------|-------|-------|
| FastAPI → ADR-001 | ✅ | Full rationale, alternatives compared |
| Lazy Init → ADR-002 | ✅ | All three external deps covered |
| 3-level chunking → ADR-003 | ✅ | Algorithm, edge cases, alternatives |
| Circuit Breaker → ADR-004 | ✅ | asyncio-native, alternatives considered |
| `typer` used for CLI (SRS did not specify CLI framework) | ✅ | Reasonable choice; no ADR needed for this magnitude |
| `defusedxml` for SSML XXE prevention | ✅ | Security-motivated, cited in §8 |
| `structlog` for logging (no ADR) | ℹ️ | Minor — no ADR required but no justification given either |
| `slowapi` for rate limiting mentioned as optional, no ADR | ⚠️ | **See Problem #10** |
| `KokoroClient` in SAD §6.6 is missing `asyncio.Lock` for Lazy Init | 🔴 | **See Problem #11** |
| `AudioConverter` in SAD §6.9 is missing `asyncio.Lock` for Lazy Init | 🔴 | **See Problem #11** |
| All external deps (httpx, redis, ffmpeg) use Lazy Init | ✅ | Covered by ADR-002 pattern |
| `pydub` mentioned in FR-04 SRS as optional crossfade | ⚠️ | **See Problem #12** |

**Dimension 4 Verdict**: ⚠️/🔴 — Critical Lazy Init inconsistency between ADR-002 and SAD §6.

---

### Dimension 5 — 實作可行性
*Phase 3 developer can start coding directly from SAD, no ambiguous designs*

| Item | Check | Notes |
|------|-------|-------|
| All module file paths are explicit | ⚠️ | `synth_engine.py` path ambiguous — see Problem #4 |
| All public interface signatures are typed | ✅ | Python 3.10+ type annotations on all public methods |
| Dependency injection wiring is shown | ✅ | `SpeechOrchestrator.__init__` lists all injected deps |
| `get_orchestrator()` dependency factory is not defined | 🔴 | **See Problem #13** |
| `health_router` imported in `main.py` code snippet but never defined | ⚠️ | **See Problem #14** |
| SynthEngine missing `_circuit_breaker` in SAD §6.5 `__init__` | 🔴 | **See Problem #15** |
| Config schema in §11 has `redis.max_connections` and `redis.socket_timeout` not present in `RedisConfig` Pydantic model in §6.10 | ⚠️ | **See Problem #16** |
| `connect_timeout` present in `config.yaml` §11 but absent from `KokoroConfig` Pydantic model in §6.10 | ⚠️ | **See Problem #16** |
| Directory structure in §10 is sufficient for a Phase 3 developer to scaffold | ✅ | All directories and files named |
| `lexicon_tw.json` schema is unspecified | ⚠️ | **See Problem #17** |

**Dimension 5 Verdict**: 🔴 — Multiple implementation blockers for Phase 3 developer.

---

## Section 2: 發現的問題清單

---

### 🔴 BLOCK — Must fix before Phase 3

---

#### BLOCK-01: FR-03 Chunking Level 2 spec diverges from SRS

**SAD Section**: ADR-003 §2.1, SAD §6.4
**SRS Reference**: FR-03

**Issue**: The SRS defines the three-level split triggers differently from the ADR:

| Level | SRS Spec | SAD / ADR-003 Spec |
|-------|----------|--------------------|
| Level 1 (Sentence) | `。？！!?\n` | `。！？.!?\n\r` — adds `\r`, includes `.` |
| Level 2 (Clause) | `。；：` (triggers when piece still >100 chars) | `，；：,;:` — uses `，` not `。`, adds `,` |
| Level 3 (Phrase) | `，` (triggers when piece still >100 chars) | spaces + Chinese particles (的了吧呢...) |

Critical discrepancy: The SRS uses `。` (full-stop) as a Level 2 separator, implying sub-sentence-level splitting at periods. The SAD uses `，` (comma) at Level 2, which is arguably more linguistically correct, but it **contradicts the SRS without a documented deviation or ADR entry**. The SRS also specifies a ">100 char" threshold for when to recurse into lower levels — the SAD ignores this and recurses immediately when any piece exceeds 250 chars (not 100 chars). This means the SAD implementation will produce different chunks than the SRS specifies.

**Proposed Fix**: Either (a) update SRS §FR-03 to match the SAD/ADR-003 algorithm (preferred, as the ADR-003 design is linguistically superior), documenting it as a deliberate deviation with the superior rationale; or (b) add an explicit SRS deviation note to ADR-003 §1. This must be resolved before Phase 3 writes the chunker.

---

#### BLOCK-02: Reverse-layer import in CircuitBreaker creates hidden circular dependency

**SAD Section**: SAD §12.2, ADR-004 §3.1 (`_on_failure` method)
**SAD §12.2 states**: `config_loader → any app module` is **PROHIBITED**.

**Issue**: In ADR-004 §3.1, `CircuitBreaker._on_failure()` contains:
```python
from app.backend.kokoro_client import KokoroAPIError
if isinstance(exc, KokoroAPIError) and exc.status_code < 500:
    return
```

This is a **Layer 5 module** (`circuit_breaker.py`) importing from a **Layer 4 module** (`kokoro_client.py`). This violates the Layer Dependency Rule in §3: "Layer N may only import from Layer N+1 or lower." Layer 5 is the lowest layer — it must not import from Layer 4. Additionally, this creates an actual circular risk: `kokoro_client.py` imports `CircuitBreaker` (via `SynthEngine`), and `circuit_breaker.py` imports `KokoroAPIError` from `kokoro_client.py`.

The SAD §6.6 `KokoroClient` code and SAD §6.7 `CircuitBreaker` code do not show this import, but ADR-004 (the authoritative implementation reference) does include it. The two documents are inconsistent.

**Proposed Fix**: Remove the `KokoroAPIError` import from `circuit_breaker.py`. Instead, define a protocol-level exception class (e.g., `ClientSideError`) in `app/infrastructure/` or `app/models/errors.py` that `KokoroAPIError` inherits from. The CircuitBreaker checks `isinstance(exc, ClientSideError)` without importing from `kokoro_client`.

---

#### BLOCK-03: `_on_failure()` signature inconsistency between SAD and ADR — breaks implementation

**SAD Section**: SAD §6.7 vs ADR-004 §3.1

**Issue**: The two documents define `_on_failure()` with different signatures:

- **SAD §6.7**: `async def _on_failure(self) -> None:` — takes no exception argument, always increments counter
- **ADR-004 §3.1**: `async def _on_failure(self, exc: Exception) -> None:` — takes the exception, conditionally skips 4xx errors

These cannot both be implemented. The ADR-004 version is more correct (4xx errors should not trip the breaker), but the SAD version is what a Phase 3 developer would use as their primary reference. If Phase 3 implements the SAD version, 4xx client errors (e.g., malformed voice name) will incorrectly trip the circuit breaker after 3 bad requests.

**Proposed Fix**: Update SAD §6.7 to match ADR-004's signature: `async def _on_failure(self, exc: Exception) -> None:`. Mark the resolution in both documents.

---

#### BLOCK-04: `get_orchestrator()` dependency factory is never defined

**SAD Section**: SAD §6 (ADR-001 §2 also references it)
**ADR-001 §2 Code**: `orchestrator: SpeechOrchestrator = Depends(get_orchestrator)`

**Issue**: `get_orchestrator()` is used in the route handler as a FastAPI `Depends()` factory but is never defined anywhere in the SAD. This is the wiring point that connects all the injected dependencies (SSMLParser, LexiconMapper, TextChunker, SynthEngine, RedisCache, AudioConverter, KokoroClient, CircuitBreaker, config). Without this factory, Phase 3 cannot wire the application.

**Proposed Fix**: Add a §6.14 defining `get_orchestrator()` as a FastAPI dependency factory. It should use `@lru_cache` or `app.state` to return a singleton orchestrator. Show how `KokoroClient`, `CircuitBreaker`, `RedisCache`, etc. are instantiated and injected.

---

#### BLOCK-05: SynthEngine `__init__` is missing `circuit_breaker` parameter in SAD §6.5

**SAD Section**: SAD §6.5 SynthEngine

**Issue**: SAD §6.5 defines `SynthEngine.__init__` as:
```python
def __init__(self, kokoro_client: "KokoroClient") -> None:
    self._client = kokoro_client
```

But in both ADR-004 §3.2 and the data flow in §5.1, the SynthEngine calls `self._circuit_breaker.call(...)`. The `CircuitBreaker` is never injected into `SynthEngine` in the SAD interface definition. This means the SAD §6.5 interface is incomplete and unimplementable as written.

**Proposed Fix**: Update `SynthEngine.__init__` to accept `circuit_breaker: CircuitBreaker` as a parameter:
```python
def __init__(self, kokoro_client: "KokoroClient", circuit_breaker: "CircuitBreaker") -> None:
```

---

#### BLOCK-06: `KokoroClient` and `AudioConverter` in SAD §6 are missing `asyncio.Lock` — contradicts ADR-002

**SAD Section**: SAD §6.6 (KokoroClient), SAD §6.9 (AudioConverter)
**ADR Reference**: ADR-002 §3.2 explicitly requires `asyncio.Lock` for all connection-pooling resources

**Issue**: The canonical code in ADR-002 §3.3 shows `KokoroClient` with `self._init_lock = asyncio.Lock()` and double-checked locking. The SAD §6.6 interface for `KokoroClient` omits this lock entirely:
```python
# SAD §6.6 — MISSING asyncio.Lock
async def _get_client(self) -> httpx.AsyncClient:
    if self._client is None:
        self._client = httpx.AsyncClient(...)
    return self._client
```

Similarly, SAD §6.9 `AudioConverter._get_ffmpeg()` has no lock. Without the lock, two concurrent requests at startup can double-initialize the client (a race condition at the first `await` inside initialization). ADR-002 §3.2 explicitly diagrams this race condition and mandates the lock.

**Proposed Fix**: Update SAD §6.6 `KokoroClient` and §6.9 `AudioConverter` to include `self._init_lock = asyncio.Lock()` and use double-checked locking in `_get_client()` / `_get_ffmpeg()`, consistent with ADR-002 §3.3.

---

### 🟡 WARN — Should fix

---

#### WARN-01: Directory conflict for `synth_engine.py` — `app/processing/` vs `app/synth/`

**SAD Section**: SAD §3 Layer 3 definition vs SAD §10 Directory Structure

**Issue**: The Layer definition in §3 lists:
```
app/processing/synth_engine.py  (FR-04)
```
But the Directory Structure in §10 shows:
```
app/synth/
    └── synth_engine.py
```
And the Dependency Graph in §12.1 references `app/synth/synth_engine.py`. The Module Boundary Map in §4 and the orchestrator import in §6.13 do not specify the path. Three different sections give two different answers. The test directory in §10 also uses `test_synth/` (matching `app/synth/`), suggesting `app/synth/` is the intended location, but §3 text is misleading.

**Proposed Fix**: Update §3 Layer 3 description to read `app/synth/synth_engine.py` for FR-04, and add a comment explaining that `synth_engine.py` is separated because it involves async I/O, while `app/processing/` contains pure-transform modules.

---

#### WARN-02: FR-07 CLI parameter `--file` missing; speed range mismatch

**SAD Section**: SAD §6.12 CLI Tool
**SRS Reference**: FR-07

**Issue**: The SRS FR-07 lists `--file input.txt` (file input mode) and speed range `0.5-2.0`. The SAD CLI definition omits the `--file` flag and specifies `min=0.25, max=4.0` for speed (matching the Pydantic model but contradicting the SRS speed spec). The `SpeechRequest` model also uses `ge=0.25, le=4.0`. These values are internally consistent but diverge from the SRS `0.5-2.0` range without documented justification.

**Proposed Fix**: (a) Add `--file` flag to the CLI definition. (b) Either update the SRS speed range to 0.25–4.0 with rationale (supporting more aggressive slow/fast rates) or constrain the Pydantic model and CLI to 0.5–2.0 as specified. Document the decision.

---

#### WARN-03: NFR-03 Authorization (voice/model access control) not implemented in SAD

**SAD Section**: SAD §8 Security Architecture
**SRS Reference**: NFR-03 "Authorization: 音色/模型存取權限分級"

**Issue**: The SRS explicitly requires authorization tiers for voice/model access. The SAD §8 Security Architecture covers authentication (API key/JWT) and many other controls but has zero mention of authorization logic — there is no role/tier model, no per-key voice allowlist, no middleware checking if a given API key is authorized to use a given voice. The `AuthConfig` Pydantic model has no `allowed_voices` or `tier` fields. The `AuthMiddleware` only validates identity, not permissions.

**Proposed Fix**: Either (a) define an authorization model in §8 (even if simple: all authenticated users have access to all voices initially, with a `TODO: tier enforcement`), or (b) add a clarifying note that authorization tiers are deferred to Phase 4 with a specific SRS deviation note. Leaving it entirely unaddressed is a gap.

---

#### WARN-04: L2 retry for `AudioConverterError` has no backoff timing parameters

**SAD Section**: SAD §7.2 Error Classification Table

**Issue**: The error table states `AudioConverterError` → "Retry 3×", but no backoff interval is specified anywhere in the SAD. For `KokoroClient`, the retry strategy is mentioned (§5.1: "retry up to 3× with exponential backoff") but also lacks explicit parameters (initial delay, multiplier, jitter). This is insufficient for implementation — developers will invent their own values.

**Proposed Fix**: Specify retry parameters in §7 or a dedicated subsection. Suggested: `initial_delay=0.5s, multiplier=2.0, max_delay=5.0s, jitter=True`. At minimum, state whether these are configurable via `config.yaml`.

---

#### WARN-05: `RedisCache` constructor signature inconsistency

**SAD Section**: SAD §6.8 vs SAD §6.13 (Orchestrator), ADR-002 §3.4

**Issue**:
- ADR-002 §3.4 defines: `RedisCache.__init__(self, config: AppConfig)`
- SAD §6.8 defines: `RedisCache.__init__(self, url: str | None, ttl_seconds: int = 86400)`

These are different signatures. The orchestrator in §6.13 injects `redis_cache: RedisCache` but the factory for creating it (`get_orchestrator()` — already missing, see BLOCK-04) would need to know which constructor to use. A developer reading SAD §6.8 would write the wrong constructor.

**Proposed Fix**: Standardize on one signature. The `config: AppConfig` form is preferable as it follows the dependency injection pattern used by `KokoroClient`. Update SAD §6.8 to match ADR-002 §3.4.

---

#### WARN-06: `config.yaml` §11 has fields absent from the Pydantic `AppConfig` model in §6.10

**SAD Section**: SAD §11 (config.yaml) vs SAD §6.10 (config_loader.py)

**Mismatches found**:

| config.yaml field | AppConfig model status |
|-------------------|----------------------|
| `redis.max_connections` | Missing from `RedisConfig` |
| `redis.socket_timeout` | Missing from `RedisConfig` |
| `kokoro.connect_timeout` | Missing from `KokoroConfig` (present in ADR-002 §3.3 code) |
| `kokoro.max_keepalive` | Missing from `KokoroConfig` (present in ADR-002 §3.3 code) |
| `processing.lexicon_path` | Missing from `AppConfig`; `ChunkerConfig` only has `max_chunk_size` |
| `processing.max_input_chars` | Missing from `AppConfig` |
| `synth.*` section | No `SynthConfig` model exists in §6.10 |
| `rate_limit.*` section | No `RateLimitConfig` model exists |
| `observability.*` section | No `ObservabilityConfig` model exists |
| `audio.*` section | No `AudioConfig` model exists |
| `log_level`, `host`, `port` | Missing from `AppConfig` |

This many missing fields means the Pydantic model in §6.10 will silently ignore large portions of the YAML, and developers will be confused about which fields are actually operative.

**Proposed Fix**: Either (a) expand the Pydantic models in §6.10 to cover all config.yaml fields, or (b) explicitly mark §11 config.yaml fields as "reserved for future use / not yet modelled" so developers know what to implement.

---

#### WARN-07: `pydub` crossfade mentioned in SRS FR-04 has no SAD coverage

**SAD Section**: SAD §5.1 Step F (Audio Assembly)
**SRS Reference**: FR-04 "可選：pydub crossfade 消除接縫"

**Issue**: The SRS calls out `pydub crossfade` as optional but the SAD makes no mention of it — not as implemented, not as explicitly deferred, and not as rejected. The SAD shows only `b"".join(audio_parts)` (direct concatenation). This leaves ambiguity for Phase 3: should they add pydub? Is it a known gap?

**Proposed Fix**: Add a note in §5.1 Step F explicitly stating that `pydub` crossfade is out of scope for v6.13 (if that is the decision), with a `TODO` issue reference, or include it in the audio assembly interface definition.

---

#### WARN-08: `health_router` used in `main.py` code sample but never defined in SAD

**SAD Section**: SAD §3, ADR-001 §2 (main.py code sample)

**Issue**: ADR-001 §2 contains:
```python
app.include_router(health_router)  # /health, /ready
```
But `health_router` is never defined or referenced anywhere in the SAD. It is not in `routes.py` (which only shows `/speech` and `/voices`). The `/health` and `/ready` endpoints appear in the system context diagram and the data flow examples, but their implementation is entirely undefined.

**Proposed Fix**: Add a §6.X for `app/api/health.py` defining `health_router` with `/health` returning `HealthResponse` and `/ready` returning `ReadyResponse`. The `ReadyResponse` model is already defined in §6.1 — the route handler is missing.

---

### ℹ️ INFO — Suggestions

---

#### INFO-01: No ADR for `structlog` choice

**SAD Section**: SAD §8.2 ("structlog with PII filters")

`structlog` is chosen over standard `logging` but there is no ADR or inline rationale. This is a minor omission. Suggest a one-paragraph justification (structured JSON logs, async-safe, PII filter hooks) added to §8 or §9.

---

#### INFO-02: Rate limiting module has no interface definition

**SAD Section**: SAD §11 (`rate_limit.*` config), SAD §8.2 ("slowapi / token bucket")

`slowapi` is mentioned as optional in §8.2, and the config.yaml has a `rate_limit` section. However, there is no module defined for rate limiting — no file path, no interface, no layer assignment. This is not critical if rate limiting is managed entirely by middleware configuration, but it should be stated explicitly.

---

#### INFO-03: `SynthesisPartialError` → HTTP 206 may surprise API consumers

**SAD Section**: SAD §7.2

Returning HTTP 206 (Partial Content) for a partially failed synthesis is architecturally unusual. Most REST APIs return 207 (Multi-Status) for mixed results, or a 500 with a partial body flag. Phase 3 developers may have difficulty writing tests for this path, and API consumers may not handle 206 with audio body correctly (browsers and media players may reject it). This is a suggestion to reconsider 206 vs a 200 with a `X-Partial: true` header or a 500 with partial audio in the body.

---

#### INFO-04: `lexicon_tw.json` schema is unspecified

**SAD Section**: SAD §10 directory structure (`app/data/lexicon_tw.json`)

The JSON file format is never defined — is it `{"source": "target"}`, `[{"from": ..., "to": ...}]`, or something with phoneme info? The `LexiconMapper._load()` docstring says "load lexicon from JSON and compile single-pass regex" but gives no schema. A Phase 3 developer building the lexicon file needs to know the format.

**Proposed Fix**: Add 3–5 lines in §6.3 showing the expected JSON schema for `lexicon_tw.json`.

---

#### INFO-05: No observability module defined despite `observability.metrics_enabled` in config

**SAD Section**: SAD §9 NFR-01 mentions `Prometheus tts_ttfb_seconds histogram`, §11 has `observability.metrics_enabled`

The config has `metrics_enabled: true` and §9 references Prometheus metrics, but there is no `app/infrastructure/metrics.py` module, no `/metrics` endpoint, and no `prometheus_fastapi_instrumentator` or `prometheus_client` in the dependency list (§12.3). If Prometheus metrics are required for NFR compliance measurement, this is a gap. If it is deferred, state so explicitly.

---

## Section 3: Conflict Log

| 衝突點 | SRS 建議 | SAD 選擇 | 理由記錄 |
|--------|----------|----------|---------|
| FR-03 Level 2 separator | `。；：` (uses `。` as sub-sentence splitter) | `，；：,;:` (uses `，` comma-level splitting) | ADR-003 提供更好的語言學理由，但未在 SRS 中標注偏差 |
| FR-03 recursion trigger | >100 chars triggers next level | Recursion triggers when piece >250 chars | ADR-003 不使用 100 字中間閾值；此偏差未文件化 |
| FR-07 speed range | `0.5–2.0` | `0.25–4.0` (SAD Pydantic model) | 擴大支援範圍，但未在 ADR 或 SRS 偏差記錄中說明 |
| FR-07 `--file` flag | Required per SRS examples | Not present in SAD CLI definition | 未標注省略原因 |
| NFR-03 Authorization | Voice/model access tiers required | Only authentication (identity) implemented | 未文件化授權模型；可能延期至 Phase 4 |
| FR-04 pydub crossfade | Optional feature in SRS | Not mentioned in SAD | 未明確標記為省略或延期 |

---

## Section 4: 審查結論

**Verdict: ❌ REJECT — Phase 3 cannot start from this SAD as-is**

The SAD is well-structured and demonstrates genuine architectural depth. The ADRs are thorough and the error handling classification is commendable. However, there are **6 BLOCK-level issues** that would cause Phase 3 developers to produce incorrect or non-compiling code:

### Mandatory fixes before re-review:

1. **BLOCK-02**: Remove reverse-layer import (`circuit_breaker` → `kokoro_client`) — structural violation
2. **BLOCK-03**: Reconcile `_on_failure()` signature between SAD §6.7 and ADR-004 §3.1
3. **BLOCK-04**: Define `get_orchestrator()` dependency factory (without this, the application cannot be wired)
4. **BLOCK-05**: Add `circuit_breaker: CircuitBreaker` parameter to `SynthEngine.__init__`
5. **BLOCK-06**: Add `asyncio.Lock` to `KokoroClient` and `AudioConverter` in SAD §6 to match ADR-002
6. **BLOCK-01**: Document FR-03 chunking algorithm deviation from SRS (either update SRS or add explicit deviation note in ADR-003)

### Recommended fixes (should be resolved but not strictly blocking):

- **WARN-01** (directory mismatch for synth_engine.py)
- **WARN-04** (missing retry backoff parameters)
- **WARN-05** (RedisCache constructor inconsistency)
- **WARN-06** (config.yaml fields missing from Pydantic models)
- **WARN-08** (health_router not defined)

### On re-review, if BLOCK issues are resolved, the architecture is fundamentally sound and approval is expected.

The core design decisions — async pipeline, 3-level chunking, lazy init pattern, circuit breaker state machine — are all correct, well-reasoned, and directly implementable. The problems found are primarily **documentation inconsistencies between sections of the same SAD**, not fundamental design flaws.

---

## Section 5: Sign-off

| Field | Value |
|-------|-------|
| **Reviewer** | Agent B — reviewer |
| **Role** | Critical architecture reviewer ("挑刺") |
| **Session ID** | agent:claude:agentb:reviewer:phase2-review |
| **Methodology** | methodology-v2 v6.13 — Phase 2 Architecture Review |
| **Date** | 2026-04-01 |
| **Verdict** | ❌ REJECT — 6 BLOCK issues must be resolved |
| **Re-review required** | Yes — after BLOCK-01 through BLOCK-06 are addressed |

---

*ARCHITECTURE_REVIEW_AGENT_B.md — Agent B reviewer — 2026-04-01*
