# 規格追蹤表 — tts-kokoro-v613

> 版本：v6.13.1  
> 日期：2026-03-31

---

## 功能需求（FR）追蹤

| FR | 描述 | 狀態 | 驗證方法 | 負責 |
|----|------|------|---------|------|
| FR-01 | 台灣中文詞彙映射（≥50詞） | 待實作 | 單元測試 | Phase 3 |
| FR-02 | SSML 解析（含 `<voice>` 標籤） | 待實作 | 單元測試 | Phase 3 |
| FR-03 | 智能文本切分（Chunk ≤250字） | 待實作 | 單元測試 | Phase 3 |
| FR-04 | 並行合成引擎 | 待實作 | 整合測試 | Phase 3 |
| FR-05 | 斷路器（Circuit Breaker） | 待實作 | 單元測試 | Phase 3 |
| FR-06 | Redis 快取（可選） | 待實作 | 單元測試 | Phase 3 |
| FR-07 | CLI 命令列工具（tts-v610） | 待實作 | CLI 測試 | Phase 3 |
| FR-08 | ffmpeg 音訊格式轉換 | 待實作 | CLI 測試 | Phase 3 |

---

## 非功能需求（NFR）追蹤

| NFR | 描述 | 目標值 | 狀態 | 驗證方法 |
|-----|------|--------|------|---------|
| NFR-01 | TTFB | < 300ms | 待驗證 | 效能測試 |
| NFR-02 | LEXICON 覆蓋率 | ≥ 80% | 待驗證 | 單元測試 |
| NFR-03 | 變調正確率 | ≥ 95% | 待驗證 | 單元測試 |
| NFR-04 | API 可用率 | ≥ 99% | 待驗證 | 負載測試 |
| NFR-05 | 錯誤恢復時間 | < 10s | 待驗證 | 故障測試 |
| NFR-06 | 單元測試覆蓋率 | ≥ 80% | 待驗證 | pytest --cov |
| NFR-07 | 斷路器恢復 | < 10s | 待驗證 | 單元測試 |

---

## Phase 1 交付物狀態

| 交付物 | 路徑 | 狀態 | 完成日期 |
|--------|------|------|---------|
| SRS.md | 01-requirements/SRS.md | ✅ 完成 | 2026-03-31 |
| SPEC_TRACKING.md | 01-requirements/SPEC_TRACKING.md | ✅ 完成 | 2026-03-31 |
| TRACEABILITY_MATRIX.md | 01-requirements/TRACEABILITY_MATRIX.md | ✅ 完成 | 2026-03-31 |
| DEVELOPMENT_LOG.md | DEVELOPMENT_LOG.md | ✅ 完成 | 2026-03-31 |


---

## 更新紀錄（Changelog）

| 日期 | 變更內容 | 負責 |
|------|---------|------|
| 2026-03-31 | 初始版本：建立 FR/NFR 追蹤矩陣 | Agent A |
| 2026-04-01 | 對齊 SRS.md：修正 NFR-05/NFR-06/NFR-07 識別符、補充驗證方法 | Agent A |
| 2026-04-01 | Phase 1 交付物對齊：路徑修正至根目錄 | Agent A |

