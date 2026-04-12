# TEST_PLAN.md — tts-kokoro-v613 測試計劃

> 版本：v1.0  
> 角色：Agent A（QA）  
> 依據：SRS.md v6.13.1 + SAD.md v6.13.2  
> 日期：2026-04-12  
> 框架：[methodology-v2](https://github.com/johnnylugm-tech/methodology-v2)

---

## 1. 測試目標與範圍

### 1.1 測試目標

- **正確性**：每個 FR 的實作滿足 SRS 需求與 SAD 介面定義
- **驗收完整性**：每個 FR 具備 ≥ 1 個 TC；P0 需求（FR-01 ~ FR-03）具備正向、邊界、負面三類 TC
- **覆蓋率**：單元測試覆蓋率 ≥ 80%（NFR-06），CI 強制執行
- **可重現性**：所有測試可在隔離環境中執行，不依賴真實 Kokoro 後端（Mock）

### 1.2 測試範圍

| 納入 | 排除 |
|------|------|
| FR-01 ~ FR-09 所有功能需求 | Kokoro Docker 內部實作 |
| L1 ~ L4 錯誤處理邏輯 | CI/CD 管線設定 |
| CLI 工具（FR-07） | 基礎設施配置（Docker Compose 等） |
| ffmpeg 音訊轉換（FR-08） | 效能壓力測試（歸入 NFR-01 单独測試） |
| 斷路器邏輯（FR-05） | 安全性滲透測試 |
| Redis 快取降級（FR-06） | |

### 1.3 測試環境

```
測試框架：pytest + pytest-asyncio
Mock 策略：unittest.mock + respx（HTTP Mock）
音訊 Mock：io.BytesIO + wave（非真實檔案）
外部依賴 Mock：
  - Kokoro 後端 → respx mock HTTP 響應
  - Redis → fakeredis 或自訂 AsyncMock
  - ffmpeg → shutil.which mock + subprocess mock
```

---

## 2. 測試策略與環境

### 2.1 分層測試策略

```
Layer 1（API）      → 整合測試：FastAPI TestClient
Layer 2（Orchestrator）→ 單元測試：mock 所有下層
Layer 3（Processing）→ 單元測試：pure functions，無 I/O
Layer 4（Backend）  → 單元測試：respx mock HTTP
Layer 5（Infrastructure）→ 單元測試 + 子程序 Mock
```

### 2.2 Mock 策略矩陣

| 模組 | Mock 目標 | Mock 方式 | 理由 |
|------|-----------|-----------|------|
| `KokoroClient` | `httpx.AsyncClient` | `respx` | 避免真實 HTTP 呼叫 |
| `RedisCache` | `redis.asyncio` 連線 | `fakeredis.aioredis.FakeRedis` | 隔離 Redis 依賴 |
| `AudioConverter` | `shutil.which` + `subprocess` | `unittest.mock` | 避免呼叫真實 ffmpeg |
| `CircuitBreaker` | 時間流逝 | `freezegun` 或 monkeypatch | 測試狀態機轉換 |
| `SSMLParser` | XML 解析 | 直接餵字串，無 Mock | 測試解析邏輯本身 |
| `LexiconMapper` | 詞彙檔 | fixture JSON，無 Mock | 測試映射邏輯本身 |

### 2.3 測試資料策略

- **SSML 測試資料**：嵌入 fixture，覆蓋所有標籤組合
- **Lexicon 測試資料**：`conftest.py` 提供 50+ 詞測試詞彙表（JSON fixture）
- **音訊 Mock**：使用 `io.BytesIO` + 有效 MP3/WAV header，避免產生真實檔案

### 2.4 測試隔離原則

- 每個測試檔案對應一個 FR（`test_fr0X_*.py`）
- 測試不得依賴執行順序（`pytest-randomly` 或明确 `@pytest.mark.order`）
- `conftest.py` 提供共享 fixtures（`lexicon_json`, `mock_kokoro`, `mock_redis`）

---

## 3. TC 清單（測試案例）

### P0 需求：FR-01 ~ FR-03（正向 + 邊界 + 負面）

---

#### FR-01：台灣中文詞彙映射

**驗收標準**：詞彙映射 ≥ 50 詞（覆蓋率目標 ≥ 95%）；LEXICON 總詞彙數 ≥ 50

| TC 類別 | TC ID | 輸入 | 預期輸出 | 驗證方法 |
|---------|-------|------|----------|---------|
| 正向 | TC-01-01 | `"我要坐地鐵去看視頻"` | `"我要坐捷運去看影片"` | `LexiconMapper.apply()` 回傳值 == 預期 |
| 正向 | TC-01-02 | `"菠蘿麵包很好吃"` | `"鳳梨麵包很好吃"` | 同上 |
| 正向 | TC-01-03 | `"他是程序員"` | `"他是工程師"` | 同上 |
| 正向 | TC-01-04 | `"軟件開發"` | `"軟體開發"` | 同上 |
| 正向 | TC-01-05 | `"和是連接詞"`（和→ㄏㄢˋ） | 依詞彙表映射 | 驗證多音字映射 |
| 正向 | TC-01-06 | `"今天吃吧！" `（吧→啦） | `"今天吃啦！"` | 驗證語氣詞映射 |
| 邊界 | TC-01-07 | `""`（空字串） | `""`（不當機） | 異常處理驗證 |
| 邊界 | TC-01-08 | 未映射的普通文句 | 原樣回傳（無變化） | 確認不映射不存在詞 |
| 邊界 | TC-01-09 | 長文句（500+ 字）含多個映射詞 | 每個詞正確映射 | 確認長文字處理 |
| 負面 | TC-01-10 | 詞彙表載入失敗（檔案不存在） | 拋出 `FileNotFoundError` 或 `LexiconLoadError`（L1） | 確認錯誤類型 |
| 負面 | TC-01-11 | 非 UTF-8 編碼的詞彙表 | 優雅處理，不當機 | 確認編碼錯誤處理 |
| 覆蓋率驗證 | TC-01-12 | `get_coverage_stats()` | 回傳 `{"total": ≥50, "covered": ..., "coverage_pct": ≥80}` | NFR-02 覆蓋率 ≥ 80% |

---

#### FR-02：SSML 解析（含 `<voice>` 標籤）

**驗收標準**：支援 `<speak>`, `<break>`, `<prosody>`, `<emphasis>`, `<voice>`, `<phoneme>`；XML 解析失敗時 fallback 純文字

| TC 類別 | TC ID | 輸入 | 預期輸出 | 驗證方法 |
|---------|-------|------|----------|---------|
| 正向 | TC-02-01 | `<prosody rate="0.9">文字</prosody>` | `prosody={"rate": "0.9"}` | 檢查 `SSMLSegment.prosody` |
| 正向 | TC-02-02 | `<voice name="zf_yunxi">內容</voice>` | `voice_name="zf_yunxi"` | 檢查 `SSMLSegment.voice_name` |
| 正向 | TC-02-03 | `<break time="500ms"/>` | `break_ms=500` | 檢查 `SSMLSegment.break_ms` |
| 正向 | TC-02-04 | `<emphasis level="strong">文字</emphasis>` | `emphasis_level="strong"` | 檢查 `SSMLSegment.emphasis_level` |
| 正向 | TC-02-05 | `<phoneme alphabet="ipa" ph="əʊ">文字</phoneme>` | `phoneme_alphabet="ipa"`, `phoneme_ph="əʊ"` | 檢查 `SSMLSegment.phoneme_*` |
| 正向 | TC-02-06 | 巢狀標籤：`<voice name="A"><prosody rate="0.8">文字</prosody></voice>` | voice_name + prosody 同時存在 | 檢查 segment 屬性組合 |
| 正向 | TC-02-07 | 無根標籤的純文字（自動包裝 `<speak>`） | 解析為一個 `TEXT` segment | `parse()` 不拋異常 |
| 邊界 | TC-02-08 | `<prosody rate="2.5">`（超範圍 0.25~4.0 之外） | 不當機，保留原值或截斷 | 驗證超界值處理 |
| 邊界 | TC-02-09 | 巨大 SSML 輸入（10000+ 字） | 不當機，逐步解析 | 確認記憶體處理 |
| 負面 | TC-02-10 | 無效 XML：`</speak>` 缺少closing tag | 拋出 `SSMLParseError`（L1） | 確認錯誤類型為 L1 |
| 負面 | TC-02-11 | SSML 解析失敗時（invalid tag） | fallback 純文字，不拋異常 | 確認 L1 fallback 行為 |
| 負面 | TC-02-12 | `<speak>` 嵌套不合法（`</speak>` 過早關閉） | 拋出 `SSMLParseError` | L1 錯誤處理 |

---

#### FR-03：智能文本切分（Chunk ≤ 250 字）

**驗收標準**：每段 ≤ 250 字；三級遞迴（L1: 句，L2: 子句，L3: 片語）；不在中英文混合字中間切斷

| TC 類別 | TC ID | 輸入 | 預期輸出 | 驗證方法 |
|---------|-------|------|----------|---------|
| 正向 | TC-03-01 | 500 字長文句（無標點） | 多 chunk，每個 ≤ 250 字 | `TextChunker.chunk()` + 長度斷言 |
| 正向 | TC-03-02 | 含 `。？！` 的文句 | 每句一個 chunk | 確認 L1 切分 |
| 正向 | TC-03-03 | 含 `，。；：` 的長文句（>100 字） | 子句切分（L2） | 確認 L2 切分 |
| 正向 | TC-03-04 | 含 `，的了吧呢啊` 的長文句（>100 字） | 片語切分（L3） | 確認 L3 切分 |
| 正向 | TC-03-05 | 中英文混合：`AI是Artificial Intelligence的縮寫` | 不在 `A`/`I` 中間切斷 | 確認 mixed script 保護 |
| 正向 | TC-03-06 | 全部英文（無中文）長文句 | 依 L3 片語邊界切分 | 確認英文處理 |
| 邊界 | TC-03-07 | 249 字文句（最大臨界） | 保持為 1 個 chunk | 驗證上限不切分 |
| 邊界 | TC-03-08 | 250 字文句 | 保持為 1 個 chunk | 驗證上限不切分 |
| 邊界 | TC-03-09 | 251 字文句 | 切成 2 個 chunk | 驗證超限才切 |
| 邊界 | TC-03-10 | 空白字串 | 回傳空 list | 確認空輸入處理 |
| 負面 | TC-03-11 | 含多 byte 字元（日文/ Emoji） | 正確計算字元數（非 byte 數） | 確認 Unicode 處理 |
| 負面 | TC-03-12 | 極長文句（10000+ 字，無任何邊界） | 每 250 字一個 chunk | 確認硬分割（hard split） |
| 負面 | TC-03-13 | 只有數字和英文字母（無任何 NLP 邊界） | 依 `MAX_CHUNK_SIZE` 硬切 | 確認無 NLP 線索時的 fallback |

---

### 其他 FR（FR-04 ~ FR-09）：正向 + 關鍵邊界

#### FR-04：並行合成引擎

| TC ID | 描述 | 驗證方法 |
|-------|------|---------|
| TC-04-01 | 5 個 Chunk 同時請求，總時間 < 各 Chunk 順序執行時間 | `asyncio.gather` 並行，`time.perf_counter()` 量測 |
| TC-04-02 | 拼接後 MP3 可正常播放（有效 MP3 header） | `mp3info` 或 `pydub.AudioSegment.from_mp3()` |
| TC-04-03 | 部分 Chunk 失敗 → `SynthesisPartialError` 含 `partial_results` + `failed_indices` | Mock KokoroClient 部分失敗 |
| TC-04-04 | 全部 Chunk 失敗 → `SynthesisUnavailableError` | Mock 全部 5xx |
| TC-04-05 | 併發度上限（max_concurrency=10）驗證 | 確認不超過設定值 |

#### FR-05：斷路器（Circuit Breaker）

| TC ID | 描述 | 驗證方法 |
|-------|------|---------|
| TC-05-01 | 連續 3 次 5xx → 狀態變為 OPEN | 注入 3 次失敗，檢查 `state == CircuitState.OPEN` |
| TC-05-02 | OPEN 後請求 → 立即拋出 `CircuitBreakerOpenError`（不回後端） | Mock + assert 未發 HTTP |
| TC-05-03 | OPEN 後 10 秒 → 狀態變為 HALF_OPEN | `freezegun` 或 monkeypatch time |
| TC-05-04 | HALF_OPEN probe 成功 → CLOSED | 注入成功，檢查 `state == CircuitState.CLOSED` |
| TC-05-05 | HALF_OPEN probe 失敗 → 回到 OPEN | 注入 1 次失敗，檢查恢復到 OPEN |
| TC-05-06 | 4xx 錯誤（`ClientSideError`）不計入失敗計數 | 注入 4xx，確認 failure_count 不增加 |
| TC-05-07 | `get_metrics()` 回傳正確的狀態/計數 | assert metrics dict 含正確欄位 |

#### FR-06：Redis 快取

| TC ID | 描述 | 驗證方法 |
|-------|------|---------|
| TC-06-01 | 相同請求第二次 → 直接回傳快取（無後端請求） | Mock Redis，`assert` 後端未被呼叫 |
| TC-06-02 | 快取 Key = SHA-256(text + voice + speed) | 驗證 Key 格式（Redis key 前綴 `tts:`） |
| TC-06-03 | TTL = 24 小時（86400 秒） | 驗證 Redis SET 時使用正確 TTL |
| TC-06-04 | Redis 不可用時 → 正常降級至直接合成 | Mock Redis 連線失敗，確認不回 5xx |
| TC-06-05 | `make_key()` 不同輸入產生不同 Key | 確認一字之差 Key 不同 |
| TC-06-06 | 快取未命中 → 正常流程（後端合成） | Mock miss，確認後端被呼叫 |

#### FR-07：CLI 命令列工具

| TC ID | 描述 | 驗證方法 |
|-------|------|---------|
| TC-07-01 | `tts-v610 --help` → 顯示完整說明 | `subprocess.run` + stdout 檢查 |
| TC-07-02 | 輸入文字 → 產出 MP3 檔案（名稱符合 `-o`） | 整合測試（需要 Mock HTTP） |
| TC-07-03 | `--ssml` + SSML 字串 → SSML 解析後合成 | 確認 SSML 標籤被正確傳遞 |
| TC-07-04 | `-s 0.5`（最小速度）→ 不當機 | 確認速度參數傳遞到底層 |
| TC-07-05 | `-s 4.0`（最大速度）→ 不當機 | 同上 |
| TC-07-06 | `--format wav` → 輸出 WAV 而非 MP3 | 確認格式轉換被觸發 |
| TC-07-07 | `-i input.txt` → 讀取檔案內容作為輸入 | 確認檔案輸入模式 |
| TC-07-08 | 缺少必要參數（無 `-i` 或 `-o`）→ 顯示錯誤訊息 | CLI 錯誤處理驗證 |

#### FR-08：ffmpeg 音訊格式轉換

| TC ID | 描述 | 驗證方法 |
|-------|------|---------|
| TC-08-01 | MP3 → WAV 轉換成功 | Mock ffmpeg subprocess，驗證輸出 WAV header |
| TC-08-02 | WAV → MP3 轉換成功 | Mock ffmpeg subprocess，驗證輸出 MP3 header |
| TC-08-03 | ffmpeg 不存在 → 拋出 `AudioConverterNotFoundError`（L2） | Mock `shutil.which` 回 None |
| TC-08-04 | ffmpeg 執行失敗 → `AudioConverterError`（L2）+ 重試 3 次 | Mock subprocess returncode != 0 |
| TC-08-05 | 無效音訊資料（損壞 MP3）→ 拋出 `AudioConverterError`（L2） | 確認錯誤傳播 |

#### FR-09：Kokoro Proxy

| TC ID | 描述 | 驗證方法 |
|-------|------|---------|
| TC-09-01 | `speech("你好", "zf_xiaoxiao", 1.0)` → 回傳 MP3 bytes | respx mock + assert 回傳類型 |
| TC-09-02 | `voices()` → 回傳可用音色列表（dict list） | respx mock + assert 回傳結構 |
| TC-09-03 | 後端 5xx → 拋出 `KokoroServerError`（L4） | respx 注入 500 |
| TC-09-04 | 後端 4xx → 拋出 `KokoroClientError`（L4，不計入 CB） | respx 注入 400 |
| TC-09-05 | 連線逾時 → 拋出 `KokoroTimeoutError`（L4） | respx mock timeout |
| TC-09-06 | 連線失敗（DNS/Connection refused）→ `KokoroConnectionError`（L4） | respx mock connection error |
| TC-09-07 | `health_check()` → 後端正常時回 True | respx mock 200 |
| TC-09-08 | `close()` → 正確釋放 httpx client | 確認 `aclose()` 被呼叫 |

---

## 4. 風險評估

| 風險 ID | 風險描述 | 可能性 | 影響 | 緩解策略 | Mock 對應 |
|---------|---------|--------|------|---------|---------|
| R-CB-01 | `CircuitBreaker` 狀態機時序錯誤（OPEN/HALF_OPEN） | 中 | 高 | `freezegun` freeze 時間，單獨測試狀態轉換 | `time.monotonic()` mock |
| R-CB-02 | 非同步鎖竞争导致测试 flaky | 低 | 中 | 使用 `pytest.mark.asyncio` + 明確的 lock 釋放順序 | `asyncio.Lock` mock |
| R-REDIS-01 | `fakeredis` 與真實 Redis 行為不一致（e.g., SHA256 pipeline） | 低 | 中 | 僅 Mock 介面層，核心邏輯用實際 `redis.asyncio` client 測試 | `fakeredis.aioredis` |
| R-FFMPEG-01 | subprocess mock 覆蓋不足（ffmpeg 參數錯誤） | 中 | 中 | 驗證 subprocess.call 的完整 args list | `unittest.mock` patch subprocess |
| R-HTTP-01 | respx 版本差異導致 mock 失效 | 低 | 高 | 在 conftest.py 固定 respx 版本，CI 安裝時校園 | respx version pin |
| R-ASYNC-01 | `SynthEngine.synthesize_chunks` 併發測試不稳定 | 中 | 中 | 使用 `asyncio.Semaphore` 控制併發，固定 max_concurrency=3 測試 | `asyncio.gather` 控制 |
| R-LEX-01 | 詞彙表路徑依賴 `__file__` 在測試環境失效 | 中 | 中 | `conftest.py` 提供明確路徑 fixture，不依賴相對路徑 | `Path` fixture |
| R-SSML-01 | XML 解析注入攻擊（XXE） | 低 | 高 | SAD 要求使用 `defusedxml`，確認 SSML parser 介面不使用外部實體 | N/A — 安全測試 |

### Mock 等級對照

| 等級 | 需要 Mock | 理由 |
|------|-----------|------|
| L1（輸入驗證） | 否 | 只需正確資料 + 錯誤資料，不需要 Mock |
| L2（工具錯誤） | ffmpeg subprocess Mock | 隔離系統工具依賴 |
| L3（執行錯誤） | Redis Mock | 避免真實 Redis，測試降級路徑 |
| L4（系統錯誤） | HTTP Mock（respx） | 避免真實後端，依賴隔離 |

---

## 5. FR ↔ TC 映射表

| FR ID | FR 描述 | TC 數量 | TC IDs |
|--------|---------|--------|--------|
| FR-01 | 台灣中文詞彙映射 | **12** | TC-01-01 ~ TC-01-12 |
| FR-02 | SSML 解析（含 `<voice>` 標籤） | **12** | TC-02-01 ~ TC-02-12 |
| FR-03 | 智能文本切分（Chunk ≤ 250 字） | **13** | TC-03-01 ~ TC-03-13 |
| FR-04 | 併行合成引擎 | **5** | TC-04-01 ~ TC-04-05 |
| FR-05 | 斷路器（Circuit Breaker） | **7** | TC-05-01 ~ TC-05-07 |
| FR-06 | Redis 快取（可選） | **6** | TC-06-01 ~ TC-06-06 |
| FR-07 | CLI 命令列工具 | **8** | TC-07-01 ~ TC-07-08 |
| FR-08 | ffmpeg 音訊格式轉換 | **5** | TC-08-01 ~ TC-08-05 |
| FR-09 | Kokoro Proxy | **8** | TC-09-01 ~ TC-09-08 |
| **合計** | | **76** | |

### P0 需求覆蓋（FR-01 ~ FR-03）

| FR | 正向 TC | 邊界 TC | 負面 TC | 總計 |
|----|---------|---------|---------|------|
| FR-01 | 6 | 3 | 3 | 12 |
| FR-02 | 7 | 2 | 3 | 12 |
| FR-03 | 6 | 4 | 3 | 13 |
| **小計** | **19** | **9** | **9** | **37** |

---

## 6. 測試資料 Fixture 清單

| Fixture 名稱 | 檔案位置 | 用途 |
|-------------|---------|------|
| `lexicon_tw_minimal.json` | `tests/fixtures/lexicon_minimal.json` | 10 詞子集，快速單元測試 |
| `lexicon_tw_full.json` | `tests/fixtures/lexicon_full.json` | 50+ 詞完整詞彙表，覆蓋率測試 |
| `ssml_samples.json` | `tests/fixtures/ssml_samples.json` | 所有標籤組合的 SSML 字串 |
| `mock_kokoro_responses.json` | `tests/fixtures/mock_kokoro.json` | HTTP mock 資料（MP3 bytes base64） |
| `audio_samples/` | `tests/fixtures/audio/` | 有效 MP3/WAV 樣本（small, for format test） |

---

## 7. 執行方式

### 7.1 本地執行

```bash
cd /Users/johnny/.openclaw/workspace/tts-kokoro-v613
pip install -r 03-development/requirements.txt

# 單元測試（無 Mock 外的外部依賴）
pytest 03-development/tests/ -v --tb=short

# 覆蓋率報告
pytest 03-development/tests/ --cov=03-development/src/ --cov-report=html --cov-fail-under=80
```

### 7.2 CI 整合

```bash
# Constitution quality gate（測試通過率 + 覆蓋率門檻）
python3 quality_gate/constitution/runner.py --type sad

# Phase verify
python3 cli.py phase-verify --phase 3
```

---

*本文件由 Agent A（QA）從 SRS.md + SAD.md 推導，不涉及 Phase 3 代碼。*
*若需求變更（FR/NFR），請更新此文件並重新執行 A/B Review。*