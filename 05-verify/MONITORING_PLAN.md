# MONITORING_PLAN.md — Phase 5 監控計畫

> 版本：v1.0  
> 日期：2026-04-12  
> 依據：Phase 4 TEST_RESULTS.md、SRS.md（NFR-01~NFR-06）  
> 角色：Agent A（DevOps）

---

## 1. 監控指標

### 1.1 效能指標（NFR-01）

| 指標 | 描述 | 目標值 | 測量方式 |
|------|------|--------|---------|
| TTFB（Time To First Byte） | 首次回應時間 | < 500ms | 生產環境 HTTP 日誌 |
| 合成耗時（per chunk） | 每個 Chunk 合成時間 | < 200ms | 生產環境 metrics |
| 併發度上限 | 最大並行合成數 | ≤ 10（可配置） | SynthEngine 計數 |
| 系統總延遲（P95） | 95th percentile 總延遲 | < 2s | APM / 日誌分析 |

### 1.2 錯誤率指標（NFR-01）

| 指標 | 描述 | 目標值 | 測量方式 |
|------|------|--------|---------|
| HTTP 5xx 錯誤率 | Kokoro 後端錯誤 | < 1% | API Gateway 日誌 |
| HTTP 4xx 錯誤率 | 客戶端錯誤 | < 5% | API Gateway 日誌 |
| L4 錯誤（KokoroClient） | 網路/超時錯誤 | < 2% | KokoroClient metrics |
| L2 錯誤（AudioConverter） | ffmpeg 轉換失敗 | < 0.1% | AudioConverter 日誌 |

### 1.3 熔斷器指標（FR-05）

| 指標 | 描述 | 正常行為 | 異常行為 |
|------|------|---------|---------|
| CircuitBreaker 狀態 | OPEN / CLOSED / HALF_OPEN | 多數時間 CLOSED | OPEN 率 > 10% |
| 熔斷觸發次數 | 每小時 OPEN 次數 | < 5 次/hr | > 5 次/hr → 報警 |
| HALF_OPEN probe 成功率 | 半開探測成功率 | > 60% | < 60% → 持續 OPEN |
| 失敗計數準確性 | 4xx 是否正確不計入 | 4xx 不影響 failure_count | 4xx 錯誤計入 → 報警 |

### 1.4 快取指標（FR-06）

| 指標 | 描述 | 目標值 | 測量方式 |
|------|------|--------|---------|
| 快取命中率（Hit Rate） | Redis 快取命中 | > 30%（相同文字） | Redis INFO stats |
| 快取降級率 | Redis 不可用時降級 | < 5% | 降級計數 |
| TTL 有效性 | TTL = 24h 是否正確 | 100% | Redis TTL 抽查 |

### 1.5 覆蓋率追蹤

| 模組 | 當前覆蓋率 | 目標覆蓋率 | 狀態 |
|------|-----------|-----------|------|
| SSMLParser | 85% | 95% | ⚠️ 追蹤 |
| Routes | 81% | 95% | ⚠️ 追蹤 |
| TextChunker | 90% | 95% | ⚠️ 追蹤 |
| CircuitBreaker | 90% | 95% | ⚠️ 追蹤 |
| 其他模組 | > 95% | 95% | ✅ 正常 |

---

## 2. 報警閾值

### 2.1 效能報警

| 指標 | 警告閾值（Warning） | 嚴重閾值（Critical） | 持續時間 |
|------|---------------------|---------------------|---------|
| TTFB | > 300ms | > 500ms | 5 分鐘 |
| 合成耗時 | > 150ms | > 200ms | 5 分鐘 |
| 錯誤率（5xx） | > 0.5% | > 1% | 10 分鐘 |

### 2.2 熔斷器報警

| 指標 | 警告閾值 | 嚴重閾值 | 行動 |
|------|---------|---------|------|
| OPEN 狀態頻率 | > 3 次/hr | > 5 次/hr | 檢查後端健康 |
| HALF_OPEN 探測失敗率 | > 50% | > 80% | 持續 OPEN，考慮降級 |
| 失敗計數異常 | — | 4xx 計入計數 | 立即修復 |

### 2.3 快取報警

| 指標 | 警告閾值 | 嚴重閾值 |
|------|---------|---------|
| 快取命中率 | < 20% | < 10% |
| Redis 連線失敗 | > 3 次/hr | > 10 次/hr |

### 2.4 覆蓋率追蹤報警

| 指標 | 警告閾值 | 嚴重閾值 |
|------|---------|---------|
| 模組覆蓋率 | 低於目標 < 5% | 低於目標 ≥ 5% |
| 單元測試執行失敗 | 任何 FAIL | 任何 FAIL |

---

## 3. 監控頻率

### 3.1 即時監控（每分鐘）

| 指標 | 來源 |
|------|------|
| TTFB | API Gateway / FastAPI middleware |
| HTTP 錯誤率（5xx/4xx） | API Gateway logs |
| CircuitBreaker 狀態 | CircuitBreaker.get_state() |
| 快取命中率 | Redis INFO |

### 3.2 定期檢查（每日）

| 檢查項目 | 說明 |
|---------|------|
| 覆蓋率趨勢 | 比對每日 coverage report |
| 熔斷器狀態摘要 | 每小時 OPEN 次數統計 |
| 錯誤日誌摘要 | 歸類 L1~L4 錯誤分布 |
| Phase 4 FrameworkEnforcer | 確認修復進度 |

### 3.3 階段性檢查（每 Phase）

| Phase | 檢查頻率 |
|-------|---------|
| Phase 5 交付驗證 | 每日 |
| Phase 6 上線後監控 | 每小時（首週）→ 每日（穩定期） |

---

## 4. 緊急應變流程

### 4.1 熔斷器觸發（OPEN）

```
觸發條件：CircuitBreaker OPEN
持續時間：每小時 > 5 次

Step 1 — 確認後端健康
  → 檢查 Kokoro 後端 /health
  → 如果後端異常：通知後端團隊
  → 如果後端正常：檢查網路/連線

Step 2 — 評估影響
  → 如果 TTFB > 500ms 持續 > 10 分鐘
  → 考慮切換到備用後端（如有）

Step 3 — 降級策略
  → Redis 快取降級（FR-06）已實作
  → 直接合成（繞過快取）
  → 熔斷器自動 HALF_OPEN 恢復
```

### 4.2 效能退化（TTFB > 500ms）

```
觸發條件：TTFB 持續 > 500ms 超過 10 分鐘

Step 1 — 診斷
  → 檢查 Kokoro 後端響應時間
  → 檢查網路延遲
  → 檢查 Redis 延遲

Step 2 — 隔離
  → 如果後端問題：觸發熔斷器
  → 如果網路問題：聯絡網路團隊
  → 如果 Redis 問題：驗證快取降級運作

Step 3 — 上報
  → 通知 Johnny（客戶）
  → 記錄事件至 DEVELOPMENT_LOG.md
```

### 4.3 測試失敗應變

```
觸發條件：CI 中任何測試 FAIL 或 Coverage < 80%

Step 1 — 隔離失敗測試
  → 確認是哪個 FR / 模組失敗
  → 隔離該模組，不影響其他功能

Step 2 — 評估影響
  → 如果是 P0（FR-01~03）：立即修復
  → 如果是其他 FR：記錄至 QUALITY_REPORT.md，計畫修復

Step 3 — 修復驗證
  → 修復後重新執行 pytest
  → 確認覆蓋率恢復
  → 更新 BASELINE.md（如有必要）
```

### 4.4 高嚴重性問題（HIGH）應變

```
觸發條件：任何 HIGH 問題發現

Step 1 — 立即暫停交付
  → Phase 5 交付暫停
  → 通知 Johnny

Step 2 — 分類問題
  → 如果影響功能：立即修復（< 24 小時）
  → 如果影響效能：計畫修復（< 72 小時）

Step 3 — 驗證修復
  → 修復後重新執行相關測試
  → 更新 QUALITY_REPORT.md + BASELINE.md
  → 確認 HIGH = 0 後恢復交付
```

### 4.5 Phase 4 FrameworkEnforcer 問題

```
觸發條件：FrameworkEnforcer BLOCK 未通過（Phase 4）

現況：Phase 3 通過，Phase 4 未通過
影響：Constitution 分數不受影響，功能不受影響

Step 1 — 確認問題
  → 問題為 A/B 協作真實性爭議（TRACEABILITY 不完整）
  → 不影響功能，不阻礙 Phase 5 交付

Step 2 — 計畫修復
  → 由 Johnny 決定是否修復 Phase 4 問題
  → 如需修復：重新執行 Phase 4 A/B Review

Step 3 — 記錄至 QUALITY_REPORT.md
  → 持續追蹤，不阻礙交付
```

---

## 5. 監控工具建議

| 用途 | 推薦工具 |
|------|---------|
| API 監控（TTFB、錯誤率） | Grafana + Prometheus / Datadog |
| 熔斷器狀態監控 | CircuitBreaker.get_metrics() → Prometheus |
| Redis 快取監控 | Redis INFO + Grafana |
| 測試覆蓋率追蹤 | pytest-cov + Codecov / Coveralls |
| 錯誤日誌追蹤 | Sentry / ELK Stack |
| 告警通知 | PagerDuty / Slack / Telegram |

---

## 6. 監控開始時間

| 階段 | 開始時間 |
|------|---------|
| Phase 5 基線建立 | 2026-04-12（本文件建立時） |
| Phase 5 交付驗證 | 2026-04-12 起 |
| Phase 6 上線後監控 | 上線後立即啟動 |

---

*本監控計畫由 Agent A（DevOps）依據 NFR-01~NFR-06 + FR-05/06 編製。*
*建立日期：2026-04-12 17:28 GMT+8*
