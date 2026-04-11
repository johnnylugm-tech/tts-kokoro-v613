# methodology-v2 v6.109
> Agent Executable Spec. Phase detail → Lazy Load `docs/P{N}_SOP.md`

## 0. 執行協議
```
1. READ .methodology/state.json → current_phase
2. LOAD 本文件 Phase {N} 章節
3. CHECK 進入條件 → blocker → STOP
4. EXECUTE SOP → LAZY LOAD docs/P{N}_SOP.md
5.   RECORD output | SPAWN A/B agent
6. CHECK 退出條件 → fail → FIX + RETRY
7. UPDATE state.json phase=N+1 → GOTO 1
```
CLI: `python cli.py update-step --step N` / `python cli.py end-phase --phase N` / `python cli.py stage-pass --phase N`
Phase Reset → **docs/CLI_REFERENCE.md**

## 1. 硬規則（違反即終止）
| ID | 規則 | 後果 |
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
| HR-12 | A/B 審查 > 5 輪 → PAUSE 通知 Johnny | — |
| HR-13 | Phase 執行 > 預估 ×3 → PAUSE checkpoint | — |
| HR-14 | Integrity < 40 → FREEZE 全面審計 | — |
| HR-15 | citations 必須含行號 + `artifact_verification` | -15 |

## 2. A/B 協作
**禁止**：自寫自審(HR-01) · HybridWorkflow=OFF(HR-04) · sessions_spawn.log 缺失(HR-10) · 程式碼省略號`...`→任務失敗
**負面約束**：`unable_to_proceed` 不說明原因(-15) · 編造內容(-20) · Subagent 繼承父 context(-15)
**產出格式**：`status(success/error/unable_to_proceed)` | `result` | `confidence(1-10)` | `citations` | `summary(50字內)`
**Subagent 隔離**：sessions_spawn 用獨立 fresh messages[]，不繼承父 Agent 上下文
詳細 → **docs/HYBRID_WORKFLOW_GUIDE.md**

## 3. 閾值門檻
| ID | 指標 | 門檻 | Phase | ID | 指標 | 門檻 | Phase |
|----|------|------|-------|----|------|------|-------|
| TH-01 | ASPICE 合規率 | >80% | 1-8 | TH-10 | 測試通過率 | =100% | 3-8 |
| TH-02 | Constitution 總分 | ≥80% | 5-8 | TH-11 | 單元測試覆蓋率 | ≥70% | 3 |
| TH-03 | Constitution 正確性 | =100% | 1-4 | TH-12 | 單元測試覆蓋率 | ≥80% | 4-8 |
| TH-04 | Constitution 安全性 | =100% | 1-4 | TH-13 | SRS FR 覆蓋率 | =100% | 4-8 |
| TH-05 | Constitution 可維護性 | >70% | 2-4 | TH-14 | 規格完整性 | ≥90% | 1 |
| TH-06 | Constitution 測試覆蓋率 | >80% | 3-4 | TH-15 | Phase Truth | ≥70% | 1-8 |
| TH-07 | 邏輯正確性分數 | ≥90 | 5-8 | TH-16 | 代碼↔SAD 映射率 | =100% | 3 |
| TH-08 | AgentEvaluator 標準 | ≥80 | 1-2 | TH-17 | FR↔測試映射率 | ≥90% | 4 |
| TH-09 | AgentEvaluator 嚴格 | ≥90 | 3-8 | | | | |
驗證命令 → **docs/CLI_REFERENCE.md**

## 4. Phase 路由
| Ph | 名稱 | Agent A/B | 關鍵交付物 | EXIT |
|----|------|-----------|-----------|------|
| 1 | 需求規格 | architect/reviewer | SRS, SPEC_TRACKING, TRACEABILITY | TH-01,03,14; APPROVE |
| 2 | 架構設計 | architect/reviewer | SAD, ADR | TH-01,03,05; APPROVE |
| 3 | 代碼實現 | developer/reviewer | 03-development/src/, 03-development/tests/ | TH-06,08,10,11,16; APPROVE |
| 4 | 測試 | qa/reviewer | TEST_PLAN, TEST_RESULTS | TH-01,03,06,10,12,17 |
| 5 | 驗證交付 | devops/architect | BASELINE, MONITORING_PLAN | TH-02,07; APPROVE |
| 6 | 品質保證 | qa/architect | QUALITY_REPORT | TH-02,07; APPROVE |
| 7 | 風險管理 | qa/devops/architect | RISK_REGISTER | TH-07; Decision Gate 100%; APPROVE |
| 8 | 配置管理 | devops/architect | CONFIG_RECORDS, Git Tag | pip freeze 存在; APPROVE |
Phase N 詳細 SOP → **LAZY LOAD `docs/P{N}_SOP.md`** · Verify_Agent → Phase 3+，Agent B<80 或自評差異>20 → **docs/VERIFIER_GUIDE.md**

## 5. 外部文檔
`SKILL_DOMAIN.md` · `docs/P{N}_SOP.md`（Phase SOP）· `templates/`（交付物模板） · `docs/PLAN_PHASE_SPEC.md`（plan-phase 完整規格）· `docs/HYBRID_WORKFLOW_GUIDE.md` · `docs/CLI_REFERENCE.md` · `docs/ANNOTATION_GUIDE.md` · `docs/VERIFIER_GUIDE.md` · `docs/RUNTIME_METRICS_MANUAL.md` · `docs/CONSTITUTION_GUIDE.md` · `docs/COWORK_PROTOCOL_v1.0.md` · `docs/TASK_INITIALIZATION_PROMPT.md`

## 6. HR-14 Integrity 計算

Integrity = 各 Phase 交付物完整度加權平均

```python
def calculate_integrity(
    phase_completions: dict[int, float],
    constitution_scores: dict[int, float],
    log_completeness: float
) -> float:
    """
    Formula:
        Integrity = Σ(Phase_N_completeness × Weight_N) × 100

    Weights:
        P1: 0.10, P2: 0.15, P3: 0.20, P4: 0.15,
        P5: 0.10, P6: 0.10, P7: 0.10, P8: 0.10

    Phase Completeness =
        (交付物數量 / 預期數量) ×
        (Constitution Score / 100) ×
        (sessions_spawn.log 完整度)

    HR-14: Integrity < 40 → FREEZE

    驗證命令：python cli.py integrity --project .
    """
    weights = {1: 0.10, 2: 0.15, 3: 0.20, 4: 0.15,
               5: 0.10, 6: 0.10, 7: 0.10, 8: 0.10}

    integrity = 0
    for phase, completion in phase_completions.items():
        constitution = constitution_scores.get(phase, 0)
        phase_score = completion * (constitution / 100) * log_completeness
        integrity += phase_score * weights.get(phase, 0)

    return integrity * 100
```

狀態追蹤欄位（state.json）：
```json
{
  "current_phase": 3,
  "start_time": "2026-04-04T05:00:00Z",
  "estimated_minutes": 180,
  "checkpoint_interval_minutes": 60,
  "last_checkpoint": "2026-04-04T06:00:00Z",
  "hr13_triggered": false,
  "hr13_remaining_minutes": null
}
```

---

---

## 附錄：CQG — Computational Quality Gate (v6.64)

CQG 是一組度量驅動的 Quality Gate 工具，自動偵測程式碼品質問題。

### 工具清單

| 工具 | 檔案 | 功能 |
|------|------|------|
| LinterAdapter | `quality_gate/linter_adapter.py` | 統一 pylint/eslint/golangci-lint 輸出 |
| ComplexityChecker | `quality_gate/complexity_checker.py` | Cyclomatic complexity 分析 |
| CoverageAnalyzer | `quality_gate/coverage_analyzer.py` | 未覆蓋函式「關鍵性」分析 |
| FitnessFunctions | `quality_gate/fitness_functions.py` | Coupling/Cohesion/Stability/Reusability |
| BaselineManager | `integrity/baseline_manager.py` | Phase-Gate baseline 建立/版本化 |
| SabSpec | `quality_gate/sab_spec.py` | 結構化 SAB 格式 |
| SabParser | `quality_gate/sab_parser.py` | 從 SAD.md 解析生成 SabSpec |

### Phase 整合

| Phase | CQG 檢查 |
|-------|----------|
| Phase 2 | `_check_sab()` — 建立 SAB |
| Phase 3+ | `_check_fitness()` — SAB drift detection |
| Phase 3+ | `_check_baseline_drift()` — Baseline drift detection |
| Phase 3+ | `_check_constitution()` — 含 BVS behaviour validation |
| Any | `_check_linter()`, `_check_complexity()`, `_check_coverage_analyzer()` |

> **注意：** `_check_constitution()` 在所有 Phase 都會執行 Constitution 靜態檢查，但內含的 BVS behaviour validation (`_check_behaviour()`) 只在 Phase 3+ 自動觸發。

### 安裝
```bash
pip3 install --break-system-packages -r requirements-cqg.txt
```

---

### BVS — Behaviour Validation System (v6.64)

BVS 驗證 AI Agent 的實際行為是否符合 Constitution HR 規則，補足 CQG 只測量代碼靜態品質的缺口。

#### 與 CQG 的區別

| 維度 | CQG | BVS |
|------|-----|-----|
| 測量對象 | Codebase（代碼本身）| Agent Behaviour（Agent 行為）|
| 觸發時機 | 每個 Phase Gate | Phase 3+ Constitution |
| 輸出 | 分數（72/100）| Pass/Fail（是否違反 HR）|
| 資料來源 | AST, coverage.xml, linter | sessions_spawn.log |

#### 工具清單

| 工具 | 檔案 | 功能 |
|------|------|------|
| InvariantEngine | `constitution/invariant_engine.py` | 7 個 HR invariants 檢查 |
| ExecutionLogger | `constitution/execution_logger.py` | 從 sessions_spawn.log 收集日誌 |
| BVSRunner | `constitution/bvs_runner.py` | 整合 InvariantEngine + ExecutionLogger |

#### Invariants 對照表

| HR | Invariant | Severity | Trigger |
|----|-----------|----------|---------|
| HR-03 | Phase execution order | critical | Phase 執行順序 |
| HR-07 | Artifact citation required | high | 無 citations |
| HR-10 | Subagent isolation | high | Session 重用 |
| HR-12 | A/B review threshold | medium | 審查 >5 輪 |
| HR-13 | Phase timeout | medium | 超過預估 3 倍 |
| HR-15 | Artifact read before proceeding | critical | 無 artifact 引用 |
| TH-07 | Confidence calibration | medium | 低信心但聲稱成功 |

#### Phase 整合

| Phase | BVS 行為 |
|-------|----------|
| Phase 1-2 | 自動 skip |
| Phase 3+ | 自動執行 invariant checks |

#### 使用方式
```bash
# 單一 Phase 檢查
python constitution/bvs_runner.py --project-path /path --phase 3

# 全 Phase 檢查
python constitution/bvs_runner.py --project-path /path --all
```

---

*methodology-v2 v6.64 | Agent Executable Specification | Last Updated: 2026-04-07*
