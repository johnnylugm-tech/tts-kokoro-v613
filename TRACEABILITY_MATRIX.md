# 追溯矩陣 — tts-kokoro-v613

> 版本：v6.13.2  
> 日期：2026-04-11  
> Phase 1 更新：2026-04-11（加入 FR-09）  
> 框架遵循：[methodology-v2](https://github.com/johnnylugm-tech/methodology-v2)

---

## 變更記錄

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| v6.13.1 | 2026-03-31 | 初始版本（FR-01 ~ FR-08） |
| v6.13.2 | 2026-04-11 | 加入 FR-09（Kokoro Proxy），更新代碼路徑 |

---

## FR ↔ 模組 ↔ 測試 對照

| FR | 功能需求 | 對應模組 | 測試檔案 | Phase 1 | 測試覆蓋率 |
|----|---------|---------|---------|---------|-----------|
| FR-01 | 台灣中文詞彙映射 | `src/processing/lexicon_mapper.py` | `tests/test_fr01_lexicon_mapper.py` | ✅ | 85% |
| FR-02 | SSML 解析（含 `<voice>`） | `src/processing/ssml_parser.py` | `tests/test_fr02_ssml_parser.py` | ✅ | 82% |
| FR-03 | 智能文本切分（≤250字） | `src/processing/text_chunker.py` | `tests/test_fr03_text_chunker.py` | ✅ | 88% |
| FR-04 | 並行合成引擎 | `src/synth/synth_engine.py` | `tests/test_fr04_synth_engine.py` | ✅ | 78% |
| FR-05 | 斷路器 | `src/synth/circuit_breaker.py` | `tests/test_fr05_circuit_breaker.py` | ✅ | 90% |
| FR-06 | Redis 快取 | `src/cache/redis_cache.py` | `tests/test_fr06_redis_cache.py` | ✅ | 80% |
| FR-07 | CLI 命令列工具 | `src/api/routes.py` | `tests/test_fr07_routes.py` | ✅ | 75% |
| FR-08 | ffmpeg 音訊轉換 | `src/audio/audio_converter.py` | `tests/test_fr08_audio_converter.py` | ✅ | 72% |
| FR-09 | Kokoro Proxy | `src/backend/kokoro_client.py` | `tests/test_fr09_kokoro_client.py` | ✅ | 70% |

---

## 代碼結構 ↔ FR 對照

### `src/processing/` — 文本處理引擎

| 檔案 | FR | 職責 |
|------|-----|------|
| `lexicon_mapper.py` | FR-01 | 台灣中文詞彙映射（50+ 詞） |
| `ssml_parser.py` | FR-02 | SSML 標籤解析 |
| `text_chunker.py` | FR-03 | 智能文本切分（三級遞迴） |

### `src/synth/` — 合成引擎

| 檔案 | FR | 職責 |
|------|-----|------|
| `synth_engine.py` | FR-04 | 並行非同步合成引擎 |
| `circuit_breaker.py` | FR-05 | 斷路器保護（3次失敗/Open/10秒） |

### `src/cache/` — 快取層

| 檔案 | FR | 職責 |
|------|-----|------|
| `redis_cache.py` | FR-06 | Redis 快取（24h TTL，可選） |

### `src/api/` — API 端點

| 檔案 | FR | 職責 |
|------|-----|------|
| `routes.py` | FR-07 | FastAPI 路由（health/voices/speech） |

### `src/audio/` — 音訊處理

| 檔案 | FR | 職責 |
|------|-----|------|
| `audio_converter.py` | FR-08 | ffmpeg 格式轉換（MP3↔WAV） |

### `src/backend/` — 後端整合

| 檔案 | FR | 職責 |
|------|-----|------|
| `kokoro_client.py` | FR-09 | Kokoro TTS API 代理 |

---

## 雙向追溯鏈

```
FR-01                    FR-09
  │                        │
  ▼                        ▼
SRS.md §2 FR-01    ...    SRS.md §2 FR-09
  │                        │
  ▼                        ▼
lexicon_mapper.py   ...    kokoro_client.py
  │                        │
  ▼                        ▼
test_fr01_*.py      ...    test_fr09_*.py
  │                        │
  └──────────┬─────────────┘
             │
             ▼
      Quality Gate
      (Phase 3)
```

---

## NFR ↔ 測試 對照

| NFR | 非功能需求 | 測試方法 | 門檻 | 狀態 |
|-----|-----------|---------|------|------|
| NFR-01 | TTFB < 300ms | 效能計時測試 | < 300ms | 待驗證 |
| NFR-01 | LEXICON 覆蓋率 ≥ 80% | 單元測試 | ≥ 80% | ✅ 已驗證 |
| NFR-01 | 變調正確率 ≥ 95% | 單元測試 | ≥ 95% | ✅ 已驗證 |
| NFR-01 | API 可用率 ≥ 99% | 負載測試 | ≥ 99% | 待驗證 |
| NFR-01 | 錯誤恢復時間 < 10s | 故障注入測試 | < 10s | ✅ 已驗證 |
| NFR-02 | 斷路器保護 | 單元測試 | 3次/Open/10秒 | ✅ 已驗證 |
| NFR-02 | SSML fallback | 單元測試 | fallback | ✅ 已驗證 |
| NFR-02 | 請求超時 30s | 單元測試 | 30s timeout | ✅ 已驗證 |
| NFR-03 | 安全性（Auth/JWT） | — | — | ⚠️ 待實作 |
| NFR-04 | 測試覆蓋率 ≥ 80% | pytest --cov | ≥ 80% | 🔄 80% |

---

## Phase ↔ 交付物 對照

| Phase | 交付物 | 狀態 | 日期 |
|-------|--------|------|------|
| Phase 1 | SRS.md | ✅ 完成 | 2026-03-31 |
| Phase 1 | SPEC_TRACKING.md | ✅ 完成 | 2026-03-31 |
| Phase 1 | TRACEABILITY_MATRIX.md | ✅ 完成 | 2026-04-11（更新） |
| Phase 1 | requirement_mapping.json | ✅ 新增 | 2026-04-11 |
| Phase 1 | spec_mapping.json | ✅ 新增 | 2026-04-11 |
| Phase 1 | DEVELOPMENT_LOG.md | ✅ 完成 | 2026-03-31 |
| Phase 1 | Phase1_STAGE_PASS.md | ✅ 完成 | 2026-03-31 |
| Phase 2 | SAD.md | ✅ 完成 | 2026-04-01 |
| Phase 2 | ADR | ✅ 完成 | 2026-04-01 |
| Phase 3 | 代碼實作 | ✅ 完成 | 2026-04-11 |
| Phase 3 | 單元測試 | ✅ 完成 | 2026-04-11 |
| Phase 4 | TEST_PLAN.md | 待實作 | — |
| Phase 4 | TEST_RESULTS.md | 待實作 | — |

---

## 測試覆蓋率摘要

| FR | 測試檔案 | 覆蓋率 | 狀態 |
|----|---------|--------|------|
| FR-01 | test_fr01_lexicon_mapper.py | 85% | ✅ |
| FR-02 | test_fr02_ssml_parser.py | 82% | ✅ |
| FR-03 | test_fr03_text_chunker.py | 88% | ✅ |
| FR-04 | test_fr04_synth_engine.py | 78% | ✅ |
| FR-05 | test_fr05_circuit_breaker.py | 90% | ✅ |
| FR-06 | test_fr06_redis_cache.py | 80% | ✅ |
| FR-07 | test_fr07_routes.py | 75% | ✅ |
| FR-08 | test_fr08_audio_converter.py | 72% | ✅ |
| FR-09 | test_fr09_kokoro_client.py | 70% | ✅ |
| **平均** | — | **80%** | ✅ |

---

## 連結（Links）

| 交付物 | GitHub 路徑 |
|--------|------------|
| SRS.md | [SRS.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/SRS.md) |
| SPEC_TRACKING.md | [SPEC_TRACKING.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/SPEC_TRACKING.md) |
| TRACEABILITY_MATRIX.md | [TRACEABILITY_MATRIX.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/TRACEABILITY_MATRIX.md) |
| requirement_mapping.json | [requirement_mapping.json](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/requirement_mapping.json) |
| spec_mapping.json | [spec_mapping.json](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/spec_mapping.json) |
| DEVELOPMENT_LOG.md | [DEVELOPMENT_LOG.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/DEVELOPMENT_LOG.md) |
| Phase1_STAGE_PASS.md | [00-summary/Phase1_STAGE_PASS.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/00-summary/Phase1_STAGE_PASS.md) |

---

## 驗證狀態

| 項目 | 狀態 | 說明 |
|------|------|------|
| FR 數量 | ✅ 9/9 | FR-01 ~ FR-09 完整 |
| 代碼映射 | ✅ 9/9 | 每個 FR 都有對應代碼 |
| 測試映射 | ✅ 9/9 | 每個 FR 都有對應測試 |
| 雙向連結 | ✅ 完整 | FR ↔ 代碼 ↔ 測試 可追溯 |
| 測試覆蓋率 | ✅ 平均 80% | 所有 FR ≥ 70% |
| NFR 追蹤 | ⚠️ 部分 | NFR-03/04 待實作 |
