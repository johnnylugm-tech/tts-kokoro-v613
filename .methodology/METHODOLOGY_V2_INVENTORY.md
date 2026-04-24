# methodology-v2 開發流程用到之組件清單

> **口徑**：以 Plan Phase 1-8 實際引用為準（`.methodology/outputs/Plan_Phase_1~8.md`）
> **Framework 版本**：v9.2（`1a6da23`）
> **產生日期**：2026-04-24
> **驗證日期**：2026-04-24（第三次完整審計，含 actual file existence + call chain）

---

## 🔗 Call Chain 總圖

```
cli.py（單一入口，71 個 subcommands）
├── run-phase ──────────────────────────→ docs/P{N}_SOP.md
├── plan-phase ─────────────────────────→ templates/plan_phase_template.md
│                                        └── scripts/generate_full_plan.py
├── stage-pass ─────────────────────────→ quality_gate/stage_pass_generator.py
├── phase-verify ───────────────────────→ quality_gate/phase_truth_verifier.py（cmd_phase_truth）
├── trace-check ────────────────────────→ internal: _trace_check_sad_to_code / _trace_check_fr_to_tests
├── enforce ────────────────────────────→ enforcement/PolicyEngine + ConstitutionAsCode
├── quality-gate ───────────────────────→ quality_gate/unified_gate.py
├── verify-artifact ────────────────────→ quality_gate/unified_gate.py
├── auto-research ──────────────────────→ quality_dashboard/dashboard.py assess
└── steering run ───────────────────────→ steering/steering_loop.py

scripts/generate_full_plan.py ────────────→ （無 further subprocess calls）
scripts/check_fr_full.py ─────────────────→ pylint + constitution/runner.py
scripts/check_fr_quality.py ──────────────→ py_compile + import check
scripts/generate_sab.py ─────────────────→ SAD.md → JSON

cli_phase_prompts.py ─────────────────────→ Phase 3 developer/reviewer prompts
    └─ PhaseHooksAdapter（透過 prompt 嵌入 Agent 執行流程）
```

---

## 1. CLI 主工具

### 1.1 cli.py（單一入口，71 個 subcommands）

| 子命令 | 直接呼叫的模組/腳本 | 驗證 |
|--------|---------------------|------|
| `python3 cli.py run-phase --phase N` | `docs/P{N}_SOP.md`（lazy load） | ✅ |
| `python3 cli.py plan-phase --phase N` | `templates/plan_phase_template.md` → `scripts/generate_full_plan.py` | ✅ |
| `python3 cli.py stage-pass --phase N` | `quality_gate/stage_pass_generator.py`（`StagePassGenerator`） | ✅ |
| `python3 cli.py end-phase --phase N` | internal（狀態寫入 `state.json`） | ✅ |
| `python3 cli.py update-step --step N` | internal（狀態更新） | ✅ |
| `python3 cli.py phase-verify --phase N` | `quality_gate/phase_truth_verifier.py`（`PhaseTruthVerifier`）→ 方法名 `cmd_phase_truth` | ✅ |
| `python3 cli.py trace-check` | internal: `_trace_check_sad_to_code`, `_trace_check_fr_to_tests` | ✅ |
| `python3 cli.py enforce` | `enforcement/policy_engine.py`（`PolicyEngine`）+ `enforcement/constitution_as_code.py`（`ConstitutionAsCode`） | ✅ |
| `python3 cli.py auto-research` | `quality_dashboard/dashboard.py assess` | ✅ |
| `python3 cli.py quality-gate` | `quality_gate/unified_gate.py`（`UnifiedGate`） | ✅ |
| `python3 cli.py verify-artifact` | `quality_gate/unified_gate.py`（`UnifiedGate`） | ✅ |
| `cli.py steering run --phase N` | `steering/steering_loop.py`（`SteeringLoop`） | ✅ |

**注意**：`phase-verify` 的實作方法名是 `cmd_phase_truth`（非 `cmd_phase_verify`）。

---

## 2. Core Framework 模組（其他章節未涵蓋者）

| 模組 | 上層呼叫者 |
|------|----------|
| `hybrid_workflow.py`（`HybridWorkflow`） | `cli.py`（HR-04 模式控制） |
| `subagent_isolator.py`（`SubagentIsolator`） | `cli.py run-phase`（HR-10 合規驗證） |
| `sessions_spawn_logger.py`（`SessionsSpawnLogger`） | `cli.py run-phase`（sessions_spawn.log 寫入） |
| `agent_spawner.py` | `cli.py`（agent 派遣） |
| `cli_phase_prompts.py`（`PHASE_PROMPTS`） | `cli.py plan-phase`（生成 Phase prompt） |
| `phase_hooks.py`（root，`PhaseHooks`） | `adapters/phase_hooks_adapter.py`（包裝對象） |
| `anti_shortcut/phase_hooks.py` | 獨立框架（未整合） |
| `cli.py` | 單一入口 |

---

## 3. Templates（Plan 產生模板）

| 檔案 | 由誰載入 | 呼叫誰 |
|------|---------|--------|
| `templates/plan_phase_template.md` | `cli.py plan-phase` | `scripts/generate_full_plan.py`（via subprocess） |
| `templates/plan_phase_6_template.md` | `cli.py plan-phase`（Phase 6 專用，自動選用）| 同上 |

---

## 4. SOP 執行細節（Lazy-loaded）

| 檔案 | 由誰載入 | 直接引用的腳本 |
|------|---------|--------------|
| `docs/P1_SOP.md` | `cli.py run-phase` | `requirement_traceability.py`（⚠️ 路徑錯誤：SOP寫`scripts/requirement_traceability.py`，實際在 framework root） |
| `docs/P2_SOP.md` | `cli.py run-phase` | `scripts/generate_sab.py` + `requirement_traceability.py` |
| `docs/P3_SOP.md` | `cli.py run-phase` | `scripts/check_fr_full.py` + `scripts/check_fr_quality.py` + `quality_gate/constitution/runner.py` |
| `docs/P4_SOP.md` | `cli.py run-phase` | `requirement_traceability.py` |
| `docs/P5_SOP.md` | `cli.py run-phase` | `requirement_traceability.py` |
| `docs/P6_SOP.md` | `cli.py run-phase` | `requirement_traceability.py` |
| `docs/P7_SOP.md` | `cli.py run-phase` | （無額外腳本） |
| `docs/P8_SOP.md` | `cli.py run-phase` | （無額外腳本） |

---

## 5. Scripts

### 5.1 主要指令稿（Plan Phase 直接引用）

| 檔案 | 上層入口 | 驗證 |
|------|---------|------|
| `scripts/generate_full_plan.py --phase N --repo /path [--no-output]` | `cli.py plan-phase`（subprocess） | ✅ |
| `scripts/check_fr_full.py --fr FR-XX --project /path [--loop]` | `cli.py quality-gate`（in SOP P3）；直接由 Agent 在 FR 迭代時呼叫 | ✅ |

### 5.2 脚手架腳本（Plan Phase 直接引用）

| 檔案 | Plan Phase |
|------|-----------|
| `scripts/generate_full_plan.py` | P1-P5, P7, P8 |
| `scripts/check_fr_full.py` | P1-P5, P7, P8 |

### 5.3 SOP 額外引用（不在 Phase Matrix 中）

| 檔案 | SOP Phase | 備註 |
|------|----------|------|
| `scripts/check_fr_quality.py` | P3 | Layer 1 快速檢查（~30秒） |
| `scripts/generate_sab.py` | P2 | Phase 2 產出 |
| `requirement_traceability.py`（framework root，非 scripts/） | P1, P2, P4, P5, P6 | ⚠️ 路徑不一致 |

---

## 6. Quality Gate

### 6.1 Constitution 執行器

**檔案**：`quality_gate/constitution/runner.py`

| `--type` 值 | 實際使用 Phase |
|-------------|--------------|
| `srs` | P1（+ `implementation`） |
| `sad` | P2（+ `implementation`） |
| `implementation` | **P1-P5, P7, P8** |
| `test_plan` | P4（+ `implementation`） |
| `verification` | P5（+ `implementation`） |
| `all` | P6（唯一） |

### 6.2 UnifiedGate（`quality-gate` 和 `verify-artifact` 共同底層）

**檔案**：`quality_gate/unified_gate.py`

### 6.3 PhaseTruthVerifier（`phase-verify` 底層）

**檔案**：`quality_gate/phase_truth_verifier.py`

### 6.4 其他 Quality Gate 模組

| 模組 | 上層呼叫者 |
|------|----------|
| `quality_gate/stage_pass_generator.py` | `cli.py stage-pass` |
| `quality_gate/spec_tracking_checker.py` | `quality_gate/unified_gate.py` |
| `quality_gate/unified_gate.py` | `cli.py quality-gate` + `cli.py verify-artifact` |
| `quality_gate/ab_enforcer.py` | `cli.py` |
| `quality_gate/claims_verifier.py` | `quality_gate/unified_gate.py` |
| `quality_gate/citation_enforcer.py` | `quality_gate/unified_gate.py` |

---

## 7. Enforcement（`enforce` 底層）

| 模組 | 上層呼叫者 |
|------|----------|
| `enforcement/policy_engine.py`（`PolicyEngine`） | `cli.py enforce` |
| `enforcement/constitution_as_code.py`（`ConstitutionAsCode`） | `cli.py enforce` |
| `enforcement/execution_registry.py` | `cli.py enforce` |

---

## 8. Agent 執行基礎設施

| 模組 | 上層呼叫者 |
|------|----------|
| `subagent_isolator.py`（`SubagentIsolator`） | `cli.py run-phase`（HR-10 合規） |
| `sessions_spawn_logger.py`（`SessionsSpawnLogger`） | `cli.py run-phase` |
| `agent_spawner.py` | `cli.py` |
| `hybrid_workflow.py`（`HybridWorkflow`） | `cli.py`（HR-04 模式：ON/OFF/HYBRID）|

---

## 9. Phase 1-8 工具使用矩陣

| 工具/模組 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | 底層呼叫鏈 |
|----------|----|----|----|----|----|----|----|----|----------|
| `cli.py run-phase` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | → docs/P{N}_SOP.md |
| `cli.py plan-phase` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | → templates/plan_phase_template.md → scripts/generate_full_plan.py |
| `cli.py stage-pass` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | → stage_pass_generator.py |
| `cli.py end-phase` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | internal |
| `cli.py update-step` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | internal |
| `cli.py phase-verify` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | → phase_truth_verifier.py |
| `cli.py trace-check` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | internal _trace methods |
| `cli.py enforce --level BLOCK` | — | — | ✅ | — | — | — | — | — | → PolicyEngine + ConstitutionAsCode |
| `cli.py auto-research` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | → quality_dashboard/dashboard.py |
| `cli.py quality-gate` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | → unified_gate.py |
| `cli.py verify-artifact` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | → unified_gate.py |
| `cli.py steering` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | → steering_loop.py |
| **Scripts** |
| `generate_full_plan.py` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | via plan-phase |
| `check_fr_full.py` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | via P3 SOP + quality-gate |
| `check_fr_quality.py` | — | — | ✅ | — | — | — | — | — | via P3 SOP |
| `generate_sab.py` | — | ✅ | — | — | — | — | — | — | via P2 SOP |
| `requirement_traceability.py` | ✅ | ✅ | — | ✅ | ✅ | ✅ | — | — | ⚠️ via SOP（路徑錯誤） |
| **Constitution** |
| `--type srs` | ✅+impl | — | — | — | — | — | — | — | |
| `--type sad` | — | ✅+impl | — | — | — | — | — | — | |
| `--type implementation` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | |
| `--type test_plan` | — | — | — | ✅ | — | — | — | — | |
| `--type verification` | — | — | — | — | ✅ | — | — | — | |
| `--type all` | — | — | — | — | — | ✅ | — | — | |
| **PhaseHooks** |
| `PhaseHooksAdapter`（prompt 嵌入） | — | — | ✅ | — | — | — | — | — | via cli_phase_prompts.py |
| **pytest** |
| `pytest tests/ -v` | — | — | ✅ | ✅ | — | — | — | — | |
| `pytest --cov=03-development/src/` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | |
| **Sessions Log** |
| `sessions_spawn.log` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | |

---

## 10. 發現的不一致與問題

### 10.1 `requirement_traceability.py` 路徑不一致（文件錯誤）

| 位置 | 寫法 | 實際路徑 |
|------|------|---------|
| `docs/P1~P6_SOP.md` | `python scripts/requirement_traceability.py` | `methodology-v2/requirement_traceability.py`（framework root） |

**影響**：SOP 中的 `python scripts/requirement_traceability.py ...` 會執行失敗，正確應為 `python requirement_traceability.py ...`。

### 10.2 P6 是隔離 Phase

P6 是唯一不呼叫以下工具的 Phase：
- `generate_full_plan.py`、`check_fr_full.py`
- `auto-research`、`quality-gate`、`verify-artifact`、`steering`
- `trace-check`
- `PhaseHooksAdapter`（prompt 中未嵌入）

唯一工具：`phase-verify --phase 6` + `constitution/runner.py --type all`。

### 10.3 `phase-verify` 命令方法名是 `cmd_phase_truth`

INVENTORY 描述為「直接呼叫 `phase_truth_verifier.py`（`PhaseTruthVerifier`）」是正確的，但底層方法名是 `cmd_phase_truth`，不是 `cmd_phase_verify`。

---

## 11. 驗證狀態總結

| 類別 | 項目數 | 驗證通過 | 問題 |
|------|--------|---------|------|
| CLI 子命令（12 核心） | 12 | ✅ 12/12 | |
| Core Framework 模組 | 7 | ✅ 7/7 | |
| Scripts（plan 直接引用） | 2 | ✅ 2/2 | |
| Scripts（SOP 額外引用） | 3 | ✅ 3/3（路徑問題1個）| |
| Templates | 2 | ✅ 2/2 | |
| SOP docs | 8 | ✅ 8/8 | |
| Quality Gate modules | 6+ | ✅ 6/6 | |
| Enforcement modules | 3 | ✅ 3/3 | |
| Steering/AutoResearch | 2 | ✅ 2/2 | |
| Constitution types | 6 | ✅ 6/6 | |
| 所有列出檔案 actual existence | — | ✅ 全部存在 | |

---

## 12. PhaseHooksAdapter 整合狀態（v9.2）

### 整合方式

PhaseHooksAdapter 透過 `cli_phase_prompts.py` 的 Phase 3 developer/reviewer prompt **嵌入 Agent 的任務描述中**（HR-09 強制執行）。

Agent 在執行每個 FR 時，會在 prompt 中看到具體的鉤子呼叫指令並執行。

### Phase 3 Prompt 嵌入了什麼

**Developer Prompt（每個 FR）：**
```python
from adapters.phase_hooks_adapter import PhaseHooksAdapter
adapter = PhaseHooksAdapter(project_path=..., phase=3, feature_flags={...})
adapter.preflight_all()                               # 只在第一個 FR 前
adapter.monitoring_before_dev("FR-XX")                # 每個 FR 前
# Developer 實作...
hook_result = adapter.monitoring_after_dev("FR-XX", result=dev_result)
if not hook_result.get("passed"):
    raise Exception(f"Hook blocked: {hook_result}")  # UQLM/Hunter block
```

**Reviewer Prompt：**
```python
adapter.monitoring_before_rev("FR-XX")
# Reviewer 審查...
hook_result = adapter.monitoring_after_rev("FR-XX", result=rev_result)
```

**OUTPUT_FORMAT** 新增 `hook_calls` 欄位：
```json
{
  "hook_calls": {
    "monitoring_before_dev": { "blocked": false },
    "monitoring_after_dev": { "passed": true, "shield_verdict": "...", "uqlm_score": 0.92, "hunter_severity": null }
  }
}
```

### 13 Features 鉤子點狀態（⚠️ 待實際執行驗證）

| Feature | 實現 | 鉤子點 | INVENTORY 備註 |
|---------|------|--------|----------------|
| #1 SAIF | `implement/governance/` | monitoring_after_dev | ⚠️ 待驗證 |
| #2 Prompt Shields | `adapters/phase_hooks_adapter.py::PromptShieldWrapper` | monitoring_after_dev | ⚠️ 待驗證 |
| #3 Governance | `implement/governance/` | monitoring_after_rev | ⚠️ 待驗證 |
| #4 Kill-Switch | `implement/kill_switch/` + `KillSwitchWrapper` | HR-12/13 | ⚠️ 待驗證 |
| #5 LLM Cascade | `implement/llm_cascade/` | monitoring_after_rev | ⚠️ 待驗證 |
| #6 Hunter | `implement/feature-06-hunter/` | monitoring_after_dev | ⚠️ 待驗證 |
| #7 UQLM | `implement/feature-07-uqlm/` + `wave2_features.py::UQLMWrapper` | monitoring_after_dev | ⚠️ 待驗證 |
| #8 Gap Detector | `implement/feature-08-gap-detector/` | monitoring_after_dev | ⚠️ 待驗證 |
| #9 Risk Assessment | `implement/feature-09-risk-assessment/` | postflight | ⚠️ 待驗證 |
| #10 LangGraph | `implement/feature-10-langgraph/` | 選択的（checkpoint/parallel/routing）| ⚠️ 待驗證 |
| #11 Langfuse | `implement/feature-11-langfuse/` + `LangfuseTracer` | 所有鉤子 | ⚠️ 待驗證 |
| #12 Compliance | `implement/feature-12-compliance/` | postflight | ⚠️ 待驗證 |
| #13 Decision Log | `implement/feature-13-observability/.../decision_log.py` + `DecisionLogWriter` | 所有鉤子 | ⚠️ 待驗證 |

**Note**: `adapters/shield.py` 不存在，PromptShieldWrapper 在 `adapters/phase_hooks_adapter.py`。Decision Log 在 `implement/feature-13-observability/03-implement/observability/decision_log.py`。
