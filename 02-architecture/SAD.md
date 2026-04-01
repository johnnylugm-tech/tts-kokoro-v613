# SAD — 軟體架構文件
## tts-kokoro-v613 — 台灣中文 TTS 代理服務

| 欄位 | 內容 |
|------|------|
| 版本 | 2.0.0（合併版） |
| Phase | Phase 2 — 架構設計（methodology-v2 v6.13） |
| 日期 | 2026-04-01 |
| 作者 | Agent A（架構師）＋ Johnny（需求方） |
| 狀態 | Approved |
| 參考 | SRS.md v6.13.1 |

---

## 目錄

1. [概覽](#1-概覽)
2. [系統上下文圖](#2-系統上下文圖)
3. [架構層](#3-架構層)
4. [模組邊界對應表](#4-模組邊界對應表)
5. [資料流圖](#5-資料流圖)
6. [模組介面定義](#6-模組介面定義)
7. [L1–L4 錯誤處理策略](#7-l1l4-錯誤處理策略)
8. [安全性架構](#8-安全性架構)
9. [NFR 實作策略](#9-nfr-實作策略)
10. [目錄結構](#10-目錄結構)
11. [設定檔結構](#11-設定檔結構)
12. [依賴關係圖](#12-依賴關係圖)
13. [ADR 參考表](#13-adr-參考表)

---

## 1. 概覽

### 1.1 系統目的

**tts-kokoro-v613** 是一個台灣中文最佳化語音合成（TTS）代理服務，基於 Kokoro-82M 模型，透過 FastAPI 代理層將後端 Kokoro Docker 服務轉化為具備台灣在地化能力的專業 TTS 系統。

### 1.2 系統範圍

本架構涵蓋：FastAPI 代理服務及所有內部模組、Kokoro Docker 後端的整合合約、選配的 Redis 快取層、CLI 工具（`tts-v610`）、所有橫切關注點（認證、錯誤處理、可觀測性）。

不在範圍內：Kokoro Docker 內部實作、基礎設施配置、CI/CD 管線。

### 1.3 FR 需求對應（FR-01 ~ FR-09）

| FR ID | 需求 | 負責模組 |
|-------|------|---------|
| **FR-01** | TaiwanLexicon ≥ 50 詞映射（台灣中文詞彙替換） | `app/processing/lexicon_mapper.py` |
| **FR-02** | SSMLParser 解析 SSML 標籤（`<voice>`、`<break>`、`<prosody>`） | `app/processing/ssml_parser.py` |
| **FR-03** | TextSplitter 三級遞迴切分（≤ 250 字） | `app/processing/text_chunker.py` |
| **FR-04** | AsyncEngine 併發處理（httpx.AsyncClient + MP3 串接） | `app/synth/synth_engine.py` |
| **FR-05** | CircuitBreaker 熔斷機制（失敗 ≥ 3 → Open，10 秒後 Half-Open） | `app/infrastructure/circuit_breaker.py` |
| **FR-06** | RedisCache 可選快取（SHA-256 key，TTL=24h，優雅降級） | `app/infrastructure/redis_cache.py` |
| **FR-07** | FastAPI + Typer CLI（HTTP API + 命令列工具） | `app/api/routes.py` + `app/cli/main.py` |
| **FR-08** | AudioConverter（ffmpeg MP3 ↔ WAV 互轉） | `app/infrastructure/audio_converter.py` |
| **FR-09** | Kokoro Proxy（整合外部 TTS API，代理轉發） | `app/backend/kokoro_client.py` |

### 1.4 架構目標

1. **可直接實作**：每個介面定義都對應 Phase 3 中的一個 Python 模組。
2. **FR 可追溯**：每個功能需求 FR-01 至 FR-09 由一個模組完全擁有。
3. **NFR 可測量**：每個非功能需求都有具體實作策略與指標。
4. **預設韌性**：L1–L4 錯誤分類統一套用；斷路器保護 Kokoro 後端。
5. **零意外啟動**：Lazy Init 模式確保選配依賴（Redis、ffmpeg）缺席時不會當機。

### 1.5 關鍵約束

- Python 3.10+、FastAPI、httpx（非同步）、選配 Redis
- Kokoro 後端為可透過 HTTP 到達的外部 Docker 服務
- 音訊輸出為暫態 — 不在請求生命週期外保留音訊資料
- 所有 I/O（網路、檔案、子程序）必須使用非同步原語

---

## 2. 系統上下文圖

```
外部消費者
  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │ HTTP Client  │    │ CLI tts-v610 │    │ 程式化消費者  │
  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
         │ HTTPS/TLS          │ subprocess       │ HTTPS/TLS
         ▼                    ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│              tts-kokoro-v613 代理服務                   │
│  ┌─────────────────────────────────────────────────┐  │
│  │ FastAPI（API Layer）                             │  │
│  │ /health /ready /v1/proxy/voices /v1/proxy/speech │  │
│  └────────────────────────┬────────────────────────┘  │
│  ┌────────────────────────▼────────────────────────┐  │
│  │ SpeechOrchestrator（協調層）                     │  │
│  └────────────────────────┬────────────────────────┘  │
│     │         │         │         │                   │
│  ┌──┴──┐ ┌───┴───┐ ┌───┴───┐ ┌────┴────┐            │
│  │SSML │ │LEXICON│ │CHUNKER│ │SYNTH    │            │
│  │F02  │ │ FR-01 │ │ FR-03 │ │ FR-04   │            │
│  └──┬──┘ └───┬───┘ └───┬───┘ └────┬────┘            │
│     └────────┴─────────┴──────────┘                   │
│  ┌─────────────────────────────────────────────────┐  │
│  │ Infrastructure: CircuitBreaker│RedisCache│     │  │
│  │ AudioConverter│ConfigLoader│Auth (FR-05~08)     │  │
│  └────────────────────┬────────────────────────────┘  │
└────────────────────────┼────────────────────────────────┘
         ┌───────────────┴───────────────┐
         ▼                                 ▼
┌─────────────────┐               ┌─────────────────┐
│ Kokoro Docker   │               │ Redis（選配）    │
│ :8880/v1/audio  │               │ :6379           │
└─────────────────┘               └─────────────────┘
```

---

## 3. 架構層

系統依嚴格順序組織為 5 層。依賴只能向下流動 — 不得有層級反向引用。

```
╔══════════════════════════════════════════════════════════════════════╗
║  LAYER 1 — API LAYER                                                 ║
║  app/api/routes.py                                                   ║
║  HTTP 請求/回應生命週期、認證、輸入驗證、L1 錯誤 → HTTP 4xx           ║
╠══════════════════════════════════════════════════════════════════════╣
║  LAYER 2 — ORCHESTRATION LAYER                                       ║
║  app/orchestrator/speech_orchestrator.py                             ║
║  協調完整合成管線、快取查詢/寫入、音訊組裝、L2/L3 錯誤傳播           ║
╠══════════════════════════════════════════════════════════════════════╣
║  LAYER 3 — PROCESSING LAYER                                          ║
║  • app/processing/ssml_parser.py        （FR-02）                    ║
║  • app/processing/lexicon_mapper.py     （FR-01）                    ║
║  • app/processing/text_chunker.py       （FR-03）                    ║
║  • app/synth/synth_engine.py           （FR-04）— async I/O 子目錄  ║
╠══════════════════════════════════════════════════════════════════════╣
║  LAYER 4 — BACKEND LAYER                                             ║
║  app/backend/kokoro_client.py（FR-09: Kokoro Proxy）                 ║
║  httpx.AsyncClient 生命週期（Lazy Init）、單一後端聯絡點、            ║
║  重試邏輯（3 次指數退避）、向 Circuit Breaker 發出 L4 錯誤           ║
╠══════════════════════════════════════════════════════════════════════╣
║  LAYER 5 — INFRASTRUCTURE LAYER                                      ║
║  • app/infrastructure/circuit_breaker.py   （FR-05）                ║
║  • app/infrastructure/redis_cache.py       （FR-06）                ║
║  • app/infrastructure/audio_converter.py   （FR-08）                ║
║  • app/infrastructure/config_loader.py                                      ║
║  • app/infrastructure/auth.py                                                ║
╚══════════════════════════════════════════════════════════════════════╝
```

**Layer Dependency Rule**：Layer N 只能引用 Layer N+1 或更低層級。違反會在 CI 中被 import linter 偵測。

---

## 4. 模組邊界對應表

| 模組 | 檔案路徑 | FR/NFR 對應 | 擁有錯誤等級 |
|------|---------|------------|------------|
| **APIRouter** | `app/api/routes.py` | NFR-04 | L1 |
| **SpeechOrchestrator** | `app/orchestrator/speech_orchestrator.py` | 全部 FRs | L3 |
| **SSMLParser** | `app/processing/ssml_parser.py` | FR-02 | L1 |
| **LexiconMapper** | `app/processing/lexicon_mapper.py` | FR-01 | L1 |
| **TextChunker** | `app/processing/text_chunker.py` | FR-03 | L1 |
| **SynthEngine** | `app/synth/synth_engine.py` | FR-04 | L2 |
| **KokoroClient** | `app/backend/kokoro_client.py` | FR-09 | L4 |
| **CircuitBreaker** | `app/infrastructure/circuit_breaker.py` | FR-05, NFR-05, NFR-07 | L4 |
| **RedisCache** | `app/infrastructure/redis_cache.py` | FR-06 | L3 |
| **AudioConverter** | `app/infrastructure/audio_converter.py` | FR-08 | L2 |
| **ConfigLoader** | `app/infrastructure/config_loader.py` | NFR-* | L1 |
| **AuthMiddleware** | `app/infrastructure/auth.py` | 安全性 | L1 |
| **CLITool** | `app/cli/main.py` | FR-07 | L1/L2 |

---

## 5. 資料流圖

### 5.1 標準合成流程（POST /v1/proxy/speech）

```
CLIENT → POST /v1/proxy/speech { input, voice, speed, response_format }
       │
       ▼
┌─────────────────────────────────────────────────────┐
│ LAYER 1: Auth + Pydantic 驗證                       │
│   L1 FAIL → 401/422 即時回傳                        │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ LAYER 2: SpeechOrchestrator.synthesize()           │
│                                                     │
│ A. 快取查詢（FR-06）→ HIT → TTFB < 50ms            │
│                                                     │
│ B. SSML 解析（FR-02）                               │
│   if ssml: segments = ssml_parser.parse(input)     │
│                                                     │
│ C. 詞彙映射（FR-01: TaiwanLexicon ≥50 詞）         │
│   for seg: seg.text = lexicon_mapper.apply(...)     │
│                                                     │
│ D. 文本切分（FR-03: 三級遞迴 ≤ 250 字）            │
│   for seg: chunks.extend(text_chunker.chunk(...))  │
│                                                     │
│ E. 並行合成（FR-04: AsyncEngine）                   │
│   audio_parts = await synth_engine.synthesize_chunks│
│                                                     │
│ F. 音訊組裝（FR-08: ffmpeg 可選）                  │
│   raw = b"".join(audio_parts)                      │
│   if format != "mp3": raw = convert(raw, format)   │
│                                                     │
│ G. 快取寫入（FR-06: TTL=24h）                      │
│   redis_cache.set(cache_key, raw, ttl=86400)         │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│ LAYER 4: KokoroClient（FR-09: Kokoro Proxy）       │
│ 對每個分塊並行（FR-04）：                           │
│  1. CircuitBreaker.call(kokoro_client.synthesize)  │
│  2. [CB OPEN] → CircuitBreakerOpenError (L4)       │
│  3. [CB CLOSED] → POST http://kokoro:8880/...      │
│  4. [HTTP 錯誤] → 指數退避重試 3 次               │
│  5. [3 次失敗] → L4 錯誤 → 斷路器記錄             │
└────────────────────┬────────────────────────────────┘
                     ▼
CLIENT ← StreamingResponse(raw_audio, audio/mpeg)
        X-Cache: HIT|MISS, X-Chunks: N
```

### 5.2 快取命中快速路徑

```
CLIENT → Auth → Pydantic → Orchestrator → RedisCache.get() → HIT
       （TTFB 目標 < 50ms）
```

### 5.3 斷路器介入路徑

```
SynthEngine → CircuitBreaker.call(kokoro_client.synthesize)
  → [CB OPEN] → CircuitBreakerOpenError
  → SynthesisUnavailableError (L4)
  → Orchestrator 捕獲 → 503 + retry_after
```

---

## 6. 模組介面定義

### 6.1 資料模型（`app/models/speech.py`）

```python
from enum import Enum
from pydantic import BaseModel, Field, field_validator

class AudioFormat(str, Enum):
    MP3 = "mp3"; WAV = "wav"

class SpeechRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=10000)
    voice: str = Field(default="zh-TW-1")
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    response_format: AudioFormat = Field(default=AudioFormat.MP3)
    ssml: bool = Field(default=False)

    @field_validator("input")
    @classmethod
    def no_control_chars(cls, v: str) -> str:
        return v.replace("\x00", "").strip()

class HealthResponse(BaseModel):
    status: str; version: str; circuit_breaker: str; cache: str

class ReadyResponse(BaseModel):
    ready: bool; kokoro_reachable: bool; uptime_seconds: float
```

### 6.2 共享錯誤基底（`app/models/errors.py`）

```python
# 避免反向依賴（Layer 5 → Layer 4）
class ClientSideError(Exception):
    """4xx 標記。CircuitBreaker 用 isinstance(exc, ClientSideError)
    排除 4xx 錯誤對斷路閾值的計數。"""
    pass
```

### 6.3 SSML Parser — FR-02（`app/processing/ssml_parser.py`）

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import xml.etree.ElementTree as ET

class SegmentType(str, Enum):
    TEXT = "text"; BREAK = "break"; EMPHASIS = "emphasis"; PHONEME = "phoneme"

@dataclass
class SSMLSegment:
    type: SegmentType; text: str
    break_ms: Optional[int] = None
    emphasis_level: Optional[str] = None
    phoneme_alphabet: Optional[str] = None
    phoneme_ph: Optional[str] = None
    voice_name: Optional[str] = None
    prosody: dict = field(default_factory=dict)

class SSMLParser:
    """FR-02: 解析 SSML 標記。支援 <speak>, <break>, <prosody>,
    <emphasis>, <voice>, <phoneme>。"""
    def parse(self, text: str) -> list[SSMLSegment]:
        """無 <speak> 根標籤時自動包裝。Raises: SSMLParseError (L1)。"""
        ...
    def _parse_element(self, element: ET.Element, inherited_prosody: dict) -> list[SSMLSegment]: ...
    def _normalize_break(self, time_str: str) -> int: ...

class SSMLParseError(ValueError): pass  # L1
```

### 6.4 Lexicon Mapper — FR-01（`app/processing/lexicon_mapper.py`）

```python
import re
from pathlib import Path

class LexiconMapper:
    """FR-01: 台灣中文詞彙替換。覆蓋率目標 ≥ 95%（≥ 50 詞）。"""
    def __init__(self, lexicon_path: Path | None = None) -> None:
        self._lexicon_path = lexicon_path or Path(__file__).parent.parent / "data" / "lexicon_tw.json"
        self._mapping: dict[str, str] = {}; self._pattern: re.Pattern | None = None
        self._load()
    def _load(self) -> None: ...
    def apply(self, text: str) -> str:
        """單次正則表達式穿越，長詞優先。"""
        ...
    def get_coverage_stats(self) -> dict[str, int]: ...
```

### 6.5 Text Chunker — FR-03（`app/processing/text_chunker.py`）

```python
import re
from dataclasses import dataclass

MAX_CHUNK_SIZE = 250  # 字元

@dataclass
class ChunkResult:
    text: str; level: int; index: int  # 1=句子, 2=子句, 3=片語

class TextChunker:
    """FR-03: 三級遞迴文本切分。

    L1: 句子邊界（。！？.!? ＋段落換行）
    L2: 子句邊界（，，；：,;:）
    L3: 片語邊界（空白、的了吧呢啊）
    遞迴降級；最後手段為 MAX_CHUNK_SIZE 硬切。"""
    LEVEL1_PATTERN = re.compile(r'(?<=[。！？.!?\n])\s*')
    LEVEL2_PATTERN = re.compile(r'(?<=[，；：,;:])\s*')
    LEVEL3_PATTERN = re.compile(r'(?<=[\s的了吧呢啊])')

    def chunk(self, text: str) -> list[ChunkResult]: ...
    def _recursive_chunk(self, text: str, level: int, base_index: int) -> list[ChunkResult]: ...
    def _hard_split(self, text: str, level: int, base_index: int) -> list[ChunkResult]: ...
```

### 6.6 Synth Engine — FR-04（`app/synth/synth_engine.py`）

```python
import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.backend.kokoro_client import KokoroClient
    from app.infrastructure.circuit_breaker import CircuitBreaker

@dataclass
class SynthesisRequest:
    text: str; voice: str; speed: float; chunk_index: int

@dataclass
class SynthesisResult:
    audio_bytes: bytes; chunk_index: int; duration_ms: float

class SynthEngine:
    """FR-04: 分塊並行非同步合成。使用 asyncio.gather()。"""
    def __init__(self, kokoro_client: "KokoroClient",
                 circuit_breaker: "CircuitBreaker") -> None:
        self._client = kokoro_client; self._circuit_breaker = circuit_breaker

    async def synthesize_chunks(self, chunks: list[str], voice: str,
                                 speed: float, max_concurrency: int = 10) -> list[bytes]:
        """並行合成，按 chunk_index 排序回傳。
        Raises: SynthesisPartialError (L3), SynthesisUnavailableError (L4)。"""
        ...

class SynthesisPartialError(RuntimeError):
    def __init__(self, partial_results: list[bytes], failed_indices: list[int]):
        self.partial_results = partial_results; self.failed_indices = failed_indices

class SynthesisUnavailableError(RuntimeError):
    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = retry_after_seconds
```

### 6.7 Kokoro Client — FR-09（`app/backend/kokoro_client.py`）

```python
import httpx, asyncio
from app.models.errors import ClientSideError

class KokoroClient:
    """FR-09: Kokoro TTS API 代理客戶端。Lazy Init + 雙重檢查鎖定。"""
    def __init__(self, config) -> None:
        self._config = config; self._client: httpx.AsyncClient | None = None
        self._init_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._init_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        base_url=self._config.kokoro.base_url,
                        timeout=httpx.Timeout(connect=5.0,
                            read=self._config.kokoro.read_timeout,
                            write=10.0, pool=5.0),
                        limits=httpx.Limits(
                            max_connections=self._config.kokoro.max_connections,
                            max_keepalive_connections=10))
        return self._client

    async def synthesize(self, text: str, voice: str, speed: float) -> bytes:
        """POST 到 Kokoro /v1/audio/speech，回傳 MP3 位元組。
        Raises: KokoroConnectionError, KokoroAPIError, KokoroTimeoutError (皆 L4)。"""
        ...
    async def list_voices(self) -> list[dict]: ...
    async def health_check(self) -> bool: ...
    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose(); self._client = None

class KokoroConnectionError(OSError): pass  # L4
class KokoroAPIError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code; self.detail = detail
class KokoroClientError(KokoroAPIError, ClientSideError): pass  # L4 sub: 4xx 不計 CB
class KokoroServerError(KokoroAPIError): pass  # L4 sub: 5xx 計入 CB
class KokoroTimeoutError(TimeoutError): pass  # L4
```

### 6.8 Circuit Breaker — FR-05（`app/infrastructure/circuit_breaker.py`）

```python
import asyncio, time
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")

class CircuitState(str, Enum):
    CLOSED = "closed"; OPEN = "open"; HALF_OPEN = "half_open"

class CircuitBreaker:
    """FR-05: 非同步斷路器。

    狀態機：
      CLOSED → OPEN:    failure_count >= failure_threshold
      OPEN → HALF_OPEN: time >= recovery_timeout_s
      HALF_OPEN → CLOSED: probe 成功
      HALF_OPEN → OPEN:   probe 失敗
    """
    def __init__(self, failure_threshold: int = 3,
                 recovery_timeout_s: float = 10.0, name: str = "kokoro") -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout_s = recovery_timeout_s
        self._name = name
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState: return self._state
    @property
    def seconds_until_half_open(self) -> float: ...

    async def call(self, coro_factory: Callable[[], Awaitable[T]]) -> T:
        """OPEN 時快速失敗拋出 CircuitBreakerOpenError。"""
        ...
    async def _on_success(self) -> None:
        async with self._lock:
            self._failure_count = 0; self._state = CircuitState.CLOSED

    async def _on_failure(self, exc: Exception) -> None:
        from app.models.errors import ClientSideError
        if isinstance(exc, ClientSideError): return  # 不計入
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN

    def get_metrics(self) -> dict[str, Any]:
        return {"state": self._state.value, "failure_count": self._failure_count,
                "failure_threshold": self._failure_threshold,
                "seconds_until_half_open": self.seconds_until_half_open}

class CircuitBreakerOpenError(RuntimeError):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker OPEN; retry after {retry_after:.1f}s")
```

### 6.9 Redis Cache — FR-06（`app/infrastructure/redis_cache.py`）

```python
import hashlib
from typing import Optional

class RedisCache:
    """FR-06: 選配非同步 Redis 快取，優雅降級。

    url=None 時永久停用（無操作模式）。
    Cache key = SHA-256(text + "|" + voice + "|" + str(speed))"""
    def __init__(self, config) -> None:
        self._url = config.redis.url; self._ttl = config.redis.ttl_seconds
        self._redis = None; self._enabled = config.redis.url is not None
        self._available = False

    @staticmethod
    def make_key(text: str, voice: str, speed: float) -> str:
        return "tts:" + hashlib.sha256(f"{text}|{voice}|{speed:.4f}".encode()).hexdigest()

    async def get(self, key: str) -> Optional[bytes]: ...  # None = miss/disabled
    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        """Redis 不可用時無操作（L3 優雅降級）。"""
        ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...
```

### 6.10 Audio Converter — FR-08（`app/infrastructure/audio_converter.py`）

```python
import asyncio, shutil

class AudioConverter:
    """FR-08: ffmpeg 音訊格式轉換（Lazy Init）。支援 MP3 ↔ WAV。"""
    def __init__(self) -> None:
        self._ffmpeg_path: str | None = None; self._init_lock = asyncio.Lock()

    async def _get_ffmpeg(self) -> str:
        """雙重檢查鎖定。找不到拋出 AudioConverterNotFoundError。"""
        if self._ffmpeg_path is None:
            async with self._init_lock:
                if self._ffmpeg_path is None:
                    path = shutil.which("ffmpeg")
                    if path is None:
                        raise AudioConverterNotFoundError("ffmpeg not found in PATH.")
                    self._ffmpeg_path = path
        return self._ffmpeg_path

    async def convert(self, audio_data: bytes, target_format: str,
                      source_format: str = "mp3") -> bytes:
        """Raises: AudioConverterError (L2), AudioConverterNotFoundError (L2)。"""
        ...

class AudioConverterError(RuntimeError): pass  # L2
class AudioConverterNotFoundError(AudioConverterError): pass  # L2
```

### 6.11 Config Loader（`app/infrastructure/config_loader.py`）

```python
from pathlib import Path
from pydantic import BaseModel, Field
import yaml
from functools import lru_cache

class KokoroConfig(BaseModel):
    base_url: str = "http://localhost:8880"; read_timeout: float = 30.0; max_connections: int = 20
class RedisConfig(BaseModel):
    url: str | None = None; ttl_seconds: int = 86400
class AuthConfig(BaseModel):
    api_keys: list[str] = Field(default_factory=list); jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
class ChunkerConfig(BaseModel):
    max_chunk_size: int = 250; max_concurrency: int = 10
class CircuitBreakerConfig(BaseModel):
    failure_threshold: int = 3; recovery_timeout_s: float = 10.0; name: str = "kokoro"
class AppConfig(BaseModel):
    env: str = "production"; version: str = "6.13.0"
    kokoro: KokoroConfig = Field(default_factory=KokoroConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    chunker: ChunkerConfig = Field(default_factory=ChunkerConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)

@lru_cache(maxsize=1)
def get_config(config_path: str = "config.yaml") -> AppConfig:
    """首次呼叫後快取。Raises: ConfigError (L1)。"""
    path = Path(config_path)
    data = yaml.safe_load(open(path)) if path.exists() else {}
    return AppConfig(**data)

class ConfigError(ValueError): pass  # L1
```

### 6.12 Auth Middleware（`app/infrastructure/auth.py`）

```python
import hmac
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import jwt

EXEMPT_PATHS = {"/health", "/ready", "/docs", "/openapi.json"}

class AuthMiddleware(BaseHTTPMiddleware):
    """驗證所有非豁免路徑的 API Key 或 JWT。"""
    def __init__(self, app, config) -> None: super().__init__(app); self._config = config
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS: return await call_next(request)
        credentials = await self._extract_credentials(request)
        if not await self._validate(credentials): raise HTTPException(status_code=401)
        return await call_next(request)
    def _validate_api_key(self, token: str) -> bool:
        return any(hmac.compare_digest(token.encode(), key.encode())
                   for key in self._config.auth.api_keys)
    def _validate_jwt(self, token: str) -> bool: ...
```

### 6.13 CLI Tool — FR-07（`app/cli/main.py`）

```python
import asyncio, typer, httpx

app = typer.Typer(name="tts-v610", help="台灣中文 TTS CLI")

@app.command()
def synthesize(
    input: str = typer.Option(..., "--input", "-i"),
    output: str = typer.Option(..., "--output", "-o"),
    voice: str = typer.Option("zh-TW-1", "--voice", "-v"),
    speed: float = typer.Option(1.0, "--speed", "-s", min=0.25, max=4.0),
    format: str = typer.Option("mp3", "--format", "-f"),
    ssml: bool = typer.Option(False, "--ssml"),
    backend: str = typer.Option("http://localhost:8000", "--backend", "-b"),
    api_key: str = typer.Option("", "--api-key", envvar="TTS_API_KEY"),
) -> None:
    """FR-07: CLI 命令列工具。"""
    asyncio.run(_run(input, output, voice, speed, format, ssml, backend, api_key))

async def _run(...): ...
```

### 6.14 Speech Orchestrator（`app/orchestrator/speech_orchestrator.py`）

```python
from app.models.speech import SpeechRequest
from app.processing.ssml_parser import SSMLParser
from app.processing.lexicon_mapper import LexiconMapper
from app.processing.text_chunker import TextChunker
from app.synth.synth_engine import SynthEngine
from app.infrastructure.redis_cache import RedisCache
from app.infrastructure.audio_converter import AudioConverter

class SpeechOrchestrator:
    """Layer 2: 協調完整 TTS 合成管線。所有依賴透過建構子注入。"""
    def __init__(self, ssml_parser: SSMLParser, lexicon_mapper: LexiconMapper,
                 text_chunker: TextChunker, synth_engine: SynthEngine,
                 redis_cache: RedisCache, audio_converter: AudioConverter) -> None:
        self._ssml_parser = ssml_parser; self._lexicon_mapper = lexicon_mapper
        self._text_chunker = text_chunker; self._synth_engine = synth_engine
        self._redis_cache = redis_cache; self._audio_converter = audio_converter

    async def synthesize(self, request: SpeechRequest) -> bytes:
        """執行完整合成管線。
        Raises: SynthesisUnavailableError (L4), SynthesisPartialError (L3),
                SSMLParseError (L1)。"""
        ...
```

### 6.15 FastAPI 依賴注入工廠（`app/api/dependencies.py`）

```python
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
    """建構並連線完整依賴圖。應用程式啟動時呼叫一次。"""
    config = get_config()
    # Layer 5
    circuit_breaker = CircuitBreaker(
        failure_threshold=config.circuit_breaker.failure_threshold,
        recovery_timeout_s=config.circuit_breaker.recovery_timeout_s,
        name=config.circuit_breaker.name)
    redis_cache = RedisCache(config=config)
    audio_converter = AudioConverter()
    # Layer 4
    kokoro_client = KokoroClient(config=config)
    # Layer 3
    ssml_parser = SSMLParser()
    lexicon_mapper = LexiconMapper()
    text_chunker = TextChunker()
    synth_engine = SynthEngine(kokoro_client=kokoro_client, circuit_breaker=circuit_breaker)
    # Layer 2
    return SpeechOrchestrator(
        ssml_parser=ssml_parser, lexicon_mapper=lexicon_mapper,
        text_chunker=text_chunker, synth_engine=synth_engine,
        redis_cache=redis_cache, audio_converter=audio_converter)

def get_orchestrator
(app: Request) -> SpeechOrchestrator:
    """FastAPI Depends() 工廠 — 回傳 singleton orchestrator。"""
    return app.state.orchestrator
```

---

## 7. L1–L4 錯誤處理策略

### 7.1 錯誤等級定義

| 等級 | 名稱 | 意義 | 預設處理 |
|------|------|------|---------|
| **L1** | 輸入錯誤 | 呼叫者提供的無效/格式錯誤輸入 | 立即回傳 4xx，不重試 |
| **L2** | 工具錯誤 | 外部工具（ffmpeg、子程序）失敗 | 指數退避重試最多 3 次 |
| **L3** | 執行錯誤 | 部分系統失敗，可優雅降級 | 降級，回傳部分結果或 fallback |
| **L4** | 系統錯誤 | 關鍵基礎設施故障 | 斷路器 + 警報；回傳 503 |

### 7.2 錯誤分類表

| 錯誤類別 | 模組 | 等級 | HTTP 狀態碼 | 重試 | 處理策略 |
|---------|------|------|------------|------|---------|
| `SSMLParseError` | SSMLParser | L1 | 422 | 否 | 立即回傳含 XML 行號資訊的錯誤 |
| `ValidationError`（Pydantic） | API Routes | L1 | 422 | 否 | FastAPI 預設處理器 |
| `HTTPException(401)` | AuthMiddleware | L1 | 401 | 否 | 拒絕請求，只記錄 IP |
| `ConfigError` | ConfigLoader | L1 | 500* | 否 | 啟動時致命錯誤；阻止伺服器啟動 |
| `AudioConverterError` | AudioConverter | L2 | 500 | 3× | 重試 ffmpeg 子程序；3 次失敗後 L4 |
| `AudioConverterNotFoundError` | AudioConverter | L2 | 500 | 否 | 立即回傳（設定問題） |
| `KokoroConnectionError` | KokoroClient | L4 | 503 | Via CB | 斷路器記錄失敗 |
| `KokoroAPIError` | KokoroClient | L4 | 502 | Via CB | 斷路器記錄失敗 |
| `KokoroTimeoutError` | KokoroClient | L4 | 504 | Via CB | 斷路器記錄失敗 |
| `CircuitBreakerOpenError` | CircuitBreaker | L4 | 503 | 否 | 立即回傳含 `Retry-After` header |
| `SynthesisPartialError` | SynthEngine | L3 | 206 | 部分 | 回傳部分音訊含警告 header |
| `SynthesisUnavailableError` | SynthEngine | L4 | 503 | 否 | 傳播至 API 層 |
| `RedisError`（任何） | RedisCache | L3 | N/A | 否 | 無聲停用快取；繼續執行 |

### 7.3 錯誤回應結構

```python
class ErrorResponse(BaseModel):
    error: str          # 機器可讀錯誤碼
    message: str        # 人類可讀描述（不回傳使用者輸入）
    level: str          # "L1" | "L2" | "L3" | "L4"
    retry_after: float | None = None  # 503 時的秒數
    request_id: str     # 日誌關聯用 UUID
```

### 7.4 全域例外處理器註冊

```python
# app/main.py
@app.exception_handler(SSMLParseError)       # → 422
@app.exception_handler(SynthesisUnavailableError)  # → 503 + Retry-After
@app.exception_handler(CircuitBreakerOpenError)    # → 503 + Retry-After
@app.exception_handler(SynthesisPartialError)      # → 206 + partial audio
@app.exception_handler(Exception)                   # → 500 (sanitized)
```

---

## 8. 安全性架構

### 8.1 認證流程

```
Request → Path in EXEMPT_PATHS? ── YES ──→ bypass → handler
              │ NO
         Extract Authorization header
              │
         ├── Missing → 401
         ├── Bearer matches api_keys (hmac.compare_digest) → PASS
         ├── Valid JWT (signature + expiry) → PASS
         └── Neither → 401 Unauthorized
```

### 8.2 安全控制矩陣

| 控制項 | 實作 | 說明 |
|-------|------|------|
| **傳輸加密** | HTTPS/TLS（由反向代理 Nginx/Caddy 終止） | 服務本身跑 HTTP；TLS 在代理層終止 |
| **認證** | API Key（定時比對）或 JWT（HS256/RS256） | 在 `config.yaml:auth` 設定 |
| **輸入驗證** | Pydantic validators 去除控制字元；max_length=10000 | 不會有使用者輸入傳到 shell 命令 |
| **日誌脫敏** | Logging middleware：只記錄 request_id、path、status，不記錄 body | `structlog` + PII 過濾器 |
| **不留存音訊** | 音訊 bytes 只存在記憶體；從不寫入磁碟 | Cache 只存 Redis（有加密時加密） |
| **SSML 注入** | `xml.etree.ElementTree` 解析（無外部實體解析） | 使用 `defusedxml` 防止 XXE |
| **速率限制** | 可設定 middleware（slowapi / token bucket） | 按 API Key 套用 |
| **依賴固定** | `requirements.txt` 精確版本 + `pip-audit` in CI | 防止供應鏈攻擊 |

### 8.3 機密管理

- API Key 和 JWT Secret 從 `config.yaml` 或環境變數載入
- 環境變數優先於設定檔
- 機密永不記錄、永不包含在錯誤回應中
- 生產環境：使用 Docker secrets 或 Kubernetes secrets，啟動時掛載

### 8.4 輸入驗證層

```
Layer 1 (HTTP):    Content-Type 檢查、大小限制（body 最大 10MB）
Layer 2 (Pydantic):  欄位型別/範圍驗證、自訂 validators
Layer 3 (SSML):    嚴格 XML 解析，無外部實體解析
Layer 4 (Lexicon): 唯讀操作內部資料 — 無注入風險
```

---

## 9. NFR 實作策略

| NFR | 需求 | 實作策略 | 測量方式 | 目標 |
|-----|------|---------|---------|------|
| **NFR-01** | TTFB < 300ms | Redis 快取命中繞過所有處理；快取命中 TTFB ≈ 0ms | `time.perf_counter()` 量測；Prometheus histogram | p95 < 300ms |
| **NFR-02** | 詞彙覆蓋率 ≥ 80%（目標 95%） | LexiconMapper 載入 ≥ 50 詞；標準語料庫上計算覆蓋率 | CI 中呼叫 `get_coverage_stats()`；斷言 ≥ 80% | ≥ 80%（目標 95%） |
| **NFR-03** | 變調正確率 ≥ 95% | 詞彙表中的音韻項目明確編碼聲調變體 | 自動化 MOS-LQO 或 N=200 手動審查 | ≥ 95% |
| **NFR-04** | API 可用率 ≥ 99% | CircuitBreaker 防止級聯故障；`/health` 和 `/ready` 豁免認證 | Uptime 監控；SLO dashboard | ≥ 99% |
| **NFR-05** | 錯誤恢復 < 10s | CircuitBreaker `recovery_timeout_s = 10.0` | `seconds_until_half_open` metric；整合測試 | < 10s |
| **NFR-06** | 測試覆蓋率 ≥ 80% | `pytest-cov` 在 CI 中強制執行 | `pytest --cov=app --cov-fail-under=80` | ≥ 80% |
| **NFR-07** | 斷路器恢復 < 10s | 同 NFR-05 | 整合測試注入 3 次失敗後量測恢復時間 | < 10s |

---

## 10. 目錄結構

```
tts-kokoro-v613/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app factory, lifespan, middleware
│   ├── api/                             # LAYER 1
│   │   ├── routes.py                    # 所有路由處理者
│   │   ├── health.py                    # /health, /ready
│   │   └── dependencies.py              # FastAPI Depends() 工廠
│   ├── orchestrator/                    # LAYER 2
│   │   └── speech_orchestrator.py       # SpeechOrchestrator
│   ├── processing/                      # LAYER 3
│   │   ├── ssml_parser.py               # FR-02
│   │   ├── lexicon_mapper.py             # FR-01
│   │   └── text_chunker.py              # FR-03
│   ├── synth/                           # LAYER 3 (I/O)
│   │   └── synth_engine.py              # FR-04
│   ├── backend/                         # LAYER 4
│   │   └── kokoro_client.py             # FR-09
│   ├── infrastructure/                  # LAYER 5
│   │   ├── circuit_breaker.py           # FR-05
│   │   ├── redis_cache.py              # FR-06
│   │   ├── audio_converter.py          # FR-08
│   │   ├── config_loader.py
│   │   └── auth.py
│   ├── models/
│   │   ├── speech.py                    # SpeechRequest, VoiceInfo
│   │   └── errors.py                    # ClientSideError
│   ├── data/
│   │   └── lexicon_tw.json              # ≥ 50 詞
│   └── cli/
│       └── main.py                      # FR-07: tts-v610
├── tests/                               # 測試套件（鏡像 app/ 結構）
├── 01-requirements/
├── 02-architecture/
├── config.yaml / config.example.yaml
├── requirements.txt / requirements-dev.txt
├── pyproject.toml / pytest.ini
├── Dockerfile / docker-compose.yml
└── .env.example
```

---

## 11. 設定檔結構

```yaml
# config.yaml — tts-kokoro-v613 執行期設定
# 所有值可被 TTS_ 前綴環境變數覆蓋

env: "production"           # production | development | test
version: "6.13.0"
log_level: "INFO"
host: "0.0.0.0"; port: 8000

kokoro:
  base_url: "http://localhost:8880"
  read_timeout: 30.0; connect_timeout: 5.0
  max_connections: 20; max_keepalive: 10

redis:
  url: null                           # null = 停用
  ttl_seconds: 86400                  # 24 小時
  max_connections: 10; socket_timeout: 5.0

auth:
  api_keys: ["change-me-in-production"]
  jwt_secret: null                    # null = 停用 JWT
  jwt_algorithm: "HS256"
  jwt_expiry_seconds: 3600

processing:
  lexicon_path: "app/data/lexicon_tw.json"
  max_input_chars: 10000
  max_chunk_size: 250

synth:
  max_concurrency: 10
  default_voice: "zh-TW-1"; default_speed: 1.0

circuit_breaker:
  failure_threshold: 3                # FR-05
  recovery_timeout_s: 10.0           # FR-05
  name: "kokoro"

rate_limit:
  enabled: true
  requests_per_minute: 60; burst: 10

observability:
  metrics_enabled: true
  trace_enabled: false
  request_id_header: "X-Request-ID"

audio:
  default_format: "mp3"              # mp3 | wav
  ffmpeg_path: null                   # null = 從 PATH 自動偵測
  max_output_bytes: 52428800          # 50MB
```

---

## 12. 依賴關係圖

### 12.1 模組依賴映射

```
app/main.py
    ├── app/api/routes.py
    │       ├── app/models/speech.py
    │       ├── app/orchestrator/speech_orchestrator.py
    │       └── app/infrastructure/auth.py
    └── app/orchestrator/speech_orchestrator.py
            ├── app/processing/ssml_parser.py
            ├── app/processing/lexicon_mapper.py
            ├── app/processing/text_chunker.py
            ├── app/synth/synth_engine.py
            │       └── app/backend/kokoro_client.py
            │               ├── app/infrastructure/circuit_breaker.py
            │               └── app/infrastructure/config_loader.py
            ├── app/infrastructure/redis_cache.py
            └── app/infrastructure/audio_converter.py
```

### 12.2 循環依賴分析

| 潛在循環 | 狀態 | 緩解措施 |
|---------|------|---------|
| `synth_engine → kokoro_client → circuit_breaker` | 無循環 | 單向依賴 |
| `circuit_breaker → kokoro_client` | **已解決** | `ClientSideError` 基底類別置於 `app/models/errors.py`（共享層）；`KokoroClientError` 繼承它；CB 用 `isinstance(exc, ClientSideError)` 檢查 |
| `orchestrator → synth_engine → orchestrator` | **禁止** | SynthEngine 不得引用 orchestrator |
| `routes → orchestrator → routes` | **禁止** | Orchestrator 不得引用 API 層 |
| `config_loader → 任何 app 模組` | **禁止** | ConfigLoader 零 app 模組引用 |

### 12.3 外部依賴版本

```
fastapi>=0.111.0,<0.112
uvicorn[standard]>=0.29.0,<0.30
httpx>=0.27.0,<0.28
pydantic>=2.7.0,<3.0
pydantic-settings>=2.2.0,<3.0
redis>=5.0.3,<6.0          # 選配
defusedxml>=0.7.1
PyJWT>=2.8.0,<3.0
typer>=0.12.0,<0.13
pyyaml>=6.0.1
structlog>=24.1.0
```

---

## 13. ADR 參考表

| ADR ID | 標題 | 決策 | 狀態 | 日期 |
|--------|------|------|------|------|
| ADR-001 | FastAPI 作為代理框架 | 使用 FastAPI + uvicorn 提供非同步 HTTP 服務 | Accepted | 2026-04-01 |
| ADR-002 | 外部依賴的 Lazy Init 模式 | 所有 `_client`/`_conn` 屬性初始為 `None`，在首次使用時初始化 | Accepted | 2026-04-01 |
| ADR-003 | 三級遞迴文本切分 | 句子 → 子句 → 片語遞迴切分，最大 250 字元 | Accepted | 2026-04-01 |
| ADR-004 | 斷路器狀態機 | Closed/Open/Half-Open：失敗 ≥ 3 → Open，10s → Half-Open | Accepted | 2026-04-01 |

---

*軟體架構文件終*
*下次審查：Phase 3 實作完成後*
