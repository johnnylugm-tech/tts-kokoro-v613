# SAD.md — Software Architecture Document

> **版本**: v1.0.0  
> **專案**: tts-kokoro-v613  
> **日期**: 2026-04-01  
> **Phase**: 2 (架構設計)  
> **Author**: Johnny1027_bot (architect agent)

---

## 1.  Overview

### 1.1 Purpose
本文件描述 tts-kokoro-v613 專案的軟體架構，基於 SRS.md 需求規格進行架構設計。

### 1.2 Scope
Phase 2 涵蓋代理層架構、模組設計、接口定義、錯誤處理和安全性設計。

### 1.3 Technology Stack
- **後端**: Kokoro Docker (`http://localhost:8880`)
- **代理層**: FastAPI + httpx + Python 3.10+
- **可選快取**: Redis
- **CLI 工具**: ffmpeg
- **非同步**: httpx.AsyncClient

---

## 2. Module Design

### 2.1 Module Boundary Map

| Module | Responsibility | Public API | FR Mapping |
|--------|---------------|------------|------------|
| `engines/taiwan_linguistic.py` | 台灣中文詞彙映射、變調處理 | `process(text) -> ProcessedText` | FR-01 |
| `engines/ssml_parser.py` | SSML 標籤解析與驗證 | `parse(ssml_string) -> SSMLTree` | FR-02 |
| `engines/text_splitter.py` | 長文本智能切分 | `split(text, max_length) -> List[Chunk]` | FR-03 |
| `engines/synthesis.py` | Kokoro TTS 引擎調用 | `synthesize(text, voice, **opts) -> AudioBytes` | FR-04 |
| `middleware/circuit_breaker.py` | 斷路器保護模式 | `call(func, *args, **kwargs) -> Result` | FR-05 |
| `cache/redis_cache.py` | Redis 快取管理 | `get(key)`, `set(key, value, ttl)` | FR-06 |
| `cli.py` | CLI 命令列工具 | `main()` | FR-07 |
| `audio_converter.py` | 音訊格式轉換 | `convert(audio, from_fmt, to_fmt) -> bytes` | FR-08 |

### 2.2 Module Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Clients                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Router Layer                         │
│            (health.py, tts.py, /v1/proxy/*)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│     CLI         │  │  text_splitter  │  │   ssml_parser   │
│  (cli.py)      │  │  (FR-03)        │  │   (FR-02)       │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                     │                    │
         │                     └──────────┬────────┘
         │                              ▼
         │                   ┌─────────────────────┐
         │                   │ taiwan_linguistic.py │
         │                   │ (FR-01)              │
         │                   └──────────┬───────────┘
         │                              │
         │                              ▼
         │                   ┌─────────────────────┐
         │                   │   redis_cache.py     │
         │                   │   (FR-06)            │
         │                   └──────────┬───────────┘
         │                              │
         │                              ▼
         │                   ┌─────────────────────┐
         │                   │ circuit_breaker.py   │
         │                   │ (FR-05)              │
         │                   └──────────┬───────────┘
         │                              │
         │                              ▼
         │                   ┌─────────────────────┐
         │                   │   synthesis.py      │
         │                   │   (FR-04)           │
         │                   └──────────┬───────────┘
         │                              │
         │                              ▼
         │                   ┌─────────────────────┐
         │                   │ audio_converter.py  │
         │                   │ (FR-08)             │
         │                   └─────────────────────┘
         │
         ▼
┌─────────────────┐
│   Kokoro Docker │
│ (External)      │
└─────────────────┘
```

### 2.3 Dependency Matrix

| Consumer | Provider | Dependency Type | FR Mapping |
|----------|----------|----------------|------------|
| `router/tts.py` | `text_splitter.py` | Functional dependency | FR-03 |
| `router/tts.py` | `ssml_parser.py` | Functional dependency | FR-02 |
| `router/tts.py` | `taiwan_linguistic.py` | Functional dependency | FR-01 |
| `taiwan_linguistic.py` | `ssml_parser.py` | Functional dependency | FR-02 |
| `redis_cache.py` | `circuit_breaker.py` | Resilience dependency | FR-05 |
| `circuit_breaker.py` | `synthesis.py` | Resilient call dependency | FR-04 |
| `synthesis.py` | `Kokoro Docker` | External API dependency | FR-04 |
| `cli.py` | `text_splitter.py` | Functional dependency | FR-03 |
| `cli.py` | `taiwan_linguistic.py` | Functional dependency | FR-01 |
| `cli.py` | `synthesis.py` | Functional dependency | FR-04 |
| `cli.py` | `audio_converter.py` | Functional dependency | FR-08 |

---

## 3. Interface Definitions

### 3.1 FastAPI Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | 健康檢查 |
| GET | `/ready` | 就緒檢查（含 Kokoro/Redis 狀態） |
| GET | `/v1/proxy/voices` | 音色列表 |
| POST | `/v1/proxy/speech` | 語音合成 |

### 3.2 Internal Module Interfaces

#### taiwan_linguistic.py
```python
class TaiwanLinguisticEngine:
    def process(self, text: str) -> ProcessedText:
        """應用台灣中文變調規則和詞彙映射"""
```

#### ssml_parser.py
```python
class SSMLParser:
    def parse(self, ssml_string: str) -> SSMLTree:
        """解析 SSML 為語法樹"""
    def validate(self, tree: SSMLTree) -> ValidationResult:
        """驗證 SSML 結構"""
```

#### text_splitter.py
```python
class TextSplitter:
    def split(self, text: str, max_length: int = 250) -> List[Chunk]:
        """三級遞迴切分，確保每段 ≤ max_length 字"""
```

#### synthesis.py
```python
class KokoroSynthesis:
    def __init__(self, base_url: str = "http://localhost:8880")
    def synthesize(self, text: str, voice: str, **opts) -> bytes:
        """呼叫 Kokoro Docker TTS API"""
```

#### circuit_breaker.py
```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 10.0)
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """執行帶斷路器保護的調用"""
```

#### redis_cache.py
```python
class RedisCache:
    def __init__(self, url: str = "redis://localhost:6379")
    async def get(self, key: str) -> Optional[bytes]
    async def set(self, key: str, value: bytes, ttl: int = 86400) -> bool
```

---

## 4. Data Flow

```
[Client Input: Text/SSML]
         │
         ▼
┌─────────────────────────────────┐
│  FastAPI /v1/proxy/speech       │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  text_splitter.py               │◄── FR-03: 智能文本切分
│  (max 250 chars per chunk)      │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  taiwan_linguistic.py           │◄── FR-01: 詞彙映射
│  (LEXICON ≥50, tone sandhi)    │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  ssml_parser.py                 │◄── FR-02: SSML 解析
│  (break/prosody/voice tags)     │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  redis_cache.py                 │◄── FR-06: Redis 快取
│  (TTL=24h, key=hash)           │
└─────────────┬───────────────────┘
              │
     [Cache Hit]──────────┐
         │               │
         ▼               ▼
┌─────────────────┐  ┌────────────────────┐
│  Return Cache   │  │ circuit_breaker.py │
└─────────────────┘  │ (FR-05)             │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌────────────────────┐
                     │ synthesis.py       │
                     │ (Kokoro Docker)    │
                     └──────────┬─────────┘
                                │
                                ▼
                     ┌────────────────────┐
                     │ audio_converter.py │
                     │ (FR-08: ffmpeg)   │
                     └────────────────────┘
```

---

## 5. Security Architecture

### 5.1 Four Security Design Aspects

| Aspect | Implementation | Status |
|--------|---------------|--------|
| **Authentication** | API key via `X-API-Key` header; JWT token support | ✅ |
| **Authorization** | Voice/model ACL; Rate limiting (100 req/min default) | ✅ |
| **Encryption** | HTTPS/TLS for external; HTTP for localhost Kokoro | ✅ |
| **Data Protection** | No user input logged; Audio not persisted; Redis TTL auto-expiry | ✅ |

### 5.2 Security Configuration

```yaml
security:
  api_key_enabled: true
  rate_limit:
    enabled: true
    requests_per_minute: 100
  tls:
    enabled: true
  data_protection:
    log_user_input: false
    persist_audio: false
    redis_ttl: 86400
```

### 5.3 Threat Model

| Threat | Mitigation |
|--------|------------|
| Unauthorized API access | API key authentication |
| Voice/Model abuse | Authorization ACL |
| Man-in-the-middle | TLS encryption |
| Data leakage | No audio persistence |
| DoS attack | Rate limiting |
| Backend overload | Circuit breaker |

---

## 6. Error Handling

### 6.1 Error Level Classification (L1-L4)

| Level | Type | Description | Action |
|-------|------|-------------|--------|
| **L1** | Input Error | Invalid text format, SSML syntax error | Return 400 immediately |
| **L2** | Tool Error | Kokoro/Redis connection timeout | Retry 3 times, then return 503 |
| **L3** | Execution Error | Upstream API failure, decode error | Circuit breaker increments, degrade gracefully |
| **L4** | System Error | Backend崩潰, memory exhausted | Circuit breaker OPEN after 3 failures, 10s recovery, alert, return 503 |

### 6.2 Error Response Mapping

| Error Type | HTTP Code | Response |
|------------|-----------|----------|
| Kokoro unavailable | 503 | `{"error": "TTS service temporarily unavailable"}` |
| Invalid SSML | 400 | `{"error": "SSML validation failed", "details": [...]}` |
| Voice not found | 404 | `{"error": "Voice not found"}` |
| Text too long | 413 | `{"error": "Text exceeds maximum length"}` |
| Redis unavailable | 200 | Degrade gracefully (skip cache) |

### 6.3 Circuit Breaker Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| failure_threshold | 3 | Open after 3 consecutive failures |
| recovery_timeout | 10.0s | Time before Half-Open |
| expected_exception | Exception | Base exception type |

---

## 7. Configuration

```yaml
kokoro:
  base_url: "http://localhost:8880"
  timeout: 30.0

redis:
  url: "redis://localhost:6379"
  default_ttl: 86400
  key_prefix: "tts:v1:"

circuit_breaker:
  failure_threshold: 3
  recovery_timeout: 10.0

app:
  host: "0.0.0.0"
  port: 8000
  workers: 4
```

---

## 8. Directory Structure

```
tts-kokoro-v613/
├── 01-requirements/          # Phase 1
├── 02-architecture/          # Phase 2 (this)
│   ├── SAD.md                # This document
│   └── adr/                  # Architecture Decision Records
│       ├── 001-fastapi-proxy-layer.md
│       ├── 002-redis-caching-strategy.md
│       └── 003-circuit-breaker-resilience.md
├── 03-implementation/         # Phase 3 (future)
├── 04-testing/                # Phase 4 (future)
├── 00-summary/                # STAGE_PASS files
├── engines/                   # Source code (Phase 3)
├── middleware/                 # Source code (Phase 3)
├── cache/                      # Source code (Phase 3)
├── cli.py                      # CLI tool
├── audio_converter.py          # Audio converter
├── DEVELOPMENT_LOG.md
└── sessions_spawn.log
```

---

## 9. ADR (Architecture Decision Records)

See `adr/` directory for detailed ADRs:

| ADR | Title | Status |
|-----|-------|--------|
| 001 | FastAPI + httpx Proxy Layer | Accepted |
| 002 | Redis Caching Strategy | Accepted |
| 003 | Circuit Breaker Resilience Pattern | Accepted |

---

## 10. Acceptance Criteria

- [ ] All 4 API endpoints implemented
- [ ] taiwan_linguistic.py handles tone sandhi rules
- [ ] text_splitter.py correctly segments Chinese text (≤250 chars)
- [ ] ssml_parser.py validates SSML 1.0 subset
- [ ] circuit_breaker opens after 3 consecutive failures, 10s recovery
- [ ] Redis cache reduces Kokoro calls for repeated text
- [ ] CLI can synthesize audio from command line
- [ ] audio_converter.py converts between mp3/wav via ffmpeg
- [ ] Health endpoints return proper status
- [ ] Unit tests achieve ≥80% coverage

---

## 11. Conflict Log

| Date | Decision | Reason | Notes |
|------|----------|--------|-------|
| 2026-04-01 | Use FastAPI over Flask | Async-native, OpenAPI auto-generation | |
| 2026-04-01 | Circuit breaker threshold=3 | SRS FR-05 要求 | |
| 2026-04-01 | Redis TTL=24h | Balance cache size vs freshness | |

---

*本文件依據 SKILL.md Phase 2 規範生成*
