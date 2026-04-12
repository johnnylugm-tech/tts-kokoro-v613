# 追溯矩陣 — tts-kokoro-v613

> 版本：v6.13.3  
> 日期：2026-04-12（Phase 4 更新）  
> Phase 4 更新：2026-04-12（TEST_PLAN + TEST_RESULTS 完成）  
> 框架遵循：[methodology-v2](https://github.com/johnnylugm-tech/methodology-v2)

---

## 變更記錄

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| v6.13.1 | 2026-03-31 | 初始版本（FR-01 ~ FR-08） |
| v6.13.2 | 2026-04-11 | 加入 FR-09（Kokoro Proxy），更新代碼路徑 |
| v6.13.3 | 2026-04-12 | Phase 4 完成：238 tests PASS，覆蓋率更新為 91% |

---

## FR ↔ 模組 ↔ 測試 對照（Phase 4 最終）

| FR | 功能需求 | 對應模組 | 測試檔案 | Phase 3 | Phase 4 | 測試覆蓋率 |
|----|---------|---------|---------|---------|---------|-----------|
| FR-01 | 台灣中文詞彙映射 | `src/processing/lexicon_mapper.py` | `tests/test_fr01_lexicon_mapper.py` | ✅ | ✅ | **98%** |
| FR-02 | SSML 解析（含 `<voice>`） | `src/processing/ssml_parser.py` | `tests/test_fr02_ssml_parser.py` | ✅ | ✅ | **85%** |
| FR-03 | 智能文本切分（≤250字） | `src/processing/text_chunker.py` | `tests/test_fr03_text_chunker.py` | ✅ | ✅ | **90%** |
| FR-04 | 並行合成引擎 | `src/synth/synth_engine.py` | `tests/test_fr04_synth_engine.py` | ✅ | ✅ | **100%** |
| FR-05 | 斷路器 | `src/synth/circuit_breaker.py` | `tests/test_fr05_circuit_breaker.py` | ✅ | ✅ | **90%** |
| FR-06 | Redis 快取 | `src/cache/redis_cache.py` | `tests/test_fr06_redis_cache.py` | ✅ | ✅ | **95%** |
| FR-07 | CLI 命令列工具 | `src/api/routes.py` | `tests/test_fr07_routes.py` | ✅ | ✅ | **81%** |
| FR-08 | ffmpeg 音訊轉換 | `src/audio/audio_converter.py` | `tests/test_fr08_audio_converter.py` | ✅ | ✅ | **96%** |
| FR-09 | Kokoro Proxy | `src/backend/kokoro_client.py` | `tests/test_fr09_kokoro_client.py` | ✅ | ✅ | **97%** |

**Phase 4 總測試數：238 | 覆蓋率總計：91%**

---

## 測試覆蓋率摘要（Phase 4 最終）

| 模組 | 檔案 | Stmts | Miss | Cover | 測試數 |
|------|------|-------|------|-------|--------|
| api/routes.py | test_fr07_routes.py | 73 | 14 | 81% | 37 |
| audio/audio_converter.py | test_fr08_audio_converter.py | 51 | 2 | 96% | 15 |
| backend/kokoro_client.py | test_fr09_kokoro_client.py | 67 | 2 | 97% | 25 |
| cache/redis_cache.py | test_fr06_redis_cache.py | 56 | 3 | 95% | 25 |
| processing/lexicon_mapper.py | test_fr01_lexicon_mapper.py | 64 | 1 | 98% | 17 |
| processing/ssml_parser.py | test_fr02_ssml_parser.py | 138 | 21 | 85% | 38 |
| processing/text_chunker.py | test_fr03_text_chunker.py | 131 | 13 | 90% | 31 |
| synth/circuit_breaker.py | test_fr05_circuit_breaker.py | 109 | 11 | 90% | 26 |
| synth/synth_engine.py | test_fr04_synth_engine.py | 82 | 0 | 100% | 23 |
| **總計** | — | **776** | **67** | **91%** | **238** |

---

## 雙向追溯鏈

```
FR-01                                                    FR-09
  │                                                         │
  ▼                                                         ▼
SRS.md §2 FR-01                              ...         SRS.md §2 FR-09
  │                                                         │
  ▼                                                         ▼
lexicon_mapper.py                              ...          kokoro_client.py
  │                                                         │
  ▼                                                         ▼
test_fr01_lexicon_mapper.py (17 tests)         ...          test_fr09_kokoro_client.py (25 tests)
  │                                                         │
  └──────────────────────┬─────────────────────────────────┘
                         │
                         ▼
                  Phase 4 TEST_RESULTS
                  (238 tests, 91% coverage, 100% pass)
```

---

## Phase ↔ 交付物 對照

| Phase | 交付物 | 狀態 | 日期 |
|-------|--------|------|------|
| Phase 1 | SRS.md | ✅ 完成 | 2026-03-31 |
| Phase 1 | SPEC_TRACKING.md | ✅ 完成 | 2026-03-31 |
| Phase 1 | TRACEABILITY_MATRIX.md | ✅ 完成 | 2026-04-12（更新） |
| Phase 1 | DEVELOPMENT_LOG.md | ✅ 完成 | 2026-03-31 |
| Phase 1 | Phase1_STAGE_PASS.md | ✅ 完成 | 2026-03-31 |
| Phase 2 | SAD.md | ✅ 完成 | 2026-04-01 |
| Phase 2 | ADR | ✅ 完成 | 2026-04-01 |
| Phase 3 | 代碼實作（FR-01~09） | ✅ 完成 | 2026-04-11 |
| Phase 3 | 單元測試（238 tests） | ✅ 完成 | 2026-04-11 |
| Phase 4 | TEST_PLAN.md | ✅ 完成 | 2026-04-12 |
| Phase 4 | TEST_RESULTS.md | ✅ 完成 | 2026-04-12 |
| Phase 4 | Phase4_STAGE_PASS.md | ✅ 完成 | 2026-04-12 |

---

## NFR ↔ 測試 對照

| NFR | 非功能需求 | 測試方法 | 門檻 | 狀態 |
|-----|-----------|---------|------|------|
| NFR-01 | TTFB < 300ms | 效能計時測試 | < 300ms | 待驗證 |
| NFR-02 | LEXICON 覆蓋率 ≥ 80% | 單元測試 | ≥ 80% | ✅ 已驗證（98%）|
| NFR-03 | 變調正確率 ≥ 95% | 單元測試 | ≥ 95% | ✅ 已驗證 |
| NFR-04 | API 可用率 ≥ 99% | 負載測試 | ≥ 99% | 待驗證 |
| NFR-05 | 錯誤恢復時間 < 10s | 故障注入測試 | < 10s | ✅ 已驗證 |
| NFR-06 | 測試覆蓋率 ≥ 80% | pytest --cov | ≥ 80% | ✅ 已驗證（91%）|
| NFR-07 | 斷路器恢復 < 10s | 單元測試 | < 10s | ✅ 已驗證 |

---

## 連結（Links）

| 交付物 | GitHub 路徑 |
|--------|------------|
| SRS.md | [SRS.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/SRS.md) |
| SPEC_TRACKING.md | [SPEC_TRACKING.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/SPEC_TRACKING.md) |
| TRACEABILITY_MATRIX.md | [TRACEABILITY_MATRIX.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/TRACEABILITY_MATRIX.md) |
| DEVELOPMENT_LOG.md | [DEVELOPMENT_LOG.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/DEVELOPMENT_LOG.md) |
| TEST_PLAN.md | [04-testing/TEST_PLAN.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/04-testing/TEST_PLAN.md) |
| TEST_RESULTS.md | [04-testing/TEST_RESULTS.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/04-testing/TEST_RESULTS.md) |
| Phase4_STAGE_PASS.md | [00-summary/Phase4_STAGE_PASS.md](https://github.com/johnnylugm-tech/tts-kokoro-v613/blob/main/00-summary/Phase4_STAGE_PASS.md) |

---

## 驗證狀態

| 項目 | 狀態 | 說明 |
|------|------|------|
| FR 數量 | ✅ 9/9 | FR-01 ~ FR-09 完整 |
| 代碼映射 | ✅ 9/9 | 每個 FR 都有對應代碼 |
| 測試映射 | ✅ 9/9 | 每個 FR 都有對應測試 |
| 雙向連結 | ✅ 完整 | FR ↔ 代碼 ↔ 測試 可追溯 |
| 測試覆蓋率 | ✅ 91% | 所有 FR ≥ 81%（目標 ≥80%）|
| NFR 追蹤 | ⚠️ 部分 | NFR-01/04 待驗證，其餘已達標 |
