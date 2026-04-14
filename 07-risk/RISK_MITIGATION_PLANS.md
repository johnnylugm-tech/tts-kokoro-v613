# RISK_MITIGATION_PLANS.md — Phase 7 風險緩解計畫

> 版本：v1.0  
> 日期：2026-04-14  
> 依據：RISK_REGISTER.md、QUALITY_REPORT.md、SRS.md  
> 角色：Agent B（QA — 風險管理）  

---

## 1. 緩解計畫總覽

| ID | 風險 | 優先順序 | 緩解策略 | 行動項目 | 預定完成 | 狀態 |
|----|------|---------|---------|---------|---------|------|
| R-01 | Kokoro Docker 崩潰 | P1 | 緩解型 | 斷路器 + 監控 + 健康檢查 | 持續 | 監控中 |
| R-02 | 斷路器誤判 | P2 | 緩解型 | 動態閾值調整 + 熔斷後快速恢復測試 | 持續 | 監控中 |
| R-03 | Redis 失效 | P3 | 接受型 | 降級至直接合成（FR-06 已有設計） | 不適用 | 降級備援 |
| R-04 | SSML 解析失敗 | P2 | 緩解型 | Fallback 機制 + L4 負面測試覆蓋 | 持續 | 監控中 |
| R-05 | 文本切分破壞語意 | P2 | 緩解型 | 三級切分規則 + 中英文混合邊界測試 | 持續 | 監控中 |
| R-06 | Phase Truth < 70% | **P0** | 修復型 | 解決 BLOCK 違規 + Johnny 手動確認 | 2026-04-14 | **主動修復中** |
| R-07 | Constitution Score 逼近閾值 | **P0** | 修復型 | 建立 VERIFICATION.md + 避免新增違規 | 2026-04-14 | **主動修復中** |
| R-08 | VERIFICATION.md 缺失 | **P0** | 修復型 | 建立安全驗證結果文件 | 2026-04-14 | **待修復** |
| R-09 | FrameworkEnforcer BLOCK | P1 | 修復型 | 確認並解決 4 項流程違規 | 2026-04-14 | **待修復** |
| R-10 | 覆蓋率未達標 | P3 | 接受型 | 持續監控，視為長期優化目標 | 無期限 | 監控中 |

---

## 2. 高優先順序緩解計畫（P0）

### MP-R-06：Phase Truth < 70%（當前 40%）

**根本原因**：FrameworkEnforcer 發現 4 項框架流程違規（BLOCK-01~04）

**行動項目**：

| # | 行動 | 負責人 | 估計時間 | 狀態 |
|---|------|--------|---------|------|
| 1 | 執行 `sessions_spawn.log` 自檢 — 隨機選 1 筆記錄確認 task 描述合理 | Johnny | 5 min | **待 Johnny** |
| 2 | 執行 `DEVELOPMENT_LOG.md` 自檢 — 確認有實際命令輸出（非截圖） | Johnny | 5 min | **待 Johnny** |
| 3 | 執行 `06-quality/QUALITY_REPORT.md` 自檢 — 確認內容非空洞 template | Johnny | 5 min | **待 Johnny** |
| 4 | 執行 `06-quality/MONITORING_PLAN.md` 自檢 — 確認內容非空洞 template | Johnny | 5 min | **待 Johnny** |
| 5 | Agent A 解決 FrameworkEnforcer BLOCK 4 項違規 | Agent A | 30 min | **待修復** |
| 6 | 重新執行 Constitution + Phase Truth Check | Agent A | 5 min | 待執行 |

**成功標準**：Phase Truth Score ≥ 70%

**驗證方式**：
```bash
# Phase Truth Check 重新執行
cd /Users/johnny/.openclaw/workspace/tts-kokoro-v613
python3 -m constitution_checker --phase 6 --check-type phase_truth
```

---

### MP-R-07：Constitution Score 逼近閾值（當前 80.47%）

**根本原因**：Phase 6 新增 1 個 HIGH 違規（V-01），Constitution Score 從 85.7% 跌至 80.47%

**行動項目**：

| # | 行動 | 負責人 | 估計時間 | 狀態 |
|---|------|--------|---------|------|
| 1 | **建立 `docs/VERIFICATION.md`（含安全驗證結果）** | Agent A | 15 min | **待修復（P0）** |
| 2 | 避免新增任何違規（ Constitution Score 無安全餘量） | All | 持續 | 監控中 |
| 3 | 若 V-01 修復後分數回升，重新評估整體 Constitution | Agent A | 5 min | 待執行 |

**成功標準**：Constitution Score > 80%（建議維持 ≥ 85%）

**驗證方式**：
```bash
# Constitution Check 重新執行
cd /Users/johnny/.openclaw/workspace/tts-kokoro-v613
python3 -m constitution_checker --phase 6 --check-type all
```

---

### MP-R-08：`docs/VERIFICATION.md` 缺少安全驗證結果（HIGH）

**根本原因**：Phase 6 Constitution Check 發現 `missing_security_verification` 違規

**行動項目**：

| # | 行動 | 負責人 | 估計時間 | 狀態 |
|---|------|--------|---------|------|
| 1 | 建立 `docs/VERIFICATION.md` | Agent A | 10 min | **待修復** |
| 2 | 填寫安全驗證結果（Authentication、Authorization、Encryption、Data Protection） | Agent A | 5 min | **待修復** |
| 3 | 驗證 V-01 違規已消除 | Agent A | 5 min | 待驗證 |

**VERIFICATION.md 應包含**：
```markdown
## 安全驗證結果

### Authentication（認證）
- [ ] API 金鑰驗證機制已實作
- [ ] JWT token 支援已實作
- [ ] 測試案例：無效 API 金鑰 → HTTP 401

### Authorization（授權）
- [ ] 音色/模型存取權限分級已實作
- [ ] 測試案例：未授權音色 → HTTP 403

### Encryption（加密）
- [ ] HTTPS/TLS 傳輸加密已配置（對外暴露時）
- [ ] 內部通訊使用 http://localhost（符合預期）

### Data Protection（資料保護）
- [ ] 使用者輸入不寫入日誌
- [ ] 音訊資料不留存
- [ ] 測試驗證：日誌中無敏感內容
```

**成功標準**：`missing_security_verification` 違規消除，Constitution Score > 80%

---

## 3. 中優先順序緩解計畫（P1-P2）

### MP-R-01：Kokoro Docker 崩潰

**緩解策略**：緩解型 — 透過斷路器 + 監控降低衝擊

**行動項目**：
1. 確認 Circuit Breaker 實作正確（失敗 ≥ 3 次 → Open，10 秒後 Half-Open）
2. 實作健康檢查端點 `/health` 和 `/ready`
3. 配置監控：当後端失敗率 > 50% 時發出告警
4. 考慮叢化 Kokoro Docker（未來優化方向）

**現有緩解**（已實作）：
- FR-05 斷路器（`middleware/circuit_breaker.py`）
- 30 秒請求 timeout
- HTTP 503 當斷路時

**殘餘風險控制**：
- 斷路後服務降級，但不影響系統穩定性
- 使用者收到明確的錯誤訊息（非無窮等待）

---

### MP-R-02：斷路器誤判

**緩解策略**：緩解型 — 優化閾值與恢復邏輯

**行動項目**：
1. 分析網路瞬斷場景：是否需要調整失敗計數窗口（sliding window）
2. 在測試環境模擬 3 次連續 5xx，驗證斷路器行為
3. 考慮加入「連續失敗時間」條件而非僅「失敗次數」

**現有緩解**（已實作）：
- Open 後 10 秒自動嘗試恢復
- L4 Mock 測試已驗證熔斷邏輯

---

### MP-R-04：SSML 解析失敗

**緩解策略**：緩解型 — Fallback 機制已實作

**行動項目**：
1. 持續監控 SSML Parser 覆蓋率（當前 85%，目標 95%）
2. 增加 L4 負面測試案例：畸形 SSML 輸入
3. 記錄 Fallback 頻率，若頻率過高需檢討解析邏輯

**現有緩解**（已實作）：
- FR-02 要求 XML 解析失敗時 fallback 純文字
- L3 負面測試已通過

---

### MP-R-05：文本切分破壞語意完整性

**緩解策略**：緩解型 — 三級切分邏輯已實作

**行動項目**：
1. 增加中英文混合邊界測試（L2 測試已驗證基本行為）
2. 監控超長文本（>500 字）的切分品質
3. 考虑引入 NLP 語意切分（未來優化方向）

**現有緩解**（已實作）：
- FR-03 規則不在中英文混合字中間切斷
- L2 測試已驗證「AI」不在中間切斷

---

### MP-R-09：FrameworkEnforcer BLOCK（4 項流程違規）

**緩解策略**：修復型 — 確認並解決流程違規

**行動項目**：
1. 檢視 FrameworkEnforcer BLOCK 報告，確認 4 項違規具體內容
2. 比對 methodology-v2 框架要求，確認缺口
3. 逐一修復 BLOCK-01~04
4. 重新執行 FrameworkEnforcer 驗證修復結果

**依賴**：R-06 的 Johnny 手動確認完成後才能完全修復

---

## 4. 低優先順序行動（P3）

### MP-R-03：Redis 失效（接受型）

**緩解策略**：接受型 — FR-06 設計已包含降級邏輯

**行動**：
- 無需主動修復，因為 Redis 是可選依賴
- 系統會自動降級至直接合成（快取命中率為 0，但不影響功能）

---

### MP-R-10：覆蓋率未達標（接受型）

**緩解策略**：接受型 — 視為長期優化目標

**行動**：
- SSML Parser 覆蓋率 85%（目標 95%）— 異常路徑未完全覆蓋，功能正常
- Routes 覆蓋率 81%（目標 95%）— 錯誤處理分支未完全覆蓋，功能正常
- 兩個模組均高於 Constitution 閾值 80%，無緊急修復必要

---

## 5. 緩解計畫追蹤

| 行動項目 | 開始日期 | 預定完成 | 實際完成 | 狀態 | 備註 |
|---------|---------|---------|---------|------|------|
| Johnny 手動確認 4 項文件 | 2026-04-14 | 2026-04-14 | — | **待 Johnny** | R-06 依賴 |
| 建立 `docs/VERIFICATION.md` | 2026-04-14 | 2026-04-14 | — | **待修復** | R-08 P0 |
| 解決 FrameworkEnforcer BLOCK | 2026-04-14 | 2026-04-14 | — | **待修復** | R-09 P1 |
| 重新執行 Constitution Check | 2026-04-14 | 2026-04-14 | — | 待執行 | 依賴 R-08 |
| 重新執行 Phase Truth Check | 2026-04-14 | 2026-04-14 | — | 待執行 | 依賴 R-06 |

---

## 6. 降級觸發條件

若以下任一條件發生，啟動緊急降級程序：

| 條件 | 降級行動 |
|------|---------|
| Constitution Score < 80% 且無法快速修復 | 暫停發布，召開品質審查 |
| Phase Truth < 70% 且 Johnny 無法及時確認 | 暫停 Phase 6，優先解決流程問題 |
| Kokoro Docker 崩潰且斷路器無法恢復 | 公告服務降級，停止接受新請求 |

---

*本緩解計畫由 Agent B（QA — 風險管理）建立，基於 Phase 7 風險識別與優先順序分析。*
*建立日期：2026-04-14 20:15 GMT+8*

---

## 7. Mitigation Response Summary (English)

### Mitigation Actions
- **R-01**: Circuit breaker + monitoring + health checks
- **R-02**: Dynamic threshold adjustment + fast recovery testing
- **R-03**: Accept (graceful degradation to direct synthesis)
- **R-04**: Fallback mechanism + L4 negative test coverage
- **R-05**: Three-level splitting rules + mixed language boundary tests
- **R-06**: Resolve BLOCK violations + Johnny manual confirmation
- **R-07**: Create VERIFICATION.md + avoid new violations
- **R-08**: Create security verification results document
- **R-09**: Resolve 4 FrameworkEnforcer BLOCK violations
- **R-10**: Accept (monitor as long-term optimization goal)

### Response Strategy
- **Mitigation**: Proactive measures to reduce risk probability/impact
- **Accept**: Acknowledge risk with fallback mechanisms in place
- **Transfer**: Not applicable (no third-party risk transfer)
- **Avoid**: Not applicable (technical dependencies cannot be avoided)

### Action Items Status
- **Open**: 4 items (R-06, R-07, R-08, R-09) - requiring Johnny action
- **Monitor**: 6 items (R-01 to R-05, R-10) - ongoing monitoring
- **Closed**: 0 items - no risks fully resolved yet