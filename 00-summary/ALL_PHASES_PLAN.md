# Phase 1-8 執行計劃 — tts-kokoro-v613

> **Framework**: methodology-v2 v7.99
> **日期**: 2026-04-14
> **專案**: tts-kokoro-v613

---

## Phase 1: 需求規格 (Specify)

**角色**: Architect + Reviewer
**HR 約束**: HR-01, HR-04, HR-06, HR-07, HR-08, HR-10, HR-11

**執行協議**:
```
[Step 0] READ state.json → current_phase=1
[Step 1] LOAD SKILL.md §4 Phase 路由
[Step 2] CHECK 進入條件 → blocker → STOP
[Step 3] EXECUTE SOP → LAZY LOAD docs/P1_SOP.md
[Step 4] RECORD output | SPAWN A/B agent
[Step 5] CHECK 退出條件 → fail → FIX + RETRY
[Step 6] UPDATE state.json phase=2 → GOTO 1
```

**交付物**: SRS.md, SPEC_TRACKING.md, TRACEABILITY_MATRIX.md
**狀態**: ✅ 已完成

---

## Phase 2: 架構設計 (Plan)

**角色**: Architect + Reviewer
**HR 約束**: HR-01, HR-04, HR-06, HR-07, HR-08, HR-10, HR-11

**執行協議**:
```
[Step 0] READ state.json → current_phase=2
...
[Step 6] UPDATE state.json phase=3
```

**交付物**: SAD.md, ADR.md
**狀態**: ✅ 已完成

---

## Phase 3: 代碼實作 (Implementation)

**角色**: Developer + Reviewer
**HR 約束**: HR-01, HR-04, HR-06, HR-07, HR-08, HR-10, HR-11, HR-15

**執行協議**:
```
[Step 0] READ state.json → current_phase=3
...
[Step 6] UPDATE state.json phase=4
```

**交付物**: src/, tests/, IMPLEMENTATION.md, DEVELOPMENT_LOG.md
**狀態**: ✅ 已完成

---

## Phase 4: 測試 (Verify)

**角色**: QA + Reviewer
**HR 約束**: HR-01, HR-04, HR-08, HR-10, HR-11, HR-12

**執行協議**:
```
[Step 0] READ state.json → current_phase=4
...
[Step 6] UPDATE state.json phase=5
```

**交付物**: TEST_PLAN.md, TEST_RESULTS.md
**狀態**: ✅ 已完成

---

## Phase 5: 系統測試 (System Test)

**角色**: DevOps + Architect
**HR 約束**: HR-01, HR-04, HR-08, HR-10

**執行協議**:
```
[Step 0] READ state.json → current_phase=5
...
[Step 6] UPDATE state.json phase=6
```

**交付物**: BASELINE.md, VERIFICATION_REPORT.md, MONITORING_PLAN.md
**狀態**: ✅ 已完成

---

## Phase 6: 品質保證 (Quality)

**角色**: QA + Architect
**HR 約束**: HR-01, HR-07, HR-08, HR-10

**執行協議**:
```
[Step 0] READ state.json → current_phase=6
...
[Step 6] UPDATE state.json phase=7
```

**交付物**: QUALITY_REPORT.md, MONITORING_PLAN.md
**狀態**: ✅ 已完成

---

## Phase 7: 風險管理 (Risk Management)

**角色**: QA + DevOps + Architect
**HR 約束**: HR-01, HR-08, HR-10, HR-12

**執行協議**:
```
[Step 0] READ state.json → current_phase=7
...
[Step 6] UPDATE state.json phase=8
```

**交付物**: RISK_ASSESSMENT.md, RISK_REGISTER.md
**狀態**: 🔄 未開始

---

## Phase 8: 配置管理 (Configuration)

**角色**: DevOps + Architect
**HR 約束**: HR-01, HR-08, HR-10, HR-12

**執行協議**:
```
[Step 0] READ state.json → current_phase=8
...
[Step 6] UPDATE state.json phase=9 (COMPLETE)
```

**交付物**: CONFIG_RECORDS.md, requirements.lock, RELEASE_CHECKLIST.md
**狀態**: 🔄 未開始

---

## 通用 HR 規則 (HR-01~HR-15)

| HR | 規則 | 後果 |
|----|------|------|
| HR-01 | A/B 不同 Agent，禁自寫自審 | 終止 -25 |
| HR-02 | Quality Gate 需實際命令輸出 | 終止 -20 |
| HR-03 | Phase 順序執行，不可跳過 | 終止 -30 |
| HR-04 | HybridWorkflow mode=ON，強制 A/B | 終止 |
| HR-05 | 衝突時優先 methodology-v2 | 記錄 |
| HR-06 | 禁引入規格書外框架 | 終止 -20 |
| HR-07 | DEVELOPMENT_LOG 需記錄 session_id | -15 |
| HR-08 | Phase 結束需執行 Quality Gate | 終止 -10 |
| HR-09 | Claims Verifier 驗證需通過 | 終止 -20 |
| HR-10 | sessions_spawn.log 需有 A/B 記錄 | 終止 -15 |
| HR-11 | Phase Truth < 70% 禁進入下一 Phase | 終止 |
| HR-12 | A/B 審查 > 5 輪 → PAUSE | — |
| HR-13 | Phase 執行 > 預估 ×3 → PAUSE | — |
| HR-14 | Integrity < 40 → FREEZE | — |
| HR-15 | citations 必須含行號 + artifact_verification | -15 |

---

## CLI 命令參考

```bash
# 更新步驟
python3 cli.py update-step --step N

# 結束 Phase
python3 cli.py end-phase --phase N

# 階段通過
python3 cli.py stage-pass --phase N

# 執行 Phase
python3 cli.py run-phase --phase N --goal "Phase N execution"

# 計劃 Phase
python3 cli.py plan-phase --phase N --detailed
```

---

*Generated: 2026-04-14 20:04*
