# Software Architecture Document (SAD)
## tts-kokoro-v613 — Taiwanese Mandarin TTS Proxy Service

| Field       | Value                                      |
|-------------|--------------------------------------------|
| Version     | 2.0.0                                      |
| Phase       | 2 — Architecture (methodology-v2 v6.13)    |
| Date        | 2026-04-01                                 |
| Author      | Agent A (architect)                        |
| Status      | Approved                                   |
| SRS Ref     | Phase 1 SRS v1.0                           |

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Context Diagram](#2-system-context-diagram)
3. [Architecture Layers](#3-architecture-layers)
4. [Module Boundary Map](#4-module-boundary-map)
5. [Data Flow Diagram](#5-data-flow-diagram)
6. [Module Interface Definitions](#6-module-interface-definitions)
7. [L1-L4 Error Handling Strategy](#7-l1-l4-error-handling-strategy)
8. [Security Architecture](#8-security-architecture)
9. [NFR Implementation Strategy](#9-nfr-implementation-strategy)
10. [Directory Structure](#10-directory-structure)
11. [Configuration Schema](#11-configuration-schema)
12. [Dependency Graph](#12-dependency-graph)
13. [ADR Reference Table](#13-adr-reference-table)

---

## 1. Overview

### 1.1 Purpose

This Software Architecture Document (SAD) defines the structural design of the **tts-kokoro-v613** service: a Taiwanese Mandarin Text-to-Speech proxy that sits between API consumers and a Kokoro Docker TTS backend. The document serves as the authoritative reference for Phase 3 implementation and all downstream development.

### 1.2 Scope

The architecture covers:
- The FastAPI proxy service and all its internal modules
- Integration contracts with the Kokoro Docker backend
- Optional Redis caching layer
- CLI tooling (`tts-v610`)
- All cross-cutting concerns: authentication, error handling, observability

Out of scope: Kokoro Docker internals, infrastructure provisioning, CI/CD pipelines.

### 1.3 Architectural Goals

1. **Directly implementable**: every interface defined here maps 1:1 to a Python module in Phase 3.
2. **FR traceability**: each functional requirement FR-01 through FR-08 is owned by exactly one module.
3. **NFR measurability**: each non-functional requirement has a concrete implementation strategy and a metric.
4. **Resilience by default**: L1–L4 error classification applied uniformly; circuit breaker protects the Kokoro backend.
5. **Zero-surprise startup**: Lazy Init pattern ensures no crash on import when optional dependencies (Redis, ffmpeg) are absent.

### 1.4 Key Constraints

- Python 3.10+, FastAPI, httpx (async), optional Redis
- Kokoro backend is an external Docker service reachable over HTTP
- Audio output is ephemeral — no audio data is persisted beyond the request lifecycle
- All I/O (network, file, subprocess) must use async primitives

---

## 2. System Context Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            EXTERNAL CONSUMERS                                │
│                                                                              │
│   ┌────────────────┐    ┌─────────────────────┐    ┌──────────────────────┐ │
│   │  HTTP Client   │    │   CLI Tool          │    │  Programmatic        │ │
│   │  (curl/app)    │    │   tts-v610          │    │  API Consumer        │ │
│   └───────┬────────┘    └──────────┬──────────┘    └──────────┬───────────┘ │
└───────────┼──────────────────────┼────────────────────────────┼─────────────┘
            │  HTTPS/TLS           │  subprocess/HTTP           │  HTTPS/TLS
            │  API Key / JWT       │  (wraps HTTP calls)        │  API Key / JWT
            ▼                      ▼                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        tts-kokoro-v613 PROXY SERVICE                         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Application  (API Layer)                                     │   │
│  │  Routes: GET /health  GET /ready  GET /v1/proxy/voices               │   │
│  │          POST /v1/proxy/speech                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Orchestration Layer                                                  │   │
│  │  SpeechOrchestrator — coordinates pipeline stages                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│          │              │              │              │                       │
│  ┌───────┴──┐  ┌────────┴──┐  ┌───────┴──┐  ┌───────┴──────┐              │
│  │ SSML     │  │ LEXICON   │  │ CHUNKER  │  │ SYNTH ENGINE │              │
│  │ Parser   │  │ Mapper    │  │          │  │ (Parallel)   │              │
│  └───────┬──┘  └────────┬──┘  └───────┬──┘  └───────┬──────┘              │
│          └──────────────┴──────────────┴──────────────┘                     │
│                              │                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Infrastructure Layer                                                 │   │
│  │  CircuitBreaker  │  RedisCache  │  AudioConverter  │  ConfigLoader    │   │
│  └──────────────────┬────────────────────────────────────────────────────┘  │
└─────────────────────┼────────────────────────────────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
         ▼                         ▼
┌─────────────────┐     ┌─────────────────────┐
│  Kokoro Docker  │     │  Redis (optional)    │
│  TTS Backend    │     │  Cache Store         │
│  :8880/v1/audio │     │  :6379               │
│  /speech        │     │                      │
└─────────────────┘     └─────────────────────┘

External Dependencies:
  - ffmpeg binary (system PATH) — audio format conversion
  - Kokoro Docker container — TTS synthesis engine
  - Redis server (optional) — audio response cache
```

---

## 3. Architecture Layers

The system is organized into 5 strictly ordered layers. Dependencies flow downward only — no layer may import from a layer above it.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  LAYER 1 — API LAYER                                                         ║
║                                                                              ║
║  Module: app/api/routes.py                                                   ║
║  Responsibility:                                                             ║
║    • HTTP request/response lifecycle                                         ║
║    • Authentication (API key / JWT validation)                               ║
║    • Input validation (Pydantic models)                                      ║
║    • L1 error → HTTP 4xx responses                                           ║
║    • No business logic — delegates immediately to Layer 2                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 2 — ORCHESTRATION LAYER                                               ║
║                                                                              ║
║  Module: app/orchestrator/speech_orchestrator.py                             ║
║  Responsibility:                                                             ║
║    • Coordinate the full synthesis pipeline                                  ║
║    • Cache lookup (before pipeline) and cache write (after pipeline)         ║
║    • Assemble chunked audio fragments into final response                    ║
║    • Propagate L2/L3 errors with appropriate recovery                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 3 — PROCESSING LAYER                                                  ║
║                                                                              ║
║  Modules:                                                                    ║
║    • app/processing/ssml_parser.py        (FR-02)                            ║
║    • app/processing/lexicon_mapper.py     (FR-01)                            ║
║    • app/processing/text_chunker.py       (FR-03)                            ║
║    • app/synth/synth_engine.py            (FR-04) ← async I/O, own subdir   ║
║  Responsibility:                                                             ║
║    • Each module owns one FR exclusively                                     ║
║    • Pure transformations where possible (no side effects)                   ║
║    • synth_engine.py in app/synth/ (not app/processing/) because it         ║
║      performs async I/O; pure-transform modules stay in app/processing/      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 4 — BACKEND LAYER                                                     ║
║                                                                              ║
║  Module: app/backend/kokoro_client.py                                        ║
║  Responsibility:                                                             ║
║    • Manage httpx.AsyncClient lifecycle (Lazy Init)                          ║
║    • Single point of contact with Kokoro Docker API                          ║
║    • Retry logic (3 attempts with exponential backoff)                       ║
║    • Emit L4 errors to Circuit Breaker                                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  LAYER 5 — INFRASTRUCTURE LAYER                                              ║
║                                                                              ║
║  Modules:                                                                    ║
║    • app/infrastructure/circuit_breaker.py   (FR-05)                         ║
║    • app/infrastructure/redis_cache.py       (FR-06)                         ║
║    • app/infrastructure/audio_converter.py   (FR-08)                         ║
║    • app/infrastructure/config_loader.py                                     ║
║    • app/infrastructure/auth.py                                              ║
║  Responsibility:                                                             ║
║    • Manage all external service connections (Lazy Init pattern)             ║
║    • Provide resilience primitives (circuit breaker, cache)                  ║
║    • Configuration and secrets management                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

**Layer Dependency Rule**: Layer N may only import from Layer N+1 or lower. Violations are detected by the import linter in CI.

---

## 4. Module Boundary Map

| Module | File Path | FR/NFR Mapping | Single Responsibility | Public Interface (entry point) | Error Level Owned |
|--------|-----------|----------------|----------------------|--------------------------------|-------------------|
| **APIRouter** | `app/api/routes.py` | NFR-04 (availability) | HTTP routing & auth | `router: APIRouter` | L1 (input errors) |
| **SpeechOrchestrator** | `app/orchestrator/speech_orchestrator.py` | All FRs (coordinator) | Pipeline coordination | `async synthesize(req) -> bytes` | L3 (execution errors) |
| **SSMLParser** | `app/processing/ssml_parser.py` | FR-02 | Parse SSML into segments | `parse(text: str) -> list[SSMLSegment]` | L1 (malformed SSML) |
| **LexiconMapper** | `app/processing/lexicon_mapper.py` | FR-01 | Taiwan Mandarin lexicon substitution | `apply(text: str) -> str` | L1 (mapping errors) |
| **TextChunker** | `app/processing/text_chunker.py` | FR-03 | 3-level recursive text chunking | `chunk(text: str) -> list[str]` | L1 (oversized input) |
| **SynthEngine** | `app/synth/synth_engine.py` | FR-04 | Parallel async synthesis of chunks | `async synthesize_chunks(chunks, voice, speed) -> list[bytes]` | L2 (retry on tool errors) |
| **KokoroClient** | `app/backend/kokoro_client.py` | FR-04 (transport) | HTTP calls to Kokoro Docker | `async synthesize(text, voice, speed) -> bytes` | L4 (system errors) |
| **CircuitBreaker** | `app/infrastructure/circuit_breaker.py` | FR-05, NFR-05, NFR-07 | State machine for backend protection | `async call(coro) -> Any` | L4 (open/half-open) |
| **RedisCache** | `app/infrastructure/redis_cache.py` | FR-06 | Optional async cache with TTL | `async get(key) -> bytes \| None`, `async set(key, val)` | L3 (graceful degrade) |
| **AudioConverter** | `app/infrastructure/audio_converter.py` | FR-08 | ffmpeg-based format conversion | `async convert(data: bytes, fmt: str) -> bytes` | L2 (retry ffmpeg) |
| **ConfigLoader** | `app/infrastructure/config_loader.py` | NFR-* (cross-cutting) | Load and validate config.yaml | `get_config() -> AppConfig` | L1 (missing config) |
| **AuthMiddleware** | `app/infrastructure/auth.py` | Security | API key / JWT validation | `async __call__(request, call_next)` | L1 (unauthorized) |
| **CLITool** | `app/cli/main.py` | FR-07 | CLI entry point `tts-v610` | `cli()` via Click/Typer | L1/L2 (user input) |

---

## 5. Data Flow Diagram

### 5.1 Happy Path: POST /v1/proxy/speech

```
CLIENT
  │
  │  POST /v1/proxy/speech
  │  Headers: Authorization: Bearer <token>
  │  Body: { "input": "台灣你好", "voice": "zh-TW-1",
  │           "speed": 1.0, "response_format": "mp3" }
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: AuthMiddleware                                     │
│  1. Extract Bearer token from header                         │
│  2. Validate API key / verify JWT signature                  │
│  3. [L1 FAIL] → 401 Unauthorized (immediate return)         │
│  4. [PASS] → forward to route handler                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: SpeechRequest validation (Pydantic)               │
│  1. Validate field types and constraints                     │
│  2. [L1 FAIL] → 422 Unprocessable Entity                    │
│  3. [PASS] → call orchestrator.synthesize(request)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: SpeechOrchestrator.synthesize()                   │
│                                                              │
│  STEP A — Cache Lookup                                       │
│  ┌────────────────────────────────────────────────────┐     │
│  │ cache_key = sha256(input + voice + speed)          │     │
│  │ cached = await redis_cache.get(cache_key)          │     │
│  │ if cached: → return immediately (TTFB < 50ms)      │     │
│  └───────────────────────────┬────────────────────────┘     │
│                              │ cache miss                    │
│  STEP B — SSML Check                                         │
│  ┌────────────────────────────────────────────────────┐     │
│  │ if request.ssml:                                   │     │
│  │   segments = ssml_parser.parse(input)              │     │
│  │ else:                                              │     │
│  │   segments = [PlainTextSegment(input)]             │     │
│  └───────────────────────────┬────────────────────────┘     │
│                              │                               │
│  STEP C — Lexicon Mapping                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │ for seg in segments:                               │     │
│  │   seg.text = lexicon_mapper.apply(seg.text)        │     │
│  └───────────────────────────┬────────────────────────┘     │
│                              │                               │
│  STEP D — Text Chunking                                      │
│  ┌────────────────────────────────────────────────────┐     │
│  │ chunks = []                                        │     │
│  │ for seg in segments:                               │     │
│  │   chunks.extend(text_chunker.chunk(seg.text))      │     │
│  │ # Each chunk ≤ 250 chars                           │     │
│  └───────────────────────────┬────────────────────────┘     │
│                              │                               │
│  STEP E — Parallel Synthesis                                 │
│  ┌────────────────────────────────────────────────────┐     │
│  │ audio_parts = await synth_engine.synthesize_chunks(│     │
│  │   chunks, voice, speed)                            │     │
│  │ # asyncio.gather() over all chunks concurrently   │     │
│  └───────────────────────────┬────────────────────────┘     │
│                              │                               │
│  STEP F — Audio Assembly                                     │
│  ┌────────────────────────────────────────────────────┐     │
│  │ raw_audio = b"".join(audio_parts)  # direct concat │     │
│  │ if format != "mp3":                                │     │
│  │   raw_audio = await audio_converter.convert(       │     │
│  │     raw_audio, format)                             │     │
│  └───────────────────────────┬────────────────────────┘     │
│                              │                               │
│  STEP G — Cache Write                                        │
│  ┌────────────────────────────────────────────────────┐     │
│  │ await redis_cache.set(cache_key, raw_audio, ttl=   │     │
│  │   86400)  # 24h TTL, fire-and-forget               │     │
│  └───────────────────────────┬────────────────────────┘     │
└──────────────────────────────┼──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4: KokoroClient (called from SynthEngine per chunk)  │
│                                                              │
│  For each chunk (concurrent):                               │
│  1. CircuitBreaker.call(kokoro_client.synthesize(chunk))    │
│  2. [CB OPEN] → L4 error → SynthEngine receives exception   │
│  3. [CB CLOSED] → POST http://kokoro:8880/v1/audio/speech   │
│     Headers: Content-Type: application/json                  │
│     Body: { "model": "kokoro", "input": chunk,              │
│             "voice": voice, "speed": speed,                  │
│             "response_format": "mp3" }                       │
│  4. Response: binary MP3 data (streaming)                    │
│  5. [HTTP error] → retry up to 3× with exponential backoff  │
│  6. [3× fail] → L4 error → circuit breaker records failure  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  RESPONSE ASSEMBLY                                           │
│  1. StreamingResponse(content=raw_audio,                    │
│     media_type="audio/mpeg")                                │
│  2. Headers: X-Cache: HIT|MISS, X-Chunks: N,               │
│     Content-Length: <bytes>                                  │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
                            CLIENT
                     (receives audio bytes)
```

### 5.2 Cache Hit Fast Path

```
CLIENT → AuthMiddleware → Pydantic Validation
       → Orchestrator (cache_key lookup)
       → RedisCache.get() → HIT → StreamingResponse
  (Total TTFB target: < 50ms for cache hits)
```

### 5.3 Circuit Breaker Intervention Path

```
SynthEngine.synthesize_chunks()
  → CircuitBreaker.call(kokoro_client.synthesize(chunk))
  → [CB is OPEN] → raises CircuitBreakerOpenError
  → SynthEngine catches → raises SynthesisUnavailableError (L4)
  → Orchestrator catches → returns 503 Service Unavailable
  → CLIENT receives: {"error": "synthesis_unavailable",
                      "retry_after": <seconds_until_half_open>}
```

---

## 6. Module Interface Definitions

All signatures are concrete Python 3.10+ — no pseudo-code. Type annotations use `from __future__ import annotations` where needed.

### 6.1 Data Models (`app/models/`)

```python
# app/models/speech.py
from enum import Enum
from pydantic import BaseModel, Field, field_validator

class AudioFormat(str, Enum):
    MP3 = "mp3"
    WAV = "wav"

class SpeechRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=10000)
    voice: str = Field(default="zh-TW-1")
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    response_format: AudioFormat = Field(default=AudioFormat.MP3)
    ssml: bool = Field(default=False)

    @field_validator("input")
    @classmethod
    def no_control_chars(cls, v: str) -> str:
        # Strip null bytes and other control chars
        return v.replace("\x00", "").strip()

class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    language: str
    gender: str

class HealthResponse(BaseModel):
    status: str          # "ok" | "degraded" | "unavailable"
    version: str
    circuit_breaker: str # "closed" | "open" | "half_open"
    cache: str           # "connected" | "disabled" | "error"

class ReadyResponse(BaseModel):
    ready: bool
    kokoro_reachable: bool
    uptime_seconds: float
```

### 6.2 SSML Parser (`app/processing/ssml_parser.py`)

```python
# app/processing/ssml_parser.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import xml.etree.ElementTree as ET

class SegmentType(str, Enum):
    TEXT = "text"
    BREAK = "break"
    EMPHASIS = "emphasis"
    PHONEME = "phoneme"

@dataclass
class SSMLSegment:
    type: SegmentType
    text: str
    break_ms: Optional[int] = None          # for <break time="Xms"/>
    emphasis_level: Optional[str] = None    # strong | moderate | reduced
    phoneme_alphabet: Optional[str] = None  # ipa | x-sampa
    phoneme_ph: Optional[str] = None        # phoneme string
    voice_name: Optional[str] = None        # for <voice name="...">
    prosody: dict = field(default_factory=dict)  # rate, pitch, volume

class SSMLParser:
    """FR-02: Parse SSML markup into a flat list of segments.

    Supports: <speak>, <break>, <prosody>, <emphasis>, <voice>, <phoneme>
    """

    def parse(self, text: str) -> list[SSMLSegment]:
        """Parse SSML text into ordered segments.

        Args:
            text: Raw text (with or without SSML tags).
                  If no <speak> root, wraps in <speak> automatically.
        Returns:
            Ordered list of SSMLSegment objects.
        Raises:
            SSMLParseError (L1): Malformed XML that cannot be recovered.
        """
        ...

    def _parse_element(
        self,
        element: ET.Element,
        inherited_prosody: dict
    ) -> list[SSMLSegment]:
        """Recursively parse an XML element and its children."""
        ...

    def _normalize_break(self, time_str: str) -> int:
        """Convert break time string ('500ms', '1s') to milliseconds."""
        ...

class SSMLParseError(ValueError):
    """L1 error: invalid SSML structure."""
    pass
```

### 6.3 Lexicon Mapper (`app/processing/lexicon_mapper.py`)

```python
# app/processing/lexicon_mapper.py
import re
from pathlib import Path
import json

class LexiconMapper:
    """FR-01: Apply Taiwan Mandarin lexicon substitutions.

    Maps Simplified Chinese, PRC-specific terms, and common
    mispronunciation triggers to Taiwan Mandarin equivalents.
    Coverage target: ≥95% of common Taiwan usage patterns.
    """

    def __init__(self, lexicon_path: Path | None = None) -> None:
        """
        Args:
            lexicon_path: Path to lexicon JSON file.
                          Defaults to app/data/lexicon_tw.json.
        """
        self._lexicon_path = lexicon_path or Path(__file__).parent.parent / "data" / "lexicon_tw.json"
        self._mapping: dict[str, str] = {}
        self._pattern: re.Pattern | None = None
        self._load()

    def _load(self) -> None:
        """Load lexicon from JSON and compile single-pass regex."""
        ...

    def apply(self, text: str) -> str:
        """Apply all lexicon substitutions in a single regex pass.

        Args:
            text: Input text after SSML parsing.
        Returns:
            Text with all lexicon substitutions applied.
        Note:
            Longer tokens take precedence (sorted by length descending
            during pattern compilation).
        """
        ...

    def get_coverage_stats(self) -> dict[str, int]:
        """Return stats: total_entries, unique_patterns."""
        ...
```

### 6.4 Text Chunker (`app/processing/text_chunker.py`)

```python
# app/processing/text_chunker.py
import re
from dataclasses import dataclass

MAX_CHUNK_SIZE = 250  # characters

@dataclass
class ChunkResult:
    text: str
    level: int  # 1=sentence, 2=clause, 3=phrase
    index: int

class TextChunker:
    """FR-03: 3-level recursive text chunking.

    Level 1 — Sentence boundaries: 。！？.!?  (plus paragraph breaks)
    Level 2 — Clause boundaries:   ，；：,;:  (commas, semicolons)
    Level 3 — Phrase boundaries:   spaces, 的了吧呢啊 (particles)

    Algorithm: attempt split at Level 1; if any resulting piece still
    exceeds MAX_CHUNK_SIZE, recurse into Level 2 for that piece; if
    still too large, recurse into Level 3; if still too large, hard-
    split at MAX_CHUNK_SIZE boundary (last resort).
    """

    LEVEL1_PATTERN = re.compile(r'(?<=[。！？.!?\n])\s*')
    LEVEL2_PATTERN = re.compile(r'(?<=[，；：,;:])\s*')
    LEVEL3_PATTERN = re.compile(r'(?<=[\s的了吧呢啊])')

    def chunk(self, text: str) -> list[ChunkResult]:
        """Split text into synthesis-ready chunks.

        Args:
            text: Plain text (SSML already stripped).
        Returns:
            Ordered list of ChunkResult, each ≤ MAX_CHUNK_SIZE chars.
        """
        ...

    def _recursive_chunk(
        self,
        text: str,
        level: int,
        base_index: int
    ) -> list[ChunkResult]:
        """Recursively split text using the pattern for `level`."""
        ...

    def _hard_split(self, text: str, level: int, base_index: int) -> list[ChunkResult]:
        """Last-resort: split at MAX_CHUNK_SIZE character boundary."""
        ...
```

### 6.5 Synthesis Engine (`app/synth/synth_engine.py`)

```python
# app/synth/synth_engine.py
import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.backend.kokoro_client import KokoroClient

@dataclass
class SynthesisRequest:
    text: str
    voice: str
    speed: float
    chunk_index: int

@dataclass
class SynthesisResult:
    audio_bytes: bytes
    chunk_index: int
    duration_ms: float

class SynthEngine:
    """FR-04: Parallel async synthesis of text chunks.

    Uses asyncio.gather() to dispatch all chunks concurrently.
    Results are reordered by chunk_index before return.
    """

    def __init__(
        self,
        kokoro_client: "KokoroClient",
        circuit_breaker: "CircuitBreaker",
    ) -> None:
        """Dependency injection: KokoroClient and CircuitBreaker passed at construction.

        Args:
            kokoro_client:   HTTP client for Kokoro backend (Layer 4).
            circuit_breaker: State machine protecting the backend (Layer 5).
                             Each chunk call is wrapped:
                             `await self._circuit_breaker.call(lambda: ...)`
        """
        self._client = kokoro_client
        self._circuit_breaker = circuit_breaker

    async def synthesize_chunks(
        self,
        chunks: list[str],
        voice: str,
        speed: float,
        max_concurrency: int = 10
    ) -> list[bytes]:
        """Synthesize all chunks concurrently, return ordered MP3 parts.

        Args:
            chunks:          Ordered list of text chunks (each ≤ 250 chars).
            voice:           Voice identifier string.
            speed:           Playback speed multiplier.
            max_concurrency: Maximum concurrent Kokoro requests (semaphore).
        Returns:
            List of MP3 byte strings in original chunk order.
        Raises:
            SynthesisPartialError (L3): Some chunks failed; includes
                                        partial results and failed indices.
            SynthesisUnavailableError (L4): Circuit breaker is open.
        """
        ...

    async def _synthesize_one(
        self,
        req: SynthesisRequest,
        semaphore: asyncio.Semaphore
    ) -> SynthesisResult:
        """Synthesize a single chunk with semaphore-based concurrency limit."""
        ...

class SynthesisPartialError(RuntimeError):
    """L3: Partial synthesis failure; some chunks could not be synthesized."""
    def __init__(self, partial_results: list[bytes], failed_indices: list[int]):
        self.partial_results = partial_results
        self.failed_indices = failed_indices

class SynthesisUnavailableError(RuntimeError):
    """L4: Entire synthesis unavailable (circuit breaker open)."""
    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = retry_after_seconds
```

### 6.6 Kokoro Client (`app/backend/kokoro_client.py`)

```python
# app/backend/kokoro_client.py
import httpx
import asyncio
from app.infrastructure.config_loader import AppConfig
from app.models.errors import ClientSideError  # Shared base — no reverse-layer import

class KokoroClient:
    """Backend client for Kokoro Docker TTS API.

    Implements Lazy Init: _client is None until first use.
    Single responsibility: HTTP transport to Kokoro backend.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None  # Lazy Init
        self._init_lock = asyncio.Lock()  # Guards double-initialization race

    async def _get_client(self) -> httpx.AsyncClient:
        """Return (or initialize) the shared AsyncClient.

        Uses double-checked locking (ADR-002 §3.2) to prevent two concurrent
        requests from both finding _client is None and initializing it twice.
        """
        if self._client is None:                       # First check (no lock)
            async with self._init_lock:
                if self._client is None:               # Second check (under lock)
                    self._client = httpx.AsyncClient(
                        base_url=self._config.kokoro.base_url,
                        timeout=httpx.Timeout(
                            connect=5.0,
                            read=self._config.kokoro.read_timeout,
                            write=10.0,
                            pool=5.0
                        ),
                        limits=httpx.Limits(
                            max_connections=self._config.kokoro.max_connections,
                            max_keepalive_connections=10
                        )
                    )
        return self._client

    async def synthesize(self, text: str, voice: str, speed: float) -> bytes:
        """POST to Kokoro /v1/audio/speech and return raw MP3 bytes.

        Args:
            text:  Text chunk to synthesize (≤ 250 chars).
            voice: Voice identifier.
            speed: Speed multiplier.
        Returns:
            Raw MP3 audio bytes.
        Raises:
            KokoroConnectionError (L4): Network-level failure.
            KokoroAPIError (L4):        Non-2xx HTTP response.
            KokoroTimeoutError (L4):    Request exceeded timeout.
        """
        ...

    async def list_voices(self) -> list[dict]:
        """GET /v1/audio/voices from Kokoro backend."""
        ...

    async def health_check(self) -> bool:
        """GET /health from Kokoro backend. Returns True if reachable."""
        ...

    async def close(self) -> None:
        """Close the underlying httpx client. Called on app shutdown."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

class KokoroConnectionError(OSError):
    """L4: Cannot reach Kokoro backend."""
    pass

class KokoroAPIError(RuntimeError):
    """L4: Kokoro returned non-2xx status (base class).

    Use KokoroClientError for 4xx, KokoroServerError for 5xx.
    Separating the two lets CircuitBreaker use isinstance(exc, ClientSideError)
    without importing from this module (see app/models/errors.py).
    """
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

class KokoroClientError(KokoroAPIError, ClientSideError):
    """L4 sub: Kokoro returned 4xx — client error, NOT counted by CircuitBreaker."""
    pass

class KokoroServerError(KokoroAPIError):
    """L4 sub: Kokoro returned 5xx — server error, counted by CircuitBreaker."""
    pass

class KokoroTimeoutError(TimeoutError):
    """L4: Request to Kokoro timed out."""
    pass
```

> **Implementation note**: In `synthesize()`, raise `KokoroClientError` when
> `response.status_code < 500`, and `KokoroServerError` when `>= 500`.
> The `KokoroClientError` mixin of `ClientSideError` lets the circuit breaker
> call `isinstance(exc, ClientSideError)` without importing `KokoroAPIError`.

---

### 6.6a Shared Error Base Classes (`app/models/errors.py`)

```python
# app/models/errors.py
# Shared marker base classes in the models layer.
# Both app/backend/ (Layer 4) and app/infrastructure/ (Layer 5) import from here.
# This prevents reverse-layer imports (Layer 5 → Layer 4).

class ClientSideError(Exception):
    """Marker base class for 4xx client errors.

    CircuitBreaker checks isinstance(exc, ClientSideError) to skip counting
    client-caused failures against the circuit threshold.
    KokoroClientError inherits this; KokoroServerError does not.
    """
    pass
```

### 6.7 Circuit Breaker (`app/infrastructure/circuit_breaker.py`)

```python
# app/infrastructure/circuit_breaker.py
import asyncio
import time
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")

class CircuitState(str, Enum):
    CLOSED    = "closed"      # Normal operation
    OPEN      = "open"        # Blocking all calls
    HALF_OPEN = "half_open"   # Testing recovery

class CircuitBreaker:
    """FR-05: Async circuit breaker protecting the Kokoro backend.

    State machine:
        CLOSED → OPEN:      failure_count >= failure_threshold
        OPEN → HALF_OPEN:   time since open >= recovery_timeout_s
        HALF_OPEN → CLOSED: probe call succeeds
        HALF_OPEN → OPEN:   probe call fails
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_s: float = 10.0,
        name: str = "kokoro"
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout_s = recovery_timeout_s
        self._name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def seconds_until_half_open(self) -> float:
        """Seconds remaining before OPEN transitions to HALF_OPEN."""
        ...

    async def call(
        self,
        coro_factory: Callable[[], Awaitable[T]]
    ) -> T:
        """Execute coroutine through the circuit breaker.

        Args:
            coro_factory: Zero-argument async callable that produces the
                          coroutine to guard (e.g., lambda: client.synthesize(...)).
        Returns:
            Result of the coroutine.
        Raises:
            CircuitBreakerOpenError: When state is OPEN (fast-fail).
            Original exception:     When state is CLOSED/HALF_OPEN and
                                    the coroutine raises.
        """
        ...

    async def _on_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    async def _on_failure(self, exc: Exception) -> None:
        """Record a failure. 4xx client errors (ClientSideError) are skipped.

        Uses isinstance(exc, ClientSideError) from app.models.errors — no
        import from app.backend needed, preventing reverse-layer dependency.
        """
        from app.models.errors import ClientSideError
        if isinstance(exc, ClientSideError):
            return  # Client error — do not count against circuit
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN

    async def _try_half_open_transition(self) -> bool:
        """Return True if OPEN → HALF_OPEN transition should occur."""
        ...

    def get_metrics(self) -> dict[str, Any]:
        """Return current state metrics for /health endpoint."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self._failure_threshold,
            "seconds_until_half_open": self.seconds_until_half_open,
        }

class CircuitBreakerOpenError(RuntimeError):
    """Raised when circuit breaker is in OPEN state."""
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker OPEN; retry after {retry_after:.1f}s")
```

### 6.8 Redis Cache (`app/infrastructure/redis_cache.py`)

```python
# app/infrastructure/redis_cache.py
import hashlib
import json
from typing import Optional

class RedisCache:
    """FR-06: Optional async Redis cache with graceful degradation.

    Lazy Init: _redis is None until first use.
    If Redis is unavailable, all operations become no-ops (L3 degrade).
    Cache key = SHA-256(text + "|" + voice + "|" + str(speed))
    """

    def __init__(self, config: "AppConfig") -> None:
        """
        Args:
            config: Application config. Uses config.redis.url and
                    config.redis.ttl_seconds. If config.redis.url is None,
                    the cache is permanently disabled (graceful no-op mode).

        Follows ADR-002 §3.4: constructor accepts AppConfig, not raw fields,
        consistent with KokoroClient and all other infrastructure classes.
        """
        self._url = config.redis.url
        self._ttl = config.redis.ttl_seconds
        self._redis = None  # Lazy Init
        self._enabled = config.redis.url is not None
        self._available = False  # set True on first successful connect

    async def _get_redis(self):
        """Return (or initialize) the Redis connection."""
        ...

    @staticmethod
    def make_key(text: str, voice: str, speed: float) -> str:
        """Compute deterministic cache key."""
        raw = f"{text}|{voice}|{speed:.4f}"
        return "tts:" + hashlib.sha256(raw.encode()).hexdigest()

    async def get(self, key: str) -> Optional[bytes]:
        """Retrieve cached audio bytes, or None on miss/error/disabled."""
        ...

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        """Store audio bytes. Silently no-ops if Redis unavailable."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a cache entry."""
        ...

    async def ping(self) -> bool:
        """Test Redis connectivity. Returns False if disabled/unreachable."""
        ...

    async def close(self) -> None:
        """Close the Redis connection on shutdown."""
        ...
```

### 6.9 Audio Converter (`app/infrastructure/audio_converter.py`)

```python
# app/infrastructure/audio_converter.py
import asyncio
import shutil
from pathlib import Path

class AudioConverter:
    """FR-08: ffmpeg-based audio format conversion.

    Lazy Init: verifies ffmpeg binary exists on first use.
    Supports: MP3 ↔ WAV (extensible to other formats).
    """

    def __init__(self) -> None:
        self._ffmpeg_path: str | None = None  # Lazy Init
        self._init_lock = asyncio.Lock()      # Guards double-initialization race

    async def _get_ffmpeg(self) -> str:
        """Locate ffmpeg binary (cached after first call).

        Uses double-checked locking (ADR-002 §3.2) consistent with KokoroClient.
        """
        if self._ffmpeg_path is None:                  # First check (no lock)
            async with self._init_lock:
                if self._ffmpeg_path is None:          # Second check (under lock)
                    path = shutil.which("ffmpeg")
                    if path is None:
                        raise AudioConverterError(
                            "ffmpeg not found in PATH. Install ffmpeg to enable format conversion."
                        )
                    self._ffmpeg_path = path
        return self._ffmpeg_path

    async def convert(
        self,
        audio_data: bytes,
        target_format: str,
        source_format: str = "mp3"
    ) -> bytes:
        """Convert audio bytes to target format via ffmpeg subprocess.

        Args:
            audio_data:    Source audio bytes.
            target_format: Target format ("wav", "mp3", "ogg", etc.).
            source_format: Source format hint for ffmpeg.
        Returns:
            Converted audio bytes.
        Raises:
            AudioConverterError (L2): ffmpeg returned non-zero exit code.
            AudioConverterNotFoundError (L2): ffmpeg binary missing.
        """
        ...

    async def _run_ffmpeg(self, args: list[str], stdin: bytes) -> bytes:
        """Run ffmpeg subprocess asynchronously, return stdout bytes."""
        ...

class AudioConverterError(RuntimeError):
    """L2: ffmpeg conversion failed (retryable)."""
    pass

class AudioConverterNotFoundError(AudioConverterError):
    """L2: ffmpeg binary not found."""
    pass
```

### 6.10 Config Loader (`app/infrastructure/config_loader.py`)

```python
# app/infrastructure/config_loader.py
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import yaml
from functools import lru_cache

class KokoroConfig(BaseModel):
    base_url: str = "http://localhost:8880"
    read_timeout: float = 30.0
    max_connections: int = 20

class RedisConfig(BaseModel):
    url: str | None = None
    ttl_seconds: int = 86400

class AuthConfig(BaseModel):
    api_keys: list[str] = Field(default_factory=list)
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"

class ChunkerConfig(BaseModel):
    max_chunk_size: int = 250
    max_concurrency: int = 10

class CircuitBreakerConfig(BaseModel):
    failure_threshold: int = 3
    recovery_timeout_s: float = 10.0
    name: str = "kokoro"  # Identifier used in metrics and log messages

class AppConfig(BaseModel):
    env: str = "production"
    version: str = "6.13.0"
    kokoro: KokoroConfig = Field(default_factory=KokoroConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    chunker: ChunkerConfig = Field(default_factory=ChunkerConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)

@lru_cache(maxsize=1)
def get_config(config_path: str = "config.yaml") -> AppConfig:
    """Load and validate configuration. Cached after first call.

    Raises:
        ConfigError (L1): Missing required fields or invalid values.
    """
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return AppConfig(**data)

class ConfigError(ValueError):
    """L1: Configuration is missing or invalid."""
    pass
```

### 6.11 Auth Middleware (`app/infrastructure/auth.py`)

```python
# app/infrastructure/auth.py
import hmac
import hashlib
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
import jwt  # PyJWT

EXEMPT_PATHS = {"/health", "/ready", "/docs", "/openapi.json"}

class AuthMiddleware(BaseHTTPMiddleware):
    """Security: validate API key or JWT on every non-exempt request."""

    def __init__(self, app, config) -> None:
        super().__init__(app)
        self._config = config

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        credentials = await self._extract_credentials(request)
        if not await self._validate(credentials):
            raise HTTPException(status_code=401, detail="Unauthorized")
        return await call_next(request)

    async def _extract_credentials(self, request: Request) -> str:
        """Extract Bearer token from Authorization header."""
        ...

    async def _validate(self, token: str) -> bool:
        """Validate as API key (constant-time compare) or JWT."""
        ...

    def _validate_api_key(self, token: str) -> bool:
        """Constant-time comparison against configured API keys."""
        return any(
            hmac.compare_digest(token.encode(), key.encode())
            for key in self._config.auth.api_keys
        )

    def _validate_jwt(self, token: str) -> bool:
        """Verify JWT signature and expiry."""
        ...
```

### 6.12 CLI Tool (`app/cli/main.py`)

```python
# app/cli/main.py
import asyncio
import sys
from pathlib import Path
import typer
import httpx

app = typer.Typer(name="tts-v610", help="Taiwanese Mandarin TTS CLI")

@app.command()
def synthesize(
    input: str = typer.Option(..., "--input",  "-i", help="Input text or @file.txt"),
    output: str = typer.Option(..., "--output", "-o", help="Output audio file path"),
    voice:  str = typer.Option("zh-TW-1", "--voice",  "-v"),
    speed:  float = typer.Option(1.0,      "--speed",  "-s", min=0.25, max=4.0),
    format: str = typer.Option("mp3",      "--format", "-f", help="mp3 or wav"),
    ssml:   bool = typer.Option(False,     "--ssml",        help="Parse input as SSML"),
    backend: str = typer.Option("http://localhost:8000", "--backend", "-b"),
    api_key: str = typer.Option("",        "--api-key", envvar="TTS_API_KEY"),
) -> None:
    """FR-07: CLI for tts-v610 TTS synthesis."""
    asyncio.run(_run(input, output, voice, speed, format, ssml, backend, api_key))

async def _run(
    input_arg: str,
    output: str,
    voice: str,
    speed: float,
    format: str,
    ssml: bool,
    backend: str,
    api_key: str
) -> None:
    """Async implementation of the CLI command."""
    ...

def main():
    app()

if __name__ == "__main__":
    main()
```

### 6.13 Speech Orchestrator (`app/orchestrator/speech_orchestrator.py`)

```python
# app/orchestrator/speech_orchestrator.py
from app.models.speech import SpeechRequest
from app.processing.ssml_parser import SSMLParser
from app.processing.lexicon_mapper import LexiconMapper
from app.processing.text_chunker import TextChunker
from app.synth.synth_engine import SynthEngine  # app/synth/, not app/processing/
from app.infrastructure.redis_cache import RedisCache
from app.infrastructure.audio_converter import AudioConverter

class SpeechOrchestrator:
    """Layer 2: Coordinate the full TTS synthesis pipeline.

    All dependencies injected via constructor (Dependency Injection).
    """

    def __init__(
        self,
        ssml_parser: SSMLParser,
        lexicon_mapper: LexiconMapper,
        text_chunker: TextChunker,
        synth_engine: SynthEngine,
        redis_cache: RedisCache,
        audio_converter: AudioConverter,
    ) -> None:
        self._ssml_parser = ssml_parser
        self._lexicon_mapper = lexicon_mapper
        self._text_chunker = text_chunker
        self._synth_engine = synth_engine
        self._redis_cache = redis_cache
        self._audio_converter = audio_converter

    async def synthesize(self, request: SpeechRequest) -> bytes:
        """Execute the full synthesis pipeline.

        Returns:
            Audio bytes in the requested format.
        Raises:
            SynthesisUnavailableError (L4): Circuit breaker is open.
            SynthesisPartialError (L3):     Some chunks failed.
            SSMLParseError (L1):            Malformed SSML input.
        """
        ...

    async def list_voices(self) -> list[dict]:
        """Proxy voice listing from Kokoro backend."""
        ...
```

### 6.14 FastAPI Dependency Factory (`app/api/dependencies.py`)

```python
# app/api/dependencies.py
# Wires all injected dependencies and provides the singleton SpeechOrchestrator
# as a FastAPI Depends() factory. Uses app.state for true singleton lifecycle.

from functools import lru_cache
from fastapi import Request
from app.infrastructure.config_loader import get_config
from app.processing.ssml_parser import SSMLParser
from app.processing.lexicon_mapper import LexiconMapper
from app.processing.text_chunker import TextChunker
from app.synth.synth_engine import SynthEngine
from app.infrastructure.redis_cache import RedisCache
from app.infrastructure.audio_converter import AudioConverter
from app.backend.kokoro_client import KokoroClient
from app.infrastructure.circuit_breaker import CircuitBreaker
from app.orchestrator.speech_orchestrator import SpeechOrchestrator


def create_orchestrator() -> SpeechOrchestrator:
    """Build and wire the full dependency graph.

    Called once at application startup (see app/main.py lifespan).
    All objects are singletons — shared across requests for the lifetime
    of the application process.
    """
    config = get_config()

    # Layer 5: Infrastructure (no app-module imports)
    circuit_breaker = CircuitBreaker(
        failure_threshold=config.circuit_breaker.failure_threshold,
        recovery_timeout_s=config.circuit_breaker.recovery_timeout_s,
        name=config.circuit_breaker.name,
    )
    redis_cache = RedisCache(config=config)
    audio_converter = AudioConverter()

    # Layer 4: Backend client
    kokoro_client = KokoroClient(config=config)

    # Layer 3: Processing pipeline
    ssml_parser = SSMLParser()
    lexicon_mapper = LexiconMapper()
    text_chunker = TextChunker()
    synth_engine = SynthEngine(
        kokoro_client=kokoro_client,
        circuit_breaker=circuit_breaker,
    )

    # Layer 2: Orchestrator
    return SpeechOrchestrator(
        ssml_parser=ssml_parser,
        lexicon_mapper=lexicon_mapper,
        text_chunker=text_chunker,
        synth_engine=synth_engine,
        redis_cache=redis_cache,
        audio_converter=audio_converter,
    )


def get_orchestrator(request: Request) -> SpeechOrchestrator:
    """FastAPI Depends() factory — returns the singleton orchestrator.

    The orchestrator is stored on app.state at startup (see lifespan below).
    Route handlers declare it as:
        orchestrator: SpeechOrchestrator = Depends(get_orchestrator)

    Args:
        request: FastAPI Request (injected by Depends machinery).
    Returns:
        The application-level singleton SpeechOrchestrator.
    """
    return request.app.state.orchestrator
```

```python
# app/main.py (lifespan section)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.dependencies import create_orchestrator

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup: wire dependencies, store singleton on app.state
    app.state.orchestrator = create_orchestrator()
    yield
    # Shutdown: close async resources gracefully
    await app.state.orchestrator._synth_engine._client.close()
    await app.state.orchestrator._redis_cache.close()

app = FastAPI(lifespan=lifespan)
```

> **Why `app.state` instead of `@lru_cache`?**
> `@lru_cache` at module level creates the orchestrator at import time, before the
> FastAPI app exists and before `uvicorn` has set up the event loop. `asyncio.Lock`
> objects (used by Lazy Init and CircuitBreaker) must be created within a running
> event loop. Using `app.state` in the `lifespan` context ensures the event loop
> is running when all objects are instantiated.

### 6.15 Health Router (`app/api/health.py`)

```python
# app/api/health.py
from fastapi import APIRouter, Request
from pydantic import BaseModel

health_router = APIRouter(tags=["health"])

class HealthResponse(BaseModel):
    status: str          # "ok"
    version: str
    circuit_breaker: dict  # CircuitBreaker.get_metrics() output

class ReadyResponse(BaseModel):
    ready: bool
    kokoro_reachable: bool
    redis_available: bool

@health_router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Liveness probe — always returns 200 if the process is alive.

    Exempt from authentication (see AuthMiddleware.EXEMPT_PATHS).
    Includes circuit breaker state for monitoring dashboards.
    """
    orchestrator = request.app.state.orchestrator
    return HealthResponse(
        status="ok",
        version=request.app.state.orchestrator._synth_engine._circuit_breaker._name,
        circuit_breaker=orchestrator._synth_engine._circuit_breaker.get_metrics(),
    )

@health_router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request) -> ReadyResponse:
    """Readiness probe — returns 503 if Kokoro backend is unreachable.

    Used by load balancers to remove the instance from rotation when
    the circuit breaker is open or Kokoro cannot be reached.
    """
    orchestrator = request.app.state.orchestrator
    kokoro_ok = await orchestrator._synth_engine._client.health_check()
    redis_ok = await orchestrator._redis_cache.ping()
    if not kokoro_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content=ReadyResponse(
                ready=False,
                kokoro_reachable=False,
                redis_available=redis_ok,
            ).model_dump(),
        )
    return ReadyResponse(ready=True, kokoro_reachable=True, redis_available=redis_ok)
```

> `health_router` is imported and registered in `app/main.py` alongside `speech_router`:
> ```python
> from app.api.health import health_router
> from app.api.routes import speech_router
> app.include_router(health_router)
> app.include_router(speech_router, prefix="/v1/proxy")
> ```

---

## 7. L1-L4 Error Handling Strategy

### 7.1 Error Level Definitions

| Level | Name | Meaning | Default Handling |
|-------|------|---------|-----------------|
| **L1** | Input Error | Invalid/malformed input from the caller | Return 4xx immediately, no retry |
| **L2** | Tool Error | External tool (ffmpeg, subprocess) failure | Retry up to 3× with backoff |
| **L3** | Execution Error | Partial system failure, graceful degradation possible | Degrade, return partial result or fallback |
| **L4** | System Error | Critical infrastructure failure | Circuit breaker + alert; return 503 |

### 7.2 Error Classification Table

| Error Class | Module | Level | HTTP Status | Retry | Handling Strategy |
|-------------|--------|-------|-------------|-------|-------------------|
| `SSMLParseError` | SSMLParser | L1 | 422 | No | Return error immediately with XML line info |
| `ValidationError` (Pydantic) | API Routes | L1 | 422 | No | FastAPI default handler |
| `HTTPException(401)` | AuthMiddleware | L1 | 401 | No | Reject request, log IP only |
| `HTTPException(403)` | AuthMiddleware | L1 | 403 | No | Reject request |
| `ConfigError` | ConfigLoader | L1 | 500* | No | Fatal at startup; prevent server from starting |
| `AudioConverterError` | AudioConverter | L2 | 500 | 3× | Retry ffmpeg subprocess; L4 after 3 fails |
| `AudioConverterNotFoundError` | AudioConverter | L2 | 500 | No | Return error immediately (config issue) |
| `KokoroConnectionError` | KokoroClient | L4 | 503 | Via CB | Circuit breaker records failure |
| `KokoroAPIError` | KokoroClient | L4 | 502 | Via CB | Circuit breaker records failure |
| `KokoroTimeoutError` | KokoroClient | L4 | 504 | Via CB | Circuit breaker records failure |
| `CircuitBreakerOpenError` | CircuitBreaker | L4 | 503 | No | Return immediately with `Retry-After` header |
| `SynthesisPartialError` | SynthEngine | L3 | 206 | Partial | Return partial audio with warning header |
| `SynthesisUnavailableError` | SynthEngine | L4 | 503 | No | Propagate to API layer |
| `RedisError` (any) | RedisCache | L3 | N/A | No | Silently disable cache; continue without |

### 7.3 Error Response Schema

```python
# All 4xx/5xx responses use this structure
class ErrorResponse(BaseModel):
    error: str          # machine-readable code, e.g. "ssml_parse_error"
    message: str        # human-readable description (no user input echoed)
    level: str          # "L1" | "L2" | "L3" | "L4"
    retry_after: float | None = None  # seconds, for 503 responses
    request_id: str     # UUID for log correlation
```

### 7.4 Global Exception Handler Registration

```python
# app/main.py — registered handlers
@app.exception_handler(SSMLParseError)
async def ssml_error_handler(request, exc): ...      # → 422

@app.exception_handler(SynthesisUnavailableError)
async def unavailable_handler(request, exc): ...     # → 503 + Retry-After

@app.exception_handler(CircuitBreakerOpenError)
async def circuit_open_handler(request, exc): ...    # → 503 + Retry-After

@app.exception_handler(SynthesisPartialError)
async def partial_handler(request, exc): ...         # → 206 + partial audio

@app.exception_handler(Exception)
async def generic_handler(request, exc): ...         # → 500 (sanitized)
```

---

## 8. Security Architecture

### 8.1 Authentication Flow

```
Request arrives
     │
     ▼
Path in EXEMPT_PATHS? ─── YES ──→ bypass auth → handler
     │ NO
     ▼
Extract Authorization header
     │
     ├── Missing header → 401
     │
     ▼
Bearer token present?
     │
     ├── Matches api_keys list (constant-time hmac.compare_digest) → PASS
     │
     ├── Valid JWT (signature + expiry check via PyJWT) → PASS
     │
     └── Neither → 401 Unauthorized
```

### 8.2 Security Controls

| Control | Implementation | Notes |
|---------|---------------|-------|
| **Transport encryption** | HTTPS/TLS via reverse proxy (nginx/caddy) | Service itself runs HTTP internally; TLS terminated at proxy |
| **Authentication** | API key (constant-time compare) OR JWT (HS256/RS256) | Configured in `config.yaml:auth` |
| **Input sanitization** | Pydantic validators strip null bytes; max_length=10000 | No user input is passed to shell commands |
| **No input in logs** | Logging middleware: log request_id, path, status — never body | `structlog` with PII filters |
| **No audio retention** | Audio bytes live only in memory during request; never written to disk | Cache stores bytes in Redis only (encrypted if configured) |
| **SSML injection** | SSML parsed with `xml.etree.ElementTree` (no external entity resolution) | `defusedxml` used to prevent XXE |
| **Rate limiting** | Configurable via middleware (slowapi / token bucket) | Applied per API key |
| **Dependency pinning** | `requirements.txt` with exact versions + `pip-audit` in CI | Prevents supply chain attacks |

### 8.3 Secret Management

- API keys and JWT secrets are loaded from `config.yaml` or environment variables
- Environment variables take precedence over config file values
- Secrets are never logged, never included in error responses
- In production: use Docker secrets or Kubernetes secrets; mount at runtime

### 8.4 Input Validation Layers

```
Layer 1 (HTTP):    Content-Type check, size limit (10MB body max)
Layer 2 (Pydantic): Field type/range validation, custom validators
Layer 3 (SSML):    Strict XML parsing, no external entity resolution
Layer 4 (Lexicon):  Read-only operation on internal data — no injection risk
```

---

## 9. NFR Implementation Strategy

| NFR | Requirement | Implementation Approach | Measurement Method | Target |
|-----|-------------|------------------------|--------------------|--------|
| **NFR-01** | TTFB < 300ms | Redis cache hit path bypasses all processing; async pipeline starts streaming as first chunk arrives | `time.perf_counter()` around first-byte write; Prometheus `tts_ttfb_seconds` histogram | p95 < 300ms |
| **NFR-02** | LEXICON coverage ≥ 80% (target 95%) | LexiconMapper loads ≥ 50 entries; coverage computed as `matched_tokens / total_tokens` on a standard test corpus | `lexicon_mapper.get_coverage_stats()` called in CI test; assert coverage ≥ 80% | ≥ 80% (95% target) |
| **NFR-03** | Tone change accuracy ≥ 95% | Phoneme entries in lexicon explicitly encode tonal variants; test suite uses reference audio golden files | Automated MOS-LQO-style comparison or manual review of N=200 test sentences | ≥ 95% |
| **NFR-04** | API availability ≥ 99% | CircuitBreaker prevents cascade failures; /health and /ready endpoints exempt from auth; health-check-based restart policy in Docker | Uptime monitor (UptimeRobot or Prometheus `up` metric); SLO dashboard | ≥ 99% |
| **NFR-05** | Error recovery < 10s | CircuitBreaker `recovery_timeout_s = 10.0`; half-open probe attempts recovery after exactly 10s | `circuit_breaker.seconds_until_half_open` metric; integration test injects failure and measures recovery | < 10s |
| **NFR-06** | Unit test coverage ≥ 80% | `pytest-cov` enforced in CI; each module has a dedicated test file; coverage gate in `pytest.ini` | `pytest --cov=app --cov-fail-under=80` in CI | ≥ 80% |
| **NFR-07** | Circuit breaker recovery < 10s | Same as NFR-05 — `recovery_timeout_s` default is 10.0; configurable down to 1.0s | Integration test: inject 3 failures, measure time to first successful response after recovery | < 10s |

---

## 10. Directory Structure

```
tts-kokoro-v613/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app factory, lifespan, middleware registration
│   │
│   ├── api/                             # LAYER 1: HTTP routing
│   │   ├── __init__.py
│   │   └── routes.py                    # All route handlers (/health, /ready, /v1/proxy/*)
│   │
│   ├── orchestrator/                    # LAYER 2: Pipeline coordination
│   │   ├── __init__.py
│   │   └── speech_orchestrator.py       # SpeechOrchestrator class
│   │
│   ├── processing/                      # LAYER 3: Text processing pipeline
│   │   ├── __init__.py
│   │   ├── ssml_parser.py               # FR-02: SSML parsing
│   │   ├── lexicon_mapper.py            # FR-01: Taiwan Mandarin lexicon
│   │   └── text_chunker.py              # FR-03: 3-level recursive chunking
│   │
│   ├── synth/                           # LAYER 3 (I/O): Synthesis coordination
│   │   ├── __init__.py
│   │   └── synth_engine.py              # FR-04: Parallel async synthesis
│   │
│   ├── backend/                         # LAYER 4: Kokoro Docker client
│   │   ├── __init__.py
│   │   └── kokoro_client.py             # HTTP client to Kokoro backend
│   │
│   ├── infrastructure/                  # LAYER 5: Cross-cutting infrastructure
│   │   ├── __init__.py
│   │   ├── circuit_breaker.py           # FR-05: Circuit breaker state machine
│   │   ├── redis_cache.py               # FR-06: Optional Redis cache
│   │   ├── audio_converter.py           # FR-08: ffmpeg audio conversion
│   │   ├── config_loader.py             # Configuration loading and validation
│   │   └── auth.py                      # Authentication middleware
│   │
│   ├── models/                          # Shared Pydantic models
│   │   ├── __init__.py
│   │   └── speech.py                    # SpeechRequest, VoiceInfo, HealthResponse, etc.
│   │
│   ├── data/                            # Static data files
│   │   └── lexicon_tw.json              # Taiwan Mandarin lexicon (≥50 entries)
│   │
│   └── cli/                             # FR-07: CLI tool
│       ├── __init__.py
│       └── main.py                      # tts-v610 entry point
│
├── tests/                               # Test suite (mirrors app/ structure)
│   ├── __init__.py
│   ├── conftest.py                      # Shared fixtures, mock KokoroClient
│   ├── test_api/
│   │   └── test_routes.py
│   ├── test_orchestrator/
│   │   └── test_speech_orchestrator.py
│   ├── test_processing/
│   │   ├── test_ssml_parser.py
│   │   ├── test_lexicon_mapper.py
│   │   └── test_text_chunker.py
│   ├── test_synth/
│   │   └── test_synth_engine.py
│   ├── test_backend/
│   │   └── test_kokoro_client.py
│   ├── test_infrastructure/
│   │   ├── test_circuit_breaker.py
│   │   ├── test_redis_cache.py
│   │   └── test_audio_converter.py
│   └── test_cli/
│       └── test_main.py
│
├── 01-requirements/                     # Phase 1: SRS documents
├── 02-architecture/                     # Phase 2: This SAD + ADRs
│   ├── SAD.md
│   ├── ADR-001-fastapi-proxy-layer.md
│   ├── ADR-002-lazy-init-pattern.md
│   ├── ADR-003-three-level-chunking.md
│   └── ADR-004-circuit-breaker-state-machine.md
│
├── config.yaml                          # Runtime configuration (see §11)
├── config.example.yaml                  # Template with all options documented
├── requirements.txt                     # Pinned production dependencies
├── requirements-dev.txt                 # Development/test dependencies
├── pyproject.toml                       # Project metadata, tool configuration
├── pytest.ini                           # Test configuration (coverage gate)
├── Dockerfile                           # Container definition
├── docker-compose.yml                   # Local dev: service + kokoro + redis
└── .env.example                         # Environment variable template
```

---

## 11. Configuration Schema

Complete `config.yaml` with all options and their defaults:

```yaml
# config.yaml — tts-kokoro-v613 Runtime Configuration
# All values can be overridden by environment variables prefixed with TTS_
# e.g., TTS_KOKORO__BASE_URL=http://custom-host:8880

# ── Application ────────────────────────────────────────────────
env: "production"           # production | development | test
version: "6.13.0"
log_level: "INFO"           # DEBUG | INFO | WARNING | ERROR
host: "0.0.0.0"
port: 8000

# ── Kokoro Docker Backend ───────────────────────────────────────
kokoro:
  base_url: "http://localhost:8880"   # Kokoro Docker container URL
  read_timeout: 30.0                  # Seconds to wait for response
  connect_timeout: 5.0                # Seconds to wait for connection
  max_connections: 20                 # Max concurrent HTTP connections
  max_keepalive: 10                   # Max keepalive connections

# ── Redis Cache (optional) ──────────────────────────────────────
redis:
  url: null                           # null = disabled; e.g. "redis://localhost:6379"
  ttl_seconds: 86400                  # 24 hours default TTL
  max_connections: 10
  socket_timeout: 5.0

# ── Authentication ──────────────────────────────────────────────
auth:
  api_keys:                           # List of valid API keys
    - "change-me-in-production"
  jwt_secret: null                    # null = JWT disabled
  jwt_algorithm: "HS256"              # HS256 | RS256
  jwt_expiry_seconds: 3600

# ── Text Processing ─────────────────────────────────────────────
processing:
  lexicon_path: "app/data/lexicon_tw.json"  # Path to lexicon file
  max_input_chars: 10000              # Maximum input text length
  max_chunk_size: 250                 # Maximum chars per synthesis chunk

# ── Synthesis Engine ────────────────────────────────────────────
synth:
  max_concurrency: 10                 # Max parallel Kokoro requests
  default_voice: "zh-TW-1"           # Default voice if not specified
  default_speed: 1.0                  # Default speed multiplier

# ── Circuit Breaker ─────────────────────────────────────────────
circuit_breaker:
  failure_threshold: 3                # Failures before OPEN (FR-05)
  recovery_timeout_s: 10.0           # Seconds before HALF_OPEN (FR-05)
  name: "kokoro"                      # Identifier for metrics

# ── Rate Limiting ───────────────────────────────────────────────
rate_limit:
  enabled: true
  requests_per_minute: 60            # Per API key
  burst: 10                           # Burst allowance

# ── Observability ───────────────────────────────────────────────
observability:
  metrics_enabled: true               # Expose /metrics for Prometheus
  trace_enabled: false                # OpenTelemetry tracing (future)
  request_id_header: "X-Request-ID"

# ── Audio ───────────────────────────────────────────────────────
audio:
  default_format: "mp3"               # mp3 | wav
  ffmpeg_path: null                   # null = auto-detect from PATH
  max_output_bytes: 52428800          # 50MB max output size guard
```

---

## 12. Dependency Graph

### 12.1 Module Dependency Map

```
app/main.py
    ├── app/api/routes.py
    │       ├── app/models/speech.py
    │       ├── app/orchestrator/speech_orchestrator.py
    │       └── app/infrastructure/auth.py
    │
    └── app/orchestrator/speech_orchestrator.py
            ├── app/processing/ssml_parser.py
            │       └── app/models/speech.py (SSMLSegment)
            ├── app/processing/lexicon_mapper.py
            │       └── [app/data/lexicon_tw.json] (data, not import)
            ├── app/processing/text_chunker.py
            │       └── (stdlib only: re, dataclasses)
            ├── app/synth/synth_engine.py
            │       └── app/backend/kokoro_client.py
            │               ├── app/infrastructure/circuit_breaker.py
            │               └── app/infrastructure/config_loader.py
            ├── app/infrastructure/redis_cache.py
            │       └── app/infrastructure/config_loader.py
            └── app/infrastructure/audio_converter.py
                    └── (stdlib only: asyncio, shutil)

app/infrastructure/config_loader.py
    └── (stdlib + pydantic only — NO app imports)

app/cli/main.py
    ├── app/models/speech.py  (shared models)
    └── httpx               (direct HTTP calls to running service)
```

### 12.2 Circular Dependency Analysis

| Potential Cycle | Status | Mitigation |
|-----------------|--------|------------|
| `synth_engine → kokoro_client → circuit_breaker` | No cycle | One-way dependency; CB has no knowledge of client |
| `circuit_breaker → kokoro_client` | **RESOLVED** | Old pattern used `from app.backend.kokoro_client import KokoroAPIError` — reverse-layer violation. Fixed: `ClientSideError` base class in `app/models/errors.py` (shared layer). `KokoroClientError` inherits it; CB checks `isinstance(exc, ClientSideError)`. |
| `orchestrator → synth_engine → orchestrator` | **PROHIBITED** | SynthEngine must not import from orchestrator |
| `routes → orchestrator → routes` | **PROHIBITED** | Orchestrator must not import from API layer |
| `config_loader → any app module` | **PROHIBITED** | ConfigLoader has zero app-module imports |

**Enforcement**: A `tests/test_imports/test_no_circular.py` test uses `importlib` to verify no circular imports exist at module load time.

### 12.3 External Dependency Versions

```
fastapi>=0.111.0,<0.112
uvicorn[standard]>=0.29.0,<0.30
httpx>=0.27.0,<0.28
pydantic>=2.7.0,<3.0
pydantic-settings>=2.2.0,<3.0
redis>=5.0.3,<6.0          # optional
defusedxml>=0.7.1
PyJWT>=2.8.0,<3.0
typer>=0.12.0,<0.13
pyyaml>=6.0.1
structlog>=24.1.0
```

---

## 13. ADR Reference Table

| ADR ID | Title | Decision | Status | Date |
|--------|-------|----------|--------|------|
| ADR-001 | FastAPI as Proxy Framework | Use FastAPI with uvicorn for async HTTP service | Accepted | 2026-04-01 |
| ADR-002 | Lazy Init Pattern for External Dependencies | All `_client`/`_conn` attributes start as `None`, initialized on first use | Accepted | 2026-04-01 |
| ADR-003 | Three-Level Recursive Text Chunking | Sentence → Clause → Phrase recursive split, max 250 chars | Accepted | 2026-04-01 |
| ADR-004 | Circuit Breaker State Machine | Closed/Open/Half-Open with fail≥3→Open, 10s→Half-Open | Accepted | 2026-04-01 |

---

*End of Software Architecture Document*
*Next phase: Phase 3 — Implementation*
