# SAD.md — tts-kokoro-v613 軟體架構文件

> 版本：v6.13.2  
> Phase：Phase 2（架構設計）→ Phase 3（實作）  
> 日期：2026-04-02  
> 基於：SRS.md v6.13.1

---

## 0. Phase 3 框架對齊

### 0.1 定位說明

本文檔 Phase 2 階段以 Layer 視角呈現系統架構（§2–§9），符合架構設計產出要求。
進入 Phase 3 後，實作以 **FR 模組** 為單位組織，每個 FR 模組是獨立的實作/測試/審查單位。
Layer 結構降為 FR 模組內部實作細節，非頂層架構。

### 0.2 Phase 3 Entry Conditions

| 條件 | 驗證方式 |
|------|---------|
| Phase 2 APPROVE | Agent B APPROVE in Phase2_STAGE_PASS.md |
| state.json 初始化 | `.methodology/state.json` 存在且 `current_phase = 2` |
| sessions_spawn.log 存在 | A/B 記錄存在 |

### 0.3 Constitution 類型（Phase 3）

Phase 3 代碼實作使用 `sad` 作為 Constitution type。

| 維度 | 門檻 |
|------|------|
| 正確性（Correctness） | = 100% |
| 安全性（Security） | = 100% |
| 可維護性（Maintainability） | > 70% |
| 測試覆蓋率 | > 80% |

### 0.4 Quality Gate 工具（Phase 3）

| 指標 | 工具 | 命令 |
|------|------|------|
| Constitution | constitution/runner.py | `python3 quality_gate/constitution/runner.py --type sad` |
| ASPICE 合規 | doc_checker.py | `python3 quality_gate/doc_checker.py` |
| Phase Truth | phase-verify | `python cli.py phase-verify --phase 3` |
| 測試通過率 | pytest | `pytest tests/ -v` |
| 覆蓋率 | pytest --cov | `pytest --cov=app/ -v` |

---

## 1. 概覽

### 1.1 系統目的

基於 Kokoro-82M 之台灣中文最佳化語音合成系統，透過 Python FastAPI 代理層將後端 Kokoro Docker 服務轉化為具備台灣在地化能力的專業 TTS 系統。

### 1.2 系統邊界

```
┌─────────────────────────────────────────────────────┐
│                    Client (外部)                     │
│  CLI / HTTP Client / Telegram Bot / 其他 Agent      │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP/S
┌──────────────────────▼──────────────────────────────┐
│               tts-kokoro-v613 (本系統)                  │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │           API Layer (FastAPI)                  │   │
│  │  /health  /ready  /v1/proxy/voices            │   │
│  │  /v1/proxy/speech                             │   │
│  └──────────────────────────────────────────────┘   │
│                        │                              │
│  ┌─────────────────────▼────────────────────────┐   │
│  │           CLI Layer (Typer)                   │   │
│  │  tts-v610 文字/SSML/檔案 輸入                  │   │
│  └───────────────────────────────────────────────┘   │
│                        │                              │
│  ┌─────────────────────▼────────────────────────┐   │
│  │      Text Processing Layer (Module 1)         │   │
│  │  TaiwanLexicon → SSMLParser → TextSplitter    │   │
│  └───────────────────────────────────────────────┘   │
│                        │                              │
│  ┌─────────────────────▼────────────────────────┐   │
│  │      Synthesis Layer (Module 2)                │   │
│  │  AsyncEngine + CircuitBreaker                  │   │
│  └───────────────────────────────────────────────┘   │
│                        │                              │
│  ┌─────────────────────▼────────────────────────┐   │
│  │      Caching Layer (Module 3)                  │   │
│  │  RedisCache (optional, graceful degradation)   │   │
│  └───────────────────────────────────────────────┘   │
│                        │                              │
│  ┌─────────────────────▼────────────────────────┐   │
│  │      Audio Processing Layer (Module 4)         │   │
│  │  AudioConverter (ffmpeg)                       │   │
│  └───────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│           Kokoro Docker (http://localhost:8880)       │
│           - 音色合成                                  │
│           - MP3 編碼                                  │
└──────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│           Redis (optional)                            │
│           - 熱門語句快取                              │
│           - TTL: 24h                                  │
└──────────────────────────────────────────────────────┘
```

---

## 2. 模組架構

### 2.1 模組 1：Text Processing Layer

**職責**：文字預處理，涵蓋 FR-01、FR-02、FR-03

**子模組**：

| 子模組 | 檔案 | 職責 |
|--------|------|------|
| TaiwanLexicon | `engines/taiwan_linguistic.py` | 台灣詞彙映射（≥50詞） |
| SSMLParser | `engines/ssml_parser.py` | SSML 解析與音色標籤處理 |
| TextSplitter | `engines/text_splitter.py` | 三級遞迴文本切分（≤250字） |

**介面**：

```python
class TaiwanLexicon:
    def map(text: str) -> str: ...

class SSMLParser:
    def parse(ssml: str) -> SSMLDocument: ...
    def to_kokoro_params(doc: SSMLDocument) -> dict: ...

class TextSplitter:
    def split(text: str, max_chars: int = 250) -> list[str]: ...
```

**追溯至 SRS**：
- FR-01：台灣中文詞彙映射（≥50詞）
- FR-02：SSML 解析（含 `<voice>` 標籤）
- FR-03：智能文本切分（≤250字）

**NFR 覆蓋**：
- NFR-02：LEXICON 覆蓋率 ≥ 80%（目標 ≥ 95%）
- NFR-03：變調正確率 ≥ 95%

---

### 2.2 模組 2：Synthesis Layer

**職責**：非同步並行合成與可靠性保護，涵蓋 FR-04、FR-05

**子模組**：

| 子模組 | 檔案 | 職責 |
|--------|------|------|
| AsyncEngine | `engines/synthesis.py` | httpx.AsyncClient 並行合成 |
| CircuitBreaker | `middleware/circuit_breaker.py` | 三態斷路器保護 |

**介面**：

```python
class AsyncSynthesisEngine:
    def synthesize(chunks: list[str], voice: str, speed: float) -> bytes: ...

class CircuitBreaker:
    def call(func: Callable, *args, **kwargs) -> Any:
    # 狀態：CLOSED → OPEN → HALF_OPEN → CLOSED
    # 失敗閾值：3 次，恢復計時：10 秒
```

**追溯至 SRS**：
- FR-04：並行合成引擎（httpx.AsyncClient + MP3 串接）
- FR-05：斷路器（失敗 ≥ 3 → Open，10 秒後 Half-Open）

**NFR 覆蓋**：
- NFR-01：TTFB < 300ms
- NFR-04：API 可用率 ≥ 99%
- NFR-05：錯誤恢復時間 < 10s
- NFR-07：斷路器恢復 < 10s

---

### 2.3 模組 3：Caching Layer

**職責**：可選 Redis 快取，涵蓋 FR-06

**子模組**：

| 子模組 | 檔案 | 職責 |
|--------|------|------|
| RedisCache | `cache/redis_cache.py` | Hash-based 快取，24h TTL |

**介面**：

```python
class RedisCache:
    def __init__(self, url: str | None = None): ...
    def get(text: str, voice: str, speed: float) -> bytes | None: ...
    def set(text: str, voice: str, speed: float, audio: bytes, ttl: int = 86400): ...
    # url=None 時自動降級（略過快取，直接合成）
```

**追溯至 SRS**：
- FR-06：Redis 快取（Key=hash(text+voice+speed)，TTL=24h）

**NFR 覆蓋**：
- NFR-01：TTFB < 300ms（快取命中時 TTFB ≈ 0ms）

---

### 2.4 模組 4：Audio Processing Layer

**職責**：音訊格式轉換，涵蓋 FR-08

**子模組**：

| 子模組 | 檔案 | 職責 |
|--------|------|------|
| AudioConverter | `audio_converter.py` | ffmpeg MP3 ↔ WAV 互轉 |

**介面**：

```python
class AudioConverter:
    def convert(input_path: Path, output_format: str) -> Path: ...
    # 支援：mp3 → wav, wav → mp3
    # 依賴：ffmpeg CLI（必要依賴）
```

**追溯至 SRS**：
- FR-08：ffmpeg 音訊格式轉換

---

### 2.5 模組 5：API Layer

**職責**：FastAPI HTTP 端點，涵蓋 FR-07

**子模組**：

| 子模組 | 檔案 | 職責 |
|--------|------|------|
| APIServer | `api/server.py` | FastAPI 端點路由 |
| CLIApp | `cli.py` | Typer CLI 命令列工具 |

**API 端點**：

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/health` | 健康檢查 |
| GET | `/ready` | 就緒檢查（Kokoro + Redis 狀態） |
| GET | `/v1/proxy/voices` | 音色列表 |
| POST | `/v1/proxy/speech` | 語音合成（JSON 或 SSML） |

**CLI 命令**：

```bash
tts-v610 "你好世界" -o output.mp3
tts-v610 --ssml "<speak>...</speak>" -o out.mp3
tts-v610 --file input.txt -o output/
```

**追溯至 SRS**：
- FR-07：CLI 命令列工具

---

## 3. 安全性設計

### 3.1 認證（Authentication）

| 層面 | 設計 |
|------|------|
| 對外 API | API 金鑰（`X-API-Key` header）或 JWT token |
| 本地 CLI | 無（localhost 信任） |
| Kokoro Backend | 内部網路，無需認證 |

**實施**：
```python
# api/server.py
@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    if request.url.path.startswith("/v1/"):
        api_key = request.headers.get("X-API-Key")
        if api_key != settings.API_KEY:
            raise HTTPException(status_code=401)
    return await call_next(request)
```

### 3.2 授權（Authorization）

| 音色分級 | 授權 | 說明 |
|---------|------|------|
| 公開音色 | 所有已驗證用戶 | `zf_xiaoxiao`, `zf_yunxi` 等 |
| 受限音色 | Admin 角色 | 實驗性音色（Alpha/Beta） |

**實施**：基於 role 的存取控制（RBAC），音色白名單。

### 3.3 加密（Encryption）

| 場景 | 設計 |
|------|------|
| 對外暴露（Production） | HTTPS/TLS 1.2+（反向代理 Nginx/Caddy） |
| 本機開發 | HTTP（localhost:8880） |
| Kokoro Backend | localhost，無需加密 |

### 3.4 資料保護（Data Protection）

| 措施 | 說明 |
|------|------|
| 日誌脫敏 | 音訊合成內容不寫入日誌 |
| 暫存清理 | 合成後的 MP3 檔案（若暫存）自動刪除 |
| 無持久化 | 使用者音訊資料不留存 server-side |

---

## 4. 錯誤處理架構

### 4.1 錯誤分類（L1–L4 四級制）

| 等級 | 名稱 | 說明 | 可復原 | 觸發熔斷 |
|------|------|------|--------|---------|
| **L1** | 配置錯誤 | 缺少環境變數、API Key 未設定 | ❌ | ✅ |
| **L2** | API 錯誤 | Kokoro 5xx、後端超時、網路中斷 | ✅ | ✅ |
| **L3** | 業務錯誤 | SSML 解析失敗、文本過長、超過 rate limit | ✅ | ✅ |
| **L4** | 預期異常 | 參數 Validation 失敗、檔案不存在 | ✅ | ❌ |

| 錯誤類型 | HTTP 狀態碼 | 處理策略 |
|---------|-------------|---------|
| 文字預處理失敗（SSML parse error） | 200（降級） | Fallback 純文字合成 |
| 後端 Kokoro 故障（5xx） | 503 | CircuitBreaker 觸發 |
| 網路超時（>30s） | 504 | 重試 1 次後返回錯誤 |
| Redis 不可用 | 200（降級） | 略過快取，直接合成 |
| ffmpeg 轉換失敗 | 422 | 返回明確錯誤訊息 |
| 認證失敗（L1） | 401 | 拒絕訪問 |

### 4.2 錯誤傳播鏈

```
Client Request
      │
      ▼
┌─────────────┐
│ API Layer   │ ← HTTP 401/422 處理
└──────┬──────┘
       ▼
┌─────────────┐
│ Cache Layer │ ← Redis 降級
└──────┬──────┘
       ▼
┌─────────────┐
│  TextProc   │ ← SSML Fallback
└──────┬──────┘
       ▼
┌─────────────┐
│ Synthesis   │ ← CircuitBreaker 保護
│  (Async)    │
└──────┬──────┘
       ▼
┌─────────────┐
│ Kokoro      │ ← 503 if circuit open
│ (localhost) │
└─────────────┘
```

### 4.3 Circuit Breaker 詳細行為

| 狀態 | 行為 |
|------|------|
| CLOSED | 正常流量，失敗計數遞增 |
| OPEN（失敗 ≥ 3） | 直接返回 503，不發請求 |
| HALF_OPEN（10 秒後） | 允許 1 個測試請求 |
| CLOSED（HALF_OPEN 成功） | 重置計數，恢復正常 |

---

## 5. 資料流

### 5.1 標準合成流程

```
1. Client → POST /v1/proxy/speech { text, voice, speed }
2. API Layer → 驗證 API Key
3. Cache Layer → 檢查 Redis（key=hash(text+voice+speed)）
   └→ Hit → 直接返回 MP3
   └→ Miss → 繼續
4. TextProc → TaiwanLexicon.map(text)
5. TextProc → SSMLParser.parse(ssml_text)
6. TextProc → TextSplitter.split(text, max_chars=250)
7. Synthesis → AsyncEngine.synthesize(chunks) [並行 N 請求]
8. Synthesis → MP3 串接
9. Cache Layer → set(text+voice+speed, mp3, ttl=24h)
10. AudioProc → [可選] ffmpeg convert to WAV
11. API Layer → 返回 MP3/WAV
```

### 5.2 CLI 流程

```
tts-v610 "文字" -o output.mp3
  └→ CLIApp → TextProc → Synthesis → output.mp3
```

---

## 6. 部署架構

### 6.1 元件相依

```
┌─────────────────────────────────────────┐
│           tts-kokoro-v613               │
│  Python 3.10+  │  FastAPI  │  httpx     │
└────────┬───────────────────┬─────────────┘
         │                   │
    ┌────▼────┐         ┌───▼────┐
    │  Redis  │         │ Kokoro │
    │(Optional)│         │ Docker │
    └─────────┘         │:8880    │
                       └────────┘
```

### 6.2 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `KOKORO_BACKEND_URL` | `http://localhost:8880` | Kokoro 後端 URL |
| `REDIS_URL` | `None`（停用快取） | Redis 連線 URL |
| `API_KEY` | `None`（停用認證） | API 金鑰 |
| `CIRCUIT_BREAKER_THRESHOLD` | `3` | 失敗閾值 |
| `CIRCUIT_BREAKER_TIMEOUT` | `10` | 恢復秒數 |
| `REQUEST_TIMEOUT` | `30` | 請求超時秒數 |

---

## 6. 模組化設計原則

本架構遵循以下設計原則：

| 原則 | 應用 | 說明 |
|------|------|------|
| **SRP（單一職責原則）** | 各 Module 獨立 | 每個模組只負責一個明確的領域 |
| **依賴注入（DI）** | FastAPI Depends | 便於測試替換 |
| **介面隔離（ISP）** | 模組 API | 避免過度耦合 |

例如：
- `Text Processing Layer` 只負責文字預處理
- `Synthesis Layer` 只負責並行合成
- `Caching Layer` 只負責快取查詢

---

## 7. 模組責任矩陣

| 模組 | FR-01 | FR-02 | FR-03 | FR-04 | FR-05 | FR-06 | FR-07 | FR-08 |
|------|-------|-------|-------|-------|-------|-------|-------|-------|
| Module 1: TextProc | ✅ | ✅ | ✅ | | | | | |
| Module 2: Synthesis | | | | ✅ | ✅ | | | |
| Module 3: Caching | | | | | | ✅ | | |
| Module 4: AudioProc | | | | | | | | ✅ |
| Module 5: API/CLI | | | | | | | ✅ | |

---

## 8. 追溯至 SRS（NFR）

| NFR | 模組/設計 | 實現方式 |
|-----|----------|---------|
| NFR-01（TTFB < 300ms） | Module 3（Caching） | Redis 快取命中繞過 Synthesis |
| NFR-02（LEXICON ≥ 80%） | Module 1 | TaiwanLexicon ≥ 50 詞 |
| NFR-03（變調正確率 ≥ 95%） | Module 1 | 詞彙映射 + 單元測試 |
| NFR-04（API 可用率 ≥ 99%） | Module 2 | CircuitBreaker 防止級聯故障 |
| NFR-05（錯誤恢復 < 10s） | Module 2 | CircuitBreaker 10 秒恢復 |
| NFR-06（測試覆蓋 ≥ 80%） | All | pytest --cov |
| NFR-07（斷路器恢復 < 10s） | Module 2 | CircuitBreaker 10 秒計時器 |

---

## 9. 技術決策摘要

| ADR # | 決策 | 採用 |
|-------|------|------|
| ADR-001 | 代理框架 | FastAPI + httpx |
| ADR-002 | 台灣化策略 | TaiwanLexicon 映射表 |
| ADR-003 | SSML 解析 | 手寫 XML Parser + AST |
| ADR-004 | 並行合成 | httpx.AsyncClient + asyncio.gather |
| ADR-005 | 熔斷機制 | 軟體斷路器（pycircuit） |
| ADR-006 | 快取策略 | Redis Hash，optional graceful degradation |

---

## 10. 目錄結構（Phase 3 FR 模組化）

> **原則**：每個 FR 模組有自己的目錄，Layer 是內部實作細節。

```
tts-kokoro-v613/
├── app/
│   ├── processing/                # FR-01, FR-02, FR-03 模組目錄
│   │   ├── __init__.py
│   │   ├── lexicon_mapper.py      # FR-01（TaiwanLexicon）
│   │   │   └── internals/         # 可選：內部 layer（如 /lexicon_data/）
│   │   ├── ssml_parser.py         # FR-02
│   │   └── text_chunker.py        # FR-03
│   ├── synth/                     # FR-04 模組目錄
│   │   ├── __init__.py
│   │   ├── async_engine.py        # FR-04（AsyncEngine）
│   │   └── circuit_breaker.py     # FR-05
│   ├── cache/                     # FR-06 模組目錄
│   │   ├── __init__.py
│   │   └── redis_cache.py
│   ├── audio/                     # FR-08 模組目錄
│   │   ├── __init__.py
│   │   └── audio_converter.py
│   ├── api/                       # FR-07 模組目錄
│   │   ├── __init__.py
│   │   ├── server.py
│   │   └── cli.py
│   └── main.py
├── tests/                         # 測試（與 FR 對應）
│   ├── test_fr01_lexicon.py
│   ├── test_fr02_ssml.py
│   ├── test_fr03_chunker.py
│   ├── test_fr04_synth.py
│   ├── test_fr05_circuit.py
│   ├── test_fr06_cache.py
│   ├── test_fr07_api.py
│   └── test_fr08_audio.py
├── quality_gate/                  # Phase 3 Quality Gate 工具
│   ├── constitution/
│   │   └── runner.py
│   └── doc_checker.py
├── .methodology/
│   └── state.json
├── 02-architecture/
│   ├── SAD.md
│   └── adr/
├── SRS.md
└── PROJECT_STATUS.md
```

### 10.1 FR 模組與 Layer 對照

| FR 模組 | 目錄 | Layer（內部實作） |
|---------|------|------------------|
| FR-01 LexiconMapper | `app/processing/` | TextProc Layer（內部） |
| FR-02 SSMLParser | `app/processing/` | TextProc Layer（內部） |
| FR-03 TextChunker | `app/processing/` | TextProc Layer（內部） |
| FR-04 AsyncEngine | `app/synth/` | Synthesis Layer（內部） |
| FR-05 CircuitBreaker | `app/synth/` | Synthesis Layer（內部） |
| FR-06 RedisCache | `app/cache/` | Caching Layer（內部） |
| FR-07 API/CLI | `app/api/` | API Layer（內部） |
| FR-08 AudioConverter | `app/audio/` | AudioProc Layer（內部） |

---

## 11. 安全性矩陣

| 威脅 | 緩解措施 | 驗證方式 |
|------|---------|---------|
| 未授權 API 存取 | API Key / JWT | 單元測試 |
| SSML 注入攻擊 | XML 解析白名單 | 滲透測試 |
| 後端 DoS | CircuitBreaker + Rate Limiting | 負載測試 |
| 敏感資料外洩 | 日誌脫敏，無持久化 | Code Review |

---

*文件狀態：Phase 3 準備完成（SAD 已與 SKILL.md Phase 3 框架對齊）*
*下次審查：Phase 3 實作完成後*
