# Phase 6 執行計劃 — tts-kokoro-v613

> **版本**: v6.109（Framework）
> **專案**: tts-kokoro-v613（TTS Kokoro v613）
> **日期**: 2026-04-14
> **Framework**: methodology-v2 v6.109
> **前置條件**: Phase 5 全部 Sign-off ✅（BASELINE.md 雙方簽收、A/B 監控三項通過、兩次 APPROVE）
> **狀態**: 待 Johnny 確認啟動

---

## 0. 執行協議（§0）

```
Johnny: plan-phase --phase {N}
         ↓
Agent: 依照 plan 派遣 sub-agent
         ↓
Agent: 每步呼叫 PhaseHooks 監控
         ↓
Agent: run-phase --phase {N} --resume（POST-FLIGHT）
         ↓
失敗 → plan-phase --repair --step {N}.X
         ↓
成功 → 下一 Phase
```

**CLI 命令**：
```bash
cd /Users/johnny/.openclaw/workspace/methodology-v2
python3 cli.py update-step --step 6
python3 cli.py end-phase --phase 5
python3 cli.py stage-pass --phase 5
python3 cli.py run-phase --phase 6 --goal "Phase 6 execution"
```

---

## 1. 硬規則（HR-01~HR-15）

| HR | 規則 | 後果 | 具體行動 |
|----|------|------|---------|
| HR-01 | A/B 不同 Agent，禁自寫自審 | 終止 -25 | Agent A spawn → Agent B spawn（嚴格順序）|
| HR-02 | Quality Gate 需實際命令輸出 | 終止 -20 | 每個 QG 保存 stdout |
| HR-03 | Phase 順序執行，不可跳過 | 終止 -30 | state.json phase=5 → 6 |
| HR-04 | HybridWorkflow mode=ON，強制 A/B | 終止 | prompt 含 mode=ON |
| HR-05 | 衝突時優先 methodology-v2 | 記錄 | 爭議時 methodology-v2 為準 |
| HR-06 | 禁引入規格書外框架 | 終止 -20 | forbidden list |
| HR-07 | DEVELOPMENT_LOG 需記錄 session_id | -15 | 每筆記 session_id |
| HR-08 | Phase 結束需執行 Quality Gate | 終止 -10 | stage-pass --phase 6 |
| HR-09 | Claims Verifier 驗證需通過 | 終止 -20 | citations 對照 |
| HR-10 | sessions_spawn.log 需有 A/B 記錄（即時）| 終止 -15 | **每次派遣時即時寫入，不是完成後補** |
| HR-11 | Phase Truth < 70% 禁進入下一 Phase | 終止 | <70% → PAUSE |
| HR-12 | A/B 審查 > 5 輪 → PAUSE | — | 達 5 輪主動停 |
| HR-13 | Phase 執行 > 預估 ×3 → PAUSE | — | 記 start_time |
| HR-14 | Integrity < 40 → FREEZE | — | QG 後查 Integrity |
| HR-15 | citations 必須含行號 + artifact_verification | -15 | 無 citations = 任務失敗 |

---

## 2. A/B 角色（Phase 6）⚠️ 重要

### 角色名稱（auditor 識別關鍵）

| Plan 規定名稱 | 說明 |
|---------------|------|
| **Agent A** | `qa` — 品質深度分析 |
| **Agent B** | `architect` 或 `pm` — 品質報告審查 |

**⚠️ sessions_spawn.log 中的 role 必須是 `qa` 或 `architect`/`pm`**

### Agent A（QA Lead）

| 屬性 | 內容 |
|------|------|
| Persona | `qa` |
| 職責 | 彙整 Phase 1-5 品質數據、執行 Constitution 全面檢查、撰寫 QUALITY_REPORT.md 完整版（七章節）、持續 A/B 監控 |
| 禁止 | 只描述問題不分析根源；在監控數據不穩定時宣告品質通過 |

### Agent B（Architect / PM）

| 屬性 | 內容 |
|------|------|
| Persona | `architect` 或 `pm` |
| 職責 | 審查 QUALITY_REPORT.md 分析深度、確認改進建議可行性、A/B 評估 |
| 禁止 | 接受只有數字沒有分析的品質報告；跳過改進建議的可行性確認 |

---

## 3. 上階段產出確認（Phase 5 前置產出）

| 產出 | 狀態 | 路徑 |
|------|:-----:|------|
| ✅ BASELINE.md | ✅ | `05-verify/BASELINE.md` |
| ✅ VERIFICATION_REPORT.md | ✅ | `05-verify/VERIFICATION_REPORT.md` |
| ✅ QUALITY_REPORT.md（初版） | ✅ | `05-verify/QUALITY_REPORT.md` |
| ✅ MONITORING_PLAN.md | ✅ | `05-verify/MONITORING_PLAN.md` |
| ✅ 238 tests PASS | ✅ | `03-development/tests/` |
| ✅ 91% 覆蓋率 | ✅ | pytest --cov |
| ✅ Constitution Score 85.7% | ✅ | Phase 5 |

---

## 4. Phase 6 交付物

### 必須交付物（Mandatory）

| 交付物 | 負責方 | 驗證方 | 位置 |
|--------|--------|--------|------|
| `QUALITY_REPORT.md`（完整版，七章節）| Agent A (qa) | Agent B | `06-quality/` |
| `sessions_spawn.log` | Agent A (qa) | — | 即時記錄 |
| `DEVELOPMENT_LOG.md`（Phase 6 段落）| Agent A (qa) | Agent B | 專案根目錄 |

---

## 5. Step-by-Step 執行流程

### Step 6.1: 前置確認 + 監控啟動（Agent A）

**執行命令**：
```bash
# 確認 Phase 5 已完成
cd /Users/johnny/.openclaw/workspace/methodology-v2
python3 quality_gate/phase_artifact_enforcer.py

# 確認 A/B 監控機制持續運行
python3 scripts/spec_logic_checker.py      # ≥ 90 分
python3 scripts/performance_check.py       # < 10% 偏差
python3 scripts/circuit_breaker_check.py   # 0 次觸發
```

**預期輸出**：
- Phase 5 完成確認 ✅
- 邏輯正確性 ≥ 90 分
- 回應時間偏差 < 10%
- 熔斷器觸發 0 次

---

### Step 6.2: Phase 1-5 品質數據彙整（Agent A）

**數據來源**：
1. 各 Phase DEVELOPMENT_LOG.md 的 Quality Gate 結果
2. Constitution Runner 歷次輸出（Phase 3-5）
3. pytest 覆蓋率報告（Phase 3-4）
4. spec_logic_checker.py 歷次分數（Phase 5）
5. MONITORING_PLAN.md 的監控記錄（Phase 5）
6. TRACEABILITY_MATRIX.md（需求 → 測試完整度）

**彙整格式**：
- 每個 Phase 的 Constitution 四維度分數
- 每個 Phase 的 ASPICE 合規率
- 每次失敗案例的 TC ID 與根源描述
- 每次邏輯審查中發現的問題類型

---

### Step 6.3: Constitution 全面檢查（Agent A）

**執行命令**：
```bash
python3 quality_gate/constitution/runner.py
```

**閾值**：
| 閾值 | 門檻 | 驗證方式 |
|------|------|---------|
| TH-02 | Constitution 總分 ≥ 80% | constitution runner |
| TH-07 | 邏輯正確性 ≥ 90 | verification |

**預期輸出**：
```
正確性:   XX%（目標 100%）
安全性:   XX%（目標 100%）
可維護性: XX%（目標 > 70%）
覆蓋率:   XX%（目標 > 80%）
總分:     XX%（目標 ≥ 80%）
```

**若 < 80%**：
1. 識別低分維度與具體模組
2. 修正低分項目（對應 Phase 3 代碼或 Phase 4 測試）
3. 重新執行 constitution/runner.py
4. 直到總分 ≥ 80% 才繼續

---

### Step 6.4: 品質根源分析（Agent A）

**分析流程（三層遞進）**：

```
Layer 1：問題識別
  → 從 Phase 1-5 的 DEVELOPMENT_LOG 提取所有「REJECT」、「失敗」、「未通過」記錄
  → 從 Constitution 低分維度找出具體問題描述

Layer 2：分類彙整
  → 依問題類型分類：邏輯錯誤 / 文檔缺失 / 測試遺漏 / 架構偏離 / 其他
  → 統計每類問題的出現次數

Layer 3：根源 Phase 定位
  → 對每類問題，追溯「最早應該被攔截的 Phase」
  → 識別該 Phase 哪個步驟、哪個門檻沒有發揮作用
  → 提出針對根源的具體改進動作（非泛泛建議）
```

**Phase 5 已知的問題**：
| 問題 | 等級 | 根源 Phase |
|------|------|-----------|
| FR-02 覆蓋率 85%（< 95% 目標）| LOW | Phase 4 |
| FR-07 覆蓋率 81%（< 95% 目標）| LOW | Phase 4 |
| FrameworkEnforcer Phase 4 BLOCK | MEDIUM | Phase 4 |

---

### Step 6.5: 撰寫 QUALITY_REPORT.md 完整版（Agent A）

**位置**：`06-quality/QUALITY_REPORT.md`

**七章節結構**：

```markdown
# Quality Report - tts-kokoro-v613（完整版）

## 1. 品質指標全覽（Phase 5 初版 → Phase 6 更新）
| 指標 | 目標 | Phase 5 快照 | Phase 6 驗證 | 趨勢 | 狀態 |
|------|------|-------------|-------------|------|------|
| Constitution 總分 | ≥ 80% | 85.7% | XX% | ↑/↓/→ | ✅/❌ |
| 代碼覆蓋率 | ≥ 80% | 91% | XX% | ↑/↓/→ | ✅/❌ |
| 測試通過率 | 100% | 100% | 100% | → | ✅ |
| ASPICE 合規率 | > 80% | 100% | XX% | ↑/↓/→ | ✅/❌ |
| 邏輯正確性分數 | ≥ 90 分 | 9/10 | XX 分 | ↑/↓/→ | ✅/❌ |

## 2. ASPICE 各 Phase 合規性分析
| Phase | 文件 | 合規率 | 主要缺失 | 根源分析 |
|-------|------|--------|----------|----------|
| Phase 1 | SRS.md | XX% | [具體缺失] | [在哪個步驟遺漏] |
| Phase 2 | SAD.md | XX% | [具體缺失] | [在哪個步驟遺漏] |
| Phase 3 | 代碼 + 測試 | XX% | [具體缺失] | [在哪個步驟遺漏] |
| Phase 4 | TEST_PLAN + RESULTS | XX% | [具體缺失] | [在哪個步驟遺漏] |
| Phase 5 | BASELINE + VERIFY | XX% | [具體缺失] | [在哪個步驟遺漏] |

## 3. Constitution 四維度深度分析
### 3.1 正確性（目標 100%）
### 3.2 安全性（目標 100%）
### 3.3 可維護性（目標 > 70%）
### 3.4 測試覆蓋率（目標 > 80%）

## 4. 品質問題根源分析（系統性）
### 4.1 問題分類彙整
### 4.2 根源 Phase 分布

## 5. 改進建議（具體可執行）
| 優先級 | 改進項目 | 對應根源 Phase | 具體動作 | 負責角色 | 目標指標 |
|--------|----------|---------------|----------|----------|----------|
| P0 | [改進項目] | Phase X | [具體動作] | [角色] | [指標] |

## 6. A/B 監控數據分析（Phase 6 期間）
| 日期 | 邏輯分數 | 回應時間偏差 | 錯誤率 | 熔斷器 | 結論 |
|------|----------|-------------|--------|--------|------|

## 7. 品質目標達成摘要
| 目標 | 達成狀態 | 說明 |
|------|----------|------|
| ASPICE 合規率 > 80% | ✅/❌ | 實際：XX% |
| Constitution 總分 ≥ 80% | ✅/❌ | 實際：XX% |
| 邏輯正確性 ≥ 90 分 | ✅/❌ | 實際：XX 分 |
```

---

### Step 6.6: A/B 品質報告審查（Agent A → Agent B）

**Agent B 審查清單**：

**分析深度**
- [ ] 品質指標有 Phase 5 vs Phase 6 的趨勢對比（非只有當下數字）
- [ ] ASPICE 各 Phase 合規率有具體缺失項目（非只有百分比）
- [ ] Constitution 四維度有模組級別的細化分析
- [ ] 問題分類有「首次出現 Phase」的根源追溯

**改進建議可行性**
- [ ] 每條改進建議有具體動作（動詞 + 對象 + 門檻）
- [ ] 改進建議有對應的負責角色（不能是「系統自動改善」）
- [ ] P0 優先級改進建議有目標指標（可量化驗證）
- [ ] 改進建議已考慮對後續 Phase 7-8 的影響

**Constitution 四維度完整**
- [ ] 正確性：模組級別有明細（非只有總分）
- [ ] 安全性：掃描結果有具體項目（非只說「通過」）
- [ ] 可維護性：有具體可維護性問題描述
- [ ] 測試覆蓋率：有未覆蓋區域的具體模組/函數

---

### Step 6.7: Quality Gate 最終確認（Agent A）

**執行命令**：
```bash
# ASPICE 文檔完整性
python3 quality_gate/doc_checker.py
# 預期：Compliance Rate > 80%

# Framework Enforcement
methodology quality
# 預期：✅ 全部通過，無 BLOCK
```

---

## 6. HR-12/13 時間追蹤

| Step | 預估 | HR-13 臨界值 |
|------|------|--------------|
| 6.1 前置確認 | 15m | 45m |
| 6.2 數據彙整 | 30m | 90m |
| 6.3 Constitution 檢查 | 20m | 60m |
| 6.4 根源分析 | 30m | 90m |
| 6.5 撰寫報告 | 45m | 135m |
| 6.6 A/B 審查 | 30m | 90m |
| 6.7 Quality Gate | 20m | 60m |
| **總計** | **190m (~3h)** | **570m** |

---

## 7. 退出條件（全部必須 ✅）

| 條件 | 門檻 | 狀態 |
|------|------|------|
| Constitution 總分 | ≥ 80% | ⬜ |
| ASPICE 合規率 | > 80% | ⬜ |
| 邏輯正確性分數 | ≥ 90 分 | ⬜ |
| QUALITY_REPORT.md 完整版 | 七章節全部完成 | ⬜ |
| Agent B APPROVE | 品質報告審查通過 | ⬜ |
| sessions_spawn.log | qa + architect 即時記錄 | ⬜ |
| DEVELOPMENT_LOG | Phase 6 段落含 session_id | ⬜ |

---

## 8. sessions_spawn.log 格式（HR-10）⚠️ 重要

**⚠️ 即時寫入，不是完成後補**

每次 `sessions_spawn()` 呼叫時，**在派遣前**寫入：

```json
{"timestamp":"ISO8601","role":"qa","task":"任務名稱","session_id":"agent:...","fr":"PHASE6","confidence":0,"verdict":"N/A"}
```

派遣完成後更新 verdict：

```json
{"timestamp":"ISO8601","role":"qa","task":"任務名稱","session_id":"agent:...","fr":"PHASE6","confidence":1-10,"verdict":"PASS|APPROVE|REJECT"}
```

---

## 9. 禁止事項

- ❌ **完成後補寫 sessions_spawn.log**（視同造假）
- ❌ 自己執行驗收測試/stage-pass/git（繞過 sub-agent）
- ❌ sessions_spawn.log 寫 `developer`（必須是 `qa` 或 `architect`）
- ❌ 自己判定測試通過（需 Agent B 審查）
- ❌ Constitution 總分 < 80% 就建立基線

---

## 10. 下一步

```bash
# Johnny 審核後，執行：
cd /Users/johnny/.openclaw/workspace/methodology-v2
python3 cli.py run-phase --phase 6 --goal "Phase 6 execution"
```

---

*本計劃依 methodology-v2 SKILL.md v6.109 + docs/P6_SOP.md 生成*
*日期：2026-04-14*
*Phase 6：品質保證*
*Agent A: qa | Agent B: architect/pm*
