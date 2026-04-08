# SRS.md — tts-kokoro-v613 軟體需求規格

> 版本：v6.13.1  
> 專案：tts-kokoro-v613（實驗組）  
> 對照組：kokoro-taiwan-proxy  
> 日期：2026-03-31  
> 規格來源：SRS_raw.txt（docx 原文）
> 框架遵循：本專案依循 [methodology-v2](https://github.com/johnnylugm-tech/methodology-v2) 框架開發

---

## 1. 概述

### 1.1 目的
基於 Kokoro-82M 之台灣中文最佳化語音合成系統，透過 Python FastAPI 代理層將後端 Kokoro Docker 服務轉化為具備台灣在地化能力的專業 TTS 系統。

### 1.2 技術棧
- 後端：Kokoro Docker（`http://localhost:8880`）
- 代理層：FastAPI + httpx + Python 3.10+
- 可選快取：Redis

---

## 2. 功能需求（FR）

### FR-01：台灣中文詞彙映射

**描述**：在文本傳入 TTS 引擎前，進行台灣特有詞彙與發音的 LEXICON 映射。

**內容**：
- 詞彙映射 ≥ 50 詞（覆蓋率目標 ≥ 95%）
- 包含：科技詞（視頻→影片）、交通詞（地鐵→捷運）、日常詞（垃圾→ㄌㄜˋ ㄙㄜˋ）、食物詞（菠蘿→鳳梨）、職業詞（程序員→工程師）、科技詞（軟件→軟體）、發音詞（和→ㄏㄢˋ、吧→啦）

**邏輯驗證方法**：
- 測試案例：輸入「我要坐地鐵去看視頻」，預期輸出「我要坐捷運去看影片」
- 測試案例：輸入「菠蘿麵包」，預期輸出「鳳梨麵包」
- 測試案例：LEXICON 總詞彙數 ≥ 50

---

### FR-02：SSML 解析（含 `<voice>` 標籤）

**描述**：解析 SSML 標籤並映射為 Kokoro API 參數，支援音色切換。

**支援標籤**：
| 標籤 | 屬性 | 處理策略 |
|------|------|---------|
| `<speak>` | — | 根元素 |
| `<break>` | `time="500ms"` | 插入停頓 |
| `<prosody>` | `rate="0.9"` | 映射 speed |
| `<emphasis>` | `level="strong"` | speed ×1.1 |
| `<voice>` | `name="xxx"` | 音色切換 |
| `<phoneme>` | `alphabet="ipa"` | 保留原生 |

**邏輯驗證方法**：
- 測試案例：`<prosody rate="0.9">文字</prosody>` → speed=0.9
- 測試案例：`<voice name="zf_yunxi">文字</voice>` → 音色切換為 zf_yunxi
- 測試案例：`<break time="500ms"/>` → 插入停頓字元
- 測試案例：XML 解析失敗時 fallback 純文字

---

### FR-03：智能文本切分（Chunk ≤ 250 字）

**描述**：將長文本依三級遞迴邏輯切分，確保每段 ≤ 250 字。

**三級切分**：
1. 一級（句）：`。？！!?\n`
2. 二級（子句）：`。；：`（若仍 >100 字）
3. 三級（詞組）：`，`（若仍 >100 字）

**規則**：
- 每段最多 250 字
- 不在中英文混合字中間切斷

**邏輯驗證方法**：
- 測試案例：輸入 500 字長句 → 每段 ≤ 250 字
- 測試案例：含英文「AI」長句 → 不在 A/I 中間切斷
- 測試案例：三級切分遞迴驗證

---

### FR-04：並行合成引擎

**描述**：使用 httpx.AsyncClient 同時發出 N 個請求，MP3 直接串接。

**並行策略**：
- 同時發出 N 個非同步 HTTP 請求至 Kokoro 後端
- MP3 直接串接（無需重新編碼）
- 可選：pydub crossfade 消除接縫

**邏輯驗證方法**：
- 測試案例：5 個 Chunk 同時請求 → 總時間 < 各 Chunk 順序執行時間
- 測試案例：拼接後 MP3 可正常播放

---

### FR-05：斷路器（Circuit Breaker）

**描述**：後端故障時自動保護，失敗計數達閾值後断路。

**行為**：
- 失敗 ≥ 3 次 → Open
- Open 後 10 秒 → Half-Open
- 成功 → Closed

**邏輯驗證方法**：
- 測試案例：連續 3 次 5xx 錯誤 → 斷路器 Open
- 測試案例：斷路後請求 → HTTP 503

---

### FR-06：Redis 快取（可選）

**描述**：熱門語句結果快取，24 小時 TTL。

**設計**：
- Key：`hash(text + voice + speed)`
- TTL：24 小時
- 無 Redis 時自動略過

**邏輯驗證方法**：
- 測試案例：相同請求第二次 → 直接回傳快取（無後端請求）
- 測試案例：Redis 不可用時 → 正常降級至直接合成

---

### FR-07：CLI 命令列工具（tts-v610）

**描述**：提供命令列工具支援快速語音合成。

**使用範例**：
```bash
tts-v610 "你好世界" -o output.mp3
tts-v610 --ssml "<speak>...</speak>" -o out.mp3
tts-v610 --file input.txt -o output/
```

**支援參數**：
- `-i, --input`：輸入文字或檔案
- `-o, --output`：輸出檔案
- `-v, --voice`：音色或混合配方
- `-s, --speed`：語速 0.5-2.0
- `-f, --format`：mp3/wav
- `--ssml`：SSML 模式
- `--backend`：後端 URL

**邏輯驗證方法**：
- 測試案例：`tts-v610 --help` → 顯示完整說明
- 測試案例：輸入文字 → 產出 MP3 檔案

---

### FR-08：ffmpeg 音訊格式轉換

**描述**：使用 ffmpeg 將 MP3 轉換為 WAV，或 WAV 轉 MP3。

**支援格式**：MP3 ↔ WAV

**邏輯驗證方法**：
- 測試案例：MP3 檔案 → 成功轉換為 WAV
- 測試案例：WAV 檔案 → 成功轉換為 MP3

---

## 3. 非功能需求（NFR）

### NFR-01：效能

| 指標 | 目標 |
|------|------|
| TTFB | < 300ms |
| LEXICON 覆蓋率 | ≥ 80%（目標 ≥ 95%） |
| 變調正確率 | ≥ 95% |
| API 可用率 | ≥ 99% |
| 錯誤恢復時間 | < 10s |

### NFR-02：可靠性

- 斷路器保護：後端崩潰不影響整體服務
- 錯誤自動降級：SSML 解析失敗 → fallback 純文字
- 請求超時：30 秒 timeout

### NFR-03：安全性

| 安全面向 | 內容 |
|---------|------|
| 認證（Authentication） | API 金鑰或 JWT token 保護對外端點 |
| 授權（Authorization） | 音色/模型存取權限分級 |
| 加密（Encryption） | HTTPS/TLS 傳輸加密（對外暴露時） |
| 資料保護（Data Protection） | 使用者輸入不寫入日誌，音訊資料不留存 |

### NFR-04：可維護性

- 模組化設計（各 engine 獨立）
- 型別提示完整
- 單元測試覆蓋率 ≥ 80%

---

## 4. 風險矩陣

| ID | 風險 | 影響 | 可能性 | 緩解 |
|----|------|------|--------|------|
| R1 | Kokoro Docker 崩潰 | 高 | 低 | 斷路器 + 錯誤訊息 |
| R2 | 連線中斷 | 中 | 中 | 重試 3 次 + CircuitBreaker |
| R3 | ffmpeg 缺失 | 中 | 低 | 必要依賴聲明 |
| R4 | Redis 無法連線 | 低 | 低 | Optional，無 Redis 時略過 |

---

## 5. 假設與相依性（Dependencies and Constraints）

- Kokoro Docker 運行於 `http://localhost:8880`
- ffmpeg 已安裝（CLI 和音訊轉換用）
- Redis 為可選（無 Redis 時系統正常降級）

**依賴矩陣**：
| 需求 | 依賴項目 | 類型 |
|------|---------|------|
| FR-01~08 | Kokoro Backend URL | 外部服務 |
| FR-04 | httpx 非同步庫 | Python 套件 |
| FR-06 | Redis 服務 | 可選外部服務 |
| FR-07 | ffmpeg | 系統工具 |

---

## 6. 需求追蹤（Traceability）

所有需求皆具備唯一識別符（FR-01 ~ FR-08、NFR-01 ~ NFR-07）。

**模組化架構（Module/Component）**：
- FR-01 ~ FR-03 → `engines/taiwan_linguistic.py`、`engines/ssml_parser.py`、`engines/text_splitter.py`
- FR-04 ~ FR-06 → `engines/synthesis.py`、`middleware/circuit_breaker.py`、`cache/redis_cache.py`
- FR-07 ~ FR-08 → `cli.py`、`audio_converter.py`

**依賴關係（Dependencies）**：
- 核心依賴：`httpx`、`pydub`、`fastapi`
- 平台依賴：`ffmpeg`（音訊轉換）
- 可選依賴：`redis`（快取）

詳細追蹤矩陣見 `SPEC_TRACKING.md` 和 `TRACEABILITY_MATRIX.md`。

---

## 7. 審查狀態

| 項目 | 狀態 |
|------|------|
| 審查狀態 | Phase 1 審查中 |
| 最後更新 | 2026-04-01 |
| Constitution 評分 | 待 Phase 1 CONFIRM |

---

## 8. 需求變更管理

所有需求變更須經過以下審查流程：
1. 變更提出（提出人記錄變更內容與理由）
2. 影響分析（分析對架構、時程、風險的影響）
3. 審查核准（需 Johnny CONFIRM）
4. 重新追蹤（更新 SPEC_TRACKING.md 和 TRACEABILITY_MATRIX.md）

---

## 9. 模型參數建議（Taiwan Persona）

| Persona | 音色配方 | Speed | 應用 |
|---------|---------|-------|------|
| 極致溫柔助理 | `zf_xiaoxiao(0.8)+af_heart(0.2)` | 0.85–0.95 | 睡前故事 |
| 親切智慧導遊 | `zf_xiaoxiao(0.7)+af_sky(0.3)` | 0.9–1.0 | 展場導覽 |
| 現代幹練秘書 | `zf_yunxi(0.8)+af_nicole(0.2)` | 1.0–1.1 | 行事曆提醒 |
| 甜美親和主播 | `zf_xiaoyi(0.6)+zf_xiaoxiao(0.4)` | 1.0–1.1 | 新聞摘要 |

---

## 10. API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/health` | 健康檢查 |
| GET | `/ready` | 就緒檢查 |
| GET | `/v1/proxy/voices` | 音色列表 |
| POST | `/v1/proxy/speech` | 語音合成 |


TEST_MARKER_12345
