# 追溯矩陣 — tts-kokoro-v613

> 版本：v6.14.0  
> 日期：2026-04-14

---

## FR ↔ 模組 對照

| FR | 功能需求 | 對應模組 | 驗證方法 | 狀態 |
|----|---------|---------|---------|------|
| FR-01 | 台灣中文詞彙映射 | `engines/taiwan_linguistic.py` | 單元測試 | ✅ 完成 |
| FR-02 | SSML 解析（含 `<voice>`） | `engines/ssml_parser.py` | 單元測試 | ✅ 完成 |
| FR-03 | 智能文本切分（≤250字） | `engines/text_splitter.py` | 單元測試 | ✅ 完成 |
| FR-04 | 並行合成引擎 | `engines/synthesis.py` | 整合測試 | ✅ 完成 |
| FR-05 | 斷路器 | `middleware/circuit_breaker.py` | 單元測試 | ✅ 完成 |
| FR-06 | Redis 快取 | `cache/redis_cache.py` | 單元測試 | ✅ 完成 |
| FR-07 | CLI 命令列工具 | `cli.py` | CLI 測試 | ✅ 完成 |
| FR-08 | ffmpeg 音訊轉換 | `audio_converter.py` | CLI 測試 | ✅ 完成 |
| FR-09 | Kokoro API 整合 | `clients/kokoro_client.py` | 單元測試 | ✅ 完成 |

---

## NFR ↔ 測試 對照

| NFR | 非功能需求 | 測試方法 | 門檻 | 狀態 |
|-----|-----------|---------|------|------|
| NFR-01 | TTFB < 300ms | 效能計時測試 | < 300ms | ✅ 完成 |
| NFR-02 | LEXICON 覆蓋率 ≥ 80% | 單元測試 | ≥ 80% | ✅ 完成 |
| NFR-03 | 變調正確率 ≥ 95% | 單元測試 | ≥ 95% | ✅ 完成 |
| NFR-04 | API 可用率 ≥ 99% | 負載測試 | ≥ 99% | ✅ 完成 |
| NFR-05 | 錯誤恢復時間 < 10s | 故障注入測試 | < 10s | ✅ 完成 |
| NFR-06 | 單元測試覆蓋率 ≥ 80% | pytest --cov | ≥ 80% | ✅ 完成（91%）|
| NFR-07 | 斷路器恢復 < 10s | 單元測試 | < 10s | ✅ 完成 |

---

## Phase ↔ 交付物 對照

| Phase | 交付物 | 狀態 | 確認日期 |
|-------|--------|------|---------|
| Phase 1 | SRS.md | ✅ 完成 | 2026-03-31 |
| Phase 1 | SPEC_TRACKING.md | ✅ 完成 | 2026-03-31 |
| Phase 1 | TRACEABILITY_MATRIX.md | ✅ 完成 | 2026-04-14 |
| Phase 1 | DEVELOPMENT_LOG.md | ✅ 完成 | 2026-03-31 |
| Phase 2 | SAD.md | ✅ 完成 | 2026-04-01 |
| Phase 2 | ADR | ✅ 完成 | 2026-04-01 |
| Phase 3 | 代碼實作（FR-01~FR-09） | ✅ 完成 | 2026-04-10 |
| Phase 3 | 單元測試 | ✅ 完成 | 2026-04-10 |
| Phase 4 | TEST_PLAN.md | ✅ 完成 | 2026-04-11 |
| Phase 4 | TEST_RESULTS.md | ✅ 完成 | 2026-04-11 |
| Phase 5 | BASELINE.md | ✅ 完成 | 2026-04-12 |
| Phase 5 | VERIFICATION_REPORT.md | ✅ 完成 | 2026-04-12 |
| Phase 5 | QUALITY_REPORT.md | ✅ 完成 | 2026-04-14 |
| Phase 6 | MONITORING_PLAN.md | ✅ 完成 | 2026-04-14 |

---

*最後更新：2026-04-14*
