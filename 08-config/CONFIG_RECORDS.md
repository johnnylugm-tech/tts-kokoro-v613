# CONFIG_RECORDS.md — Phase 8 配置管理記錄

> 版本：v1.0  
> Phase：Phase 8（配置管理）  
> 日期：2026-04-14  
> 依據：SRS.md v6.13.1、SAD.md v6.13.2、RISK_STATUS_REPORT.md  
> 框架遵循：本專案依循 [methodology-v2](https://github.com/johnnylugm-tech/methodology-v2) 框架開發  

---

## 1. 系統配置參數（System Configuration Parameters）

### 1.1 應用程式層級參數

| 參數名稱 | 值 | 來源 | 說明 |
|---------|-----|------|------|
| `APP_NAME` | `tts-kokoro-v613` | SRS.md §1 | 應用程式名稱 |
| `APP_VERSION` | `6.13.1` | SRS.md §1 | 目前版本 |
| `API_BASE_PATH` | `/api/tts` | SAD.md §7 | FastAPI 路由基底路徑 |
| `API_TIMEOUT` | `30` 秒 | SRS.md NFR-02 | 請求超時閾值 |
| `TTFB_TARGET` | `< 300ms` | SRS.md NFR-01 | 目標首位元組時間 |
| `MAX_CHUNK_SIZE` | `250` 字 | SRS.md FR-03 | 文本切分最大長度 |
| `LEXICON_MIN_COUNT` | `≥ 50` 詞 | SRS.md FR-01 | 詞彙映射最小數量 |
| `LEXICON_COVERAGE_TARGET` | `≥ 95%` | SRS.md NFR-01 | 詞彙覆蓋率目標 |

### 1.2 後端整合參數

| 參數名稱 | 值 | 來源 | 說明 |
|---------|-----|------|------|
| `KOKORO_BACKEND_URL` | `http://localhost:8880` | SRS.md §2 | Kokoro Docker HTTP 端點 |
| `KOKORO_HEALTH_ENDPOINT` | `/v1/health` | SAD.md §7 | 後端健康檢查端點（推斷） |
| `KOKORO_TIMEOUT` | `30` 秒 | SAD.md §7 | Kokoro 請求超時 |

### 1.3 斷路器參數（Circuit Breaker — FR-05）

| 參數名稱 | 值 | 來源 | 說明 |
|---------|-----|------|------|
| `CB_FAILURE_THRESHOLD` | `≥ 3` 次 | SRS.md FR-05 | 觸發斷路（Open）的連續失敗次數 |
| `CB_OPEN_DURATION` | `10` 秒 | SRS.md FR-05 | Open 狀態持續時間後進入 Half-Open |
| `CB_HALFOPEN_SUCCESS` | `1` 次成功 → Closed | SRS.md FR-05 | Half-Open 成功後關閉 |

### 1.4 Redis 快取參數（FR-06，可選）

| 參數名稱 | 值 | 來源 | 說明 |
|---------|-----|------|------|
| `REDIS_KEY_PREFIX` | `tts:` | SAD.md §7 | Redis Key 前綴 |
| `REDIS_CACHE_TTL` | `24` 小時 | SRS.md FR-06 | 快取存活時間 |
| `REDIS_KEY_HASH` | `SHA-256(text + voice + speed)` | SRS.md FR-06 | 快取鍵生成演算法 |
| `REDIS_ENABLED` | `Optional` | SRS.md FR-06 | 可選功能，缺席時自動降級 |

### 1.5 非同步引擎參數（FR-04）

| 參數名稱 | 值 | 來源 | 說明 |
|---------|-----|------|------|
| `ASYNC_CONCURRENCY` | `N`（同時請求數） | SAD.md §7 | 並行非同步 HTTP 請求數 |
| `CROSSFADE_ENABLED` | `Optional` | SRS.md FR-04 | pydub crossfade 消除接縫 |
| `MP3_CONCAT` | 直接串接 | SRS.md FR-04 | MP3 無需重新編碼 |

---

## 2. 環境變數（Environment Variables）

### 2.1 必要環境變數

| 環境變數 | 預設值 | 類型 | 說明 |
|---------|-------|------|------|
| `KOKORO_BACKEND_URL` | `http://localhost:8880` | `str` | Kokoro Docker 服務 URL |
| `LOG_LEVEL` | `INFO` | `str` | 日誌層級（DEBUG/INFO/WARNING/ERROR） |
| `API_HOST` | `0.0.0.0` | `str` | FastAPI 監聽主機 |
| `API_PORT` | `8000` | `int` | FastAPI 監聽埠 |

### 2.2 選配環境變數

| 環境變數 | 預設值 | 類型 | 說明 |
|---------|-------|------|------|
| `REDIS_URL` | `redis://localhost:6379/0` | `str` | Redis 連線 URL（可選） |
| `REDIS_ENABLED` | `false` | `bool` | 是否啟用 Redis 快取 |
| `API_KEY` | `None` | `str` | API 金鑰認證（對外暴露時必填） |
| `JWT_SECRET` | `None` | `str` | JWT 驗證密鑰（可選） |
| `FFMPEG_PATH` | `ffmpeg` | `str` | ffmpeg 可執行檔路徑 |
| `MAX_WORKERS` | `4` | `int` | 並行 worker 數量 |

### 2.3 環境變數驗證（由誰設定）

| 環境變數 | 設定時機 | 驗證方式 |
|---------|---------|---------|
| `KOKORO_BACKEND_URL` | 系統啟動時 | `httpx.AsyncClient` 連線測試 |
| `REDIS_URL` | 系統啟動時 | `redis.asyncio ping()` |
| `API_KEY` | 部署時（環境注入） | FastAPI dependency injection |

---

## 3. API 端點配置（API Endpoint Configuration）

### 3.1 內部 API（FastAPI Routes）

| 端點 | 方法 | 模組 | 說明 |
|------|------|------|------|
| `/api/tts` | `POST` | `src.api.routes` | 主要 TTS 合成端點 |
| `/api/tts/stream` | `POST` | `src.api.routes` | 流式 TTS 合成端點（推斷） |
| `/api/voices` | `GET` | `src.api.routes` | 查詢可用音色列表 |
| `/api/health` | `GET` | `src.api.routes` | 健康檢查端點 |
| `/api/cache/clear` | `POST` | `src.api.routes` | 清除快取端點（管理用） |

### 3.2 Kokoro 後端 API 合約

| 端點 | 方法 | 說明 |
|------|------|------|
| `POST /v1/tts` | `POST` | TTS 合成（主要） |
| `GET /v1/voices` | `GET` | 取得音色列表 |
| `GET /health` | `GET` | 健康檢查 |

**後端 URL（可配置）**：`http://localhost:8880`（預設）

### 3.3 音色名稱對照表

| 音色 ID | 名稱 | 類型 | 備註 |
|--------|------|------|------|
| `zf_xiaoxiao` | 官方音色 | 標準 | 中英混合 |
| `zf_yunxi` | 官方音色 | 標準 | 中文為主 |
| `zf_yunxi_female` | 台灣女生 | 台灣化 | FR-01 映射對象 |
| `zf_bao_female` | 台灣女生 | 台灣化 | FR-01 映射對象 |

---

## 4. Docker 配置（Docker Configuration）

### 4.1 Kokoro Docker 部署

| 項目 | 值 | 說明 |
|------|---|------|
| 映像名 | `ghcr.io/remsky/kokoro-onnx:latest` 或同等 | Kokoro-82M ONNX 映像 |
| 容器名 | `kokoro-tts` | 容器識別名 |
| 暴露埠 | `8880` | HTTP 服務埠 |
| 網路模式 | `host`（或 `bridge` + port mapping） | 網路配置 |
| 運行環境 | `Python 3.10+` | 容器內 Python 版本 |
| 健康檢查 | `curl http://localhost:8880/health` | 容器健康檢查 |

### 4.2 容器網路配置

```yaml
# docker-compose.yml 片段（推斷）
services:
  kokoro:
    image: ghcr.io/remsky/kokoro-onnx:latest
    container_name: kokoro-tts
    ports:
      - "8880:8880"
    networks:
      - tts-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8880/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  tts-proxy:  # FastAPI 代理層（可選獨立部署）
    build: .
    ports:
      - "8000:8000"
    depends_on:
      kokoro:
        condition: service_healthy
    environment:
      - KOKORO_BACKEND_URL=http://kokoro:8880
    networks:
      - tts-network

networks:
  tts-network:
    driver: bridge
```

### 4.3 環境變數注入（Docker）

| 變數 | 注入方式 | 位置 |
|------|---------|------|
| `KOKORO_BACKEND_URL` | `environment` | docker-compose.yml |
| `REDIS_URL` | `environment` | docker-compose.yml |
| `LOG_LEVEL` | `environment` | docker-compose.yml |

---

## 5. 依賴版本記錄（Dependency Version Records）

### 5.1 Python 核心依賴

| 套件 | 版本 | 用途 | 來源依據 |
|------|------|------|---------|
| `fastapi` | `≥ 0.109.0` | Web 框架 | SAD.md §3、FR-07 |
| `httpx` | `≥ 0.27.0` | 非同步 HTTP 客戶端 | SRS.md FR-04、SAD.md |
| `pydantic` | `≥ 2.0` | 資料驗證 | SAD.md §3 |
| `pydub` | `≥ 0.25.1` | 音訊處理（crossfade） | SRS.md FR-04 |
| `uvicorn` | `≥ 0.27.0` | ASGI 伺服器 | SAD.md §3 |
| `typer` | `≥ 0.12.0` | CLI 框架 | SRS.md FR-07 |
| `python-multipart` | `≥ 0.0.9` | 表單資料處理 | FastAPI 依賴 |
| `redis` | `≥ 5.0` | Redis 非同步客戶端 | SRS.md FR-06 |
| `python-dotenv` | `≥ 1.0.0` | 環境變數載入 | 配置管理 |

### 5.2 開發與測試依賴

| 套件 | 版本 | 用途 | 備註 |
|------|------|------|------|
| `pytest` | `≥ 8.0` | 單元測試框架 | Phase 4+ |
| `pytest-asyncio` | `≥ 0.23.0` | 非同步測試支援 | Phase 4+ |
| `pytest-cov` | `≥ 4.1` | 覆蓋率報告 | Phase 5+ |
| `ruff` | `≥ 0.2.0` | Linting 與格式化 | Phase 5+ |
| `mypy` | `≥ 1.8.0` | 靜態類型檢查 | Phase 5+ |

### 5.3 系統工具依賴（非 Python）

| 工具 | 版本 | 用途 | 備註 |
|------|------|------|------|
| `ffmpeg` | `≥ 4.0` | 音訊格式轉換（MP3↔WAV） | FR-08，非 Python |
| `curl` | `≥ 7.0` | 健康檢查 | 容器內 |

### 5.4 選配依賴

| 套件/工具 | 版本 | 用途 | 缺席時行為 |
|-----------|------|------|-----------|
| `redis-server` | `≥ 6.0` | Redis 快取服務 | 系統降級，略過快取 |

### 5.5 依賴版本衝突風險

| 套件組合 | 風險等級 | 說明 |
|---------|---------|------|
| `httpx` vs `requests` | 低 | httpx 用於非同步，requests 不使用 |
| `redis` vs `aioredis` | 低 | 使用 `redis.asyncio`，aioredis 已廢棄 |
| `fastapi` vs `flask` | 無 | 僅使用 FastAPI |

---

## 6. Phase 7 風險狀態更新

### 6.1 風險狀態總覽（Phase 8 起始）

| ID | 風險名稱 | 狀態 | Phase 8 行動 |
|----|---------|------|------------|
| R-01 | Kokoro Docker 崩潰 | 監控中 | 配置監控與斷路器 |
| R-02 | 斷路器誤判 | 監控中 | 持續觀察 |
| R-03 | Redis 失效 | 降級備援 | 已實作，略過機制 |
| R-04 | SSML 解析失敗 | 監控中 | Fallback 已實作 |
| R-05 | 文本切分破壞語意 | 監控中 | 三級遏歸已實作 |
| R-06 | Phase Truth < 70% | **主動修復中** | 待 Johnny 確認 4 項記錄 |
| R-07 | Constitution Score 逼近閾值 | **主動修復中** | 依賴 R-08 |
| **R-08** | **VERIFICATION.md 缺失** | ✅ **已修復** | `docs/VERIFICATION.md` 已建立 |
| R-09 | FrameworkEnforcer BLOCK | 待修復 | 依賴 R-06 完成 |
| R-10 | 覆蓋率未達標 | 監控中（接受型） | 長期優化 |

### 6.2 R-08 修復確認

**Phase 7 問題**：`docs/VERIFICATION.md` 不存在，導致 V-01 HIGH 違規。

**Phase 8 狀態**：`docs/VERIFICATION.md` 已建立，包含：
- 安全驗證結果摘要（Authentication、Authorization、Encryption、Data Protection）
- 各安全領域測試驗證記錄
- HIGH 違規已消除

**驗證命令**：
```bash
# 確認檔案存在
ls -la docs/VERIFICATION.md

# Constitution Check（含 V-01 驗證）
python3 quality_gate/constitution/runner.py --type sad
```

---

## 7. 配置版本管理

| 版本 | 日期 | 修改內容 | 負責人 |
|------|------|---------|--------|
| v1.0 | 2026-04-14 | 初始建立 Phase 8 配置記錄 | Agent A（DevOps） |

---

*本文件由 Agent A（DevOps）建立，用於 Phase 8 配置管理。*
*下次更新：Phase 8 完成後或配置變更時。*
