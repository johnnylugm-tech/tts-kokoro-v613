# methodology-v2 開發流程用到之組件清單

> **口徑**：以 Plan Phase 1-8 實際引用為準（`.methodology/outputs/Plan_Phase_1~8.md`）
> **Framework 版本**：v9.1 (`af11ee8`)
> **產生日期**：2026-04-24

---

## 1. CLI 主工具

### 1.1 cli.py（單一入口）

| 子命令 | 用途 | Plan Phase |
|--------|------|-----------|
| `python3 cli.py run-phase --phase N --goal "..."` | 執行指定 Phase | 1-8 全部 |
| `python3 cli.py plan-phase --phase N --repair --step N.N` | 修復特定步驟 | 1-8 全部 |
| `python3 cli.py stage-pass --phase N` | 品質閘道通關 | 1-8 全部 |
| `python3 cli.py end-phase --phase N` | 結束 Phase | 1-8 全部 |
| `python3 cli.py update-step --step N` | 更新目前步驟 | 1-8 全部 |
| `python3 cli.py phase-verify --phase N` | Phase Truth 驗證（→ `cmd_phase_truth`） | 3, 4, 6 |
| `python3 cli.py trace-check` | 代碼↔SAD 映射率驗證 | 3, 4 |
| `python3 cli.py enforce --level BLOCK` | FrameworkEnforcer BLOCK 等級 | 3 |
| `python3 cli.py auto-research` | AutoResearch 品質改善 | 3, 4, 7 |
| `python3 cli.py quality-gate` | 品質閘道整合入口 | 6 |
| `python3 cli.py verify-artifact` | 獨立產物驗證（Verify_Agent） | 3 |
| `python3 cli.py steering` | Steering Loop 引導 | 7, 8 |

---

## 2. Scripts

### 2.1 主要指令稿

| 檔案 | 用途 | Plan Phase |
|------|------|-----------|
| `scripts/generate_full_plan.py --phase N --repo /path [--no-output]` | 產生完整 FR 詳細任務 | 1-8 全部（`--detailed` 模式） |
| `scripts/check_fr_full.py --fr FR-XX --project /path [--loop]` | 每個 FR APPROVE 後完整檢查（三層：輕量→Constitution→CQG） | 2, 3, 4, 5, 7, 8 |

### 2.2 其他腳手架

| 檔案 | Plan 是否有引用 |
|------|----------------|
| `scripts/bump_version.py` | ❌ |
| `scripts/check_fr_quality.py` | ❌ |
| `scripts/cron_docs_optimizer.py` | ❌ |
| `scripts/cron_drift_monitor.py` | ❌ |
| `scripts/dev_log_checker.py` | ❌ |
| `scripts/drift_crontab.example` | ❌ |
| `scripts/generate_fr_mapping.py` | ❌ |
| `scripts/generate_sab.py` | ❌ |
| `scripts/phase_auditor.py` | ❌ |
| `scripts/spec_logic_checker.py` | ❌ |
| `scripts/state_monitor.py` | ❌ |
| `scripts/verify_path_consistency.py` | ❌ |
| `scripts/verify_spec_compliance.py` | ❌ |

---

## 3. Quality Gate 品質閘道

### 3.1 Constitution 執行器

**檔案**：`quality_gate/constitution/runner.py`

| `--type` 值 | 含義 | Plan Phase |
|-------------|------|-----------|
| `srs` | SRS Constitution 檢查 | 1 |
| `sad` | SAD Constitution 檢查 | 2 |
| `implementation` | 實作 Constitution 檢查 | 3 |
| `verification` | 驗證 Constitution 檢查 | 5 |
| `test_plan` | Test Plan Constitution 檢查 | — |
| `quality_report` | Quality Report Constitution 檢查 | — |
| `risk_management` | Risk Management Constitution 檢查 | — |
| `configuration` | Configuration Constitution 檢查 | — |
| `all` | 全項檢查 | 6 |

**相關 Constitution 模組**（`quality_gate/constitution/`）：
- `srs_constitution_checker.py`
- `sad_constitution_checker.py`
- `implementation_constitution_checker.py`
- `verification_constitution_checker.py`
- `hr09_checker.py`（HR-09 Claims Verifier）
- `phase_prerequisite_checker.py`
- `integrity_constitution_checker.py`
- `quality_report_constitution_checker.py`
- `risk_management_constitution_checker.py`
- `configuration_constitution_checker.py`

### 3.2 其他 Quality Gate 模組

| 檔案 | 用途 | Plan Phase |
|------|------|-----------|
| `quality_gate/doc_checker.py` | 規格完整性檢查 | 1 |
| `quality_gate/ab_enforcer.py` | A/B Agent 分離驗證（HR-01） | 3 |
| `quality_gate/phase_artifact_enforcer.py` | Phase 交付物強 制檢查 | 3 |
| `quality_gate/coverage_checker.py` | 測試覆蓋率檢查 | 3, 4 |
| `quality_gate/fr_coverage_checker.py` | FR 覆蓋率檢查 | 4 |
| `quality_gate/citation_enforcer.py` | Citations 強制（HR-15） | 3 |
| `quality_gate/claims_verifier.py` | Claims 驗證（HR-09） | 3 |
| `quality_gate/phase_truth_verifier.py` | Phase Truth 分數驗證 | 3, 4 |
| `quality_gate/integrity_tracker.py` | Integrity 分數追蹤（HR-14） | 3, 4 |

---

## 4. 核心模組（直接 import 使用）

### 4.1 Agent 協作與隔離

| 模組 | 用途 | Plan Phase |
|------|------|-----------|
| `agent_spawner.AgentSpawner` | A/B Agent spawn 介面 | 3, 4（HR-01） |
| `subagent_isolator.SubagentIsolator` | Subagent 訊息隔離（fresh_messages） | 3, 4（HR-10） |
| `sessions_spawn_logger.SessionsSpawnLogger` | sessions_spawn.log 記錄 | 3, 4（HR-10） |

### 4.2 Phase Hooks 與執行框架

| 模組 | 用途 | Plan Phase |
|------|------|-----------|
| `phase_hooks.PhaseHooks` | Phase 鉤子點監控（7 個鉤子） | 3, 4, 7, 8 |
| `automation/phase_runner.PhaseRunner` | Phase 自動化執行引擎 | 3, 4, 7, 8 |
| `hybrid_workflow.HybridWorkflow` | HybridWorkflow mode=ON（A/B 強制） | 3（HR-04） |

### 4.3 Constitution 核心（不透過 runner.py 直接呼叫）

| 模組 | 用途 | Plan Phase |
|------|------|-----------|
| `constitution/claim_verifier.ClaimVerifier` | Claims 驗證（HR-09） | 3 |
| `constitution/citation_parser.CitationParser` | Citation 解析 | 3, 4 |
| `constitution/invariant_engine.InvariantEngine` | 不變量引擎 | 5, 6 |

### 4.4 追蹤與可追溯性

| 模組 | 用途 | Plan Phase |
|------|------|-----------|
| `traceability_matrix.TraceabilityMatrix` | FR↔SAD 追溯矩陣 | 3, 4（TH-16） |
| `requirement_traceability.RequirementTraceability` | 需求可追溯性 | 1, 2 |

### 4.5 Steering 與 Auto-Research

| 模組 | 用途 | Plan Phase |
|------|------|-----------|
| `steering/steering_loop.SteeringLoop` | Steering Loop 引導 | 7, 8 |
| `quality_dashboard/auto_research_loop.AutoResearchLoop` | AutoResearch 品質改善 | 3, 4, 7 |

---

## 5. 模板（Templates）

| 檔案 | 用途 | Plan Phase |
|------|------|-----------|
| `templates/plan_phase_template.md` | Plan Phase 1-5, 7, 8 產生模板 | 1, 2, 3, 4, 5, 7, 8 |
| `templates/plan_phase_6_template.md` | Plan Phase 6 專用模板 | 6 |

**Lazy-loaded 執行細節**：
| 檔案 | 用途 | Plan Phase |
|------|------|-----------|
| `docs/P1_SOP.md` | Phase 1 執行 SOP | 1 |
| `docs/P2_SOP.md` | Phase 2 執行 SOP | 2 |
| `docs/P3_SOP.md` | Phase 3 執行 SOP | 3 |
| `docs/P4_SOP.md` | Phase 4 執行 SOP | 4 |
| `docs/P5_SOP.md` | Phase 5 執行 SOP | 5 |
| `docs/P6_SOP.md` | Phase 6 執行 SOP | 6 |
| `docs/P7_SOP.md` | Phase 7 執行 SOP | 7 |
| `docs/P8_SOP.md` | Phase 8 執行 SOP | 8 |

---

## 6. Phase 專用模板（不透過 CLI 叫用的產出模板）

| 檔案 | 用途 |
|------|------|
| `templates/SRS.md` | SRS 文件模板（Phase 1 產出） |
| `templates/SAD.md` | SAD 文件模板（Phase 2 產出） |
| `templates/SPEC_TRACKING.md` | 規格變更追蹤模板 |
| `templates/TRACEABILITY_MATRIX.md` | FR 追溯矩陣模板 |
| `templates/TEST_PLAN.md` | 測試計畫模板（Phase 4） |
| `templates/QUALITY_REPORT.md` | 品質報告模板（Phase 5） |
| `templates/RISK_REGISTER.md` | 風險登記表模板 |
| `templates/BASELINE.md` | 基準線模板 |
| `templates/DEPLOYMENT.md` | 部署計畫模板（Phase 8） |
| `templates/MONITORING_PLAN.md` | 監控計畫模板 |
| `templates/ADR.md` | ADR（架構決策記錄）模板 |
| `templates/PROJECT_STRUCTURE.md` | 專案結構定義模板 |
| `templates/CONFIG_RECORDS.md` | 配置記錄模板 |

---

## 7. Phase 1-8 完整工具使用矩陣

| 工具/模組 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 |
|----------|----|----|----|----|----|----|----|----|
| **CLI 入口** |||||||||
| `cli.py run-phase` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py plan-phase` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py stage-pass` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py end-phase` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py update-step` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py phase-verify` | — | — | ✅ | ✅ | — | ✅ | — | — |
| `cli.py trace-check` | — | — | ✅ | ✅ | — | — | — | — |
| `cli.py enforce` | — | — | ✅ | — | — | — | — | — |
| `cli.py auto-research` | — | — | ✅ | ✅ | — | — | ✅ | ✅ |
| `cli.py verify-artifact` | — | — | ✅ | — | — | — | — | — |
| `cli.py steering` | — | — | — | — | — | — | ✅ | ✅ |
| **Scripts** |||||||||
| `generate_full_plan.py` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `check_fr_full.py` | — | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| **Quality Gate** |||||||||
| `constitution/runner.py --type srs` | ✅ | — | — | — | — | — | — | — |
| `constitution/runner.py --type sad` | — | ✅ | — | — | — | — | — | — |
| `constitution/runner.py --type implementation` | — | — | ✅ | — | — | — | — | — |
| `constitution/runner.py --type verification` | — | — | — | — | ✅ | — | — | — |
| `constitution/runner.py --type all` | — | — | — | — | — | ✅ | — | — |
| `quality_gate/doc_checker.py` | ✅ | — | — | — | — | — | — | — |
| **Framework 核心** |||||||||
| `ABEnforcer` | — | — | ✅ | — | — | — | — | — |
| `SubagentIsolator` | — | — | ✅ | ✅ | — | — | — | — |
| `HybridWorkflow` | — | — | ✅ | — | — | — | — | — |
| `PhaseHooks` | — | — | ✅ | ✅ | — | — | ✅ | ✅ |
| `ClaimVerifier` | — | — | ✅ | — | — | — | — | — |
| **pytest** |||||||||
| `pytest tests/ -v` | — | — | ✅ | ✅ | — | — | — | — |
| `pytest --cov=03-development/src/` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| **Sessions Log** |||||||||
| `sessions_spawn.log` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |

---

## 8. Plan Phase 各自的 Quality Gate 閾值（TH）

| TH | 指標 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 |
|----|------|----|----|----|----|----|----|----|----|
| TH-01 | ASPICE 合規率 >80% | — | — | — | — | — | — | — | — |
| TH-02 | Constitution 總分 ≥80% | — | — | — | — | ✅ | ✅ | ✅ | ✅ |
| TH-03 | Constitution 正確性 =100% | ✅ | ✅ | — | ✅ | — | — | — | — |
| TH-04 | Constitution 安全性 =100% | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| TH-05 | Constitution 可維護性 >90% | — | ✅ | — | — | — | — | — | — |
| TH-06 | Constitution 測試覆蓋率 >90% | — | — | ✅ | ✅ | — | — | — | — |
| TH-07 | 邏輯正確性分數 ≥90 | — | — | — | — | ✅ | ✅ | ✅ | — |
| TH-08 | AgentEvaluator 標準 ≥80 | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| TH-09 | AgentEvaluator 嚴格 ≥90 | — | — | ✅ | — | — | — | — | — |
| TH-10 | 測試通過率 =100% | — | — | ✅ | ✅ | — | — | — | — |
| TH-11 | 單元測試覆蓋率 ≥70% | — | — | ✅ | — | — | — | — | — |
| TH-12 | 單元測試覆蓋率 ≥80% | — | — | — | ✅ | — | — | — | — |
| TH-13 | SRS FR 覆蓋率 =100% | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| TH-14 | 規格完整性 =100% | ✅ | — | — | — | — | — | — | — |
| TH-15 | Phase Truth >90% | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| TH-16 | 代碼↔SAD 映射率 =100% | — | — | ✅ | — | — | — | — | — |
| TH-17 | FR↔測試 ≥90% | — | — | — | ✅ | — | — | — | — |

---

## 9. 總體積壓模組盤點

以下為 **Plan 未引用但存在於 methodology-v2 的模組**（可能為預留功能或跨版本殘留）：

| 目錄/類別 | 模組數 | Plan 有無引用 |
|-----------|--------|-------------|
| `implement/feature-06-hunter/` | 10 | ❌ |
| `implement/feature-07-uqlm/` | 11 | ❌ |
| `implement/feature-08-gap-detector/` | 4 | ❌ |
| `implement/feature-09-risk-assessment/` | 11 | ❌ |
| `implement/feature-10-langgraph/` | 9 | ❌ |
| `implement/feature-11-langfuse/` | 5 | ❌ |
| `implement/feature-12-compliance/` | 6 | ❌ |
| `implement/feature-13-observability/` | 4 | ❌ |
| `implement/governance/` | 7 | ❌ |
| `implement/kill_switch/` | 7 | ❌ |
| `implement/llm_cascade/` | 14 | ❌ |
| `implement/mcp/` | 2 | ❌ |
| `implement/security/` | 3 | ❌ |
| `adapters/` | 6 | ❌（PhaseHooks Adapter 是例外） |
| `ralph_mode/` | 11 | ❌ |
| `agent_memory/` | 3 | ❌ |
| `core/feedback/` | 12 | ❌ |
| `core/self_correction/` | 10 | ❌ |
| `core/quality_gate/` | 1 | ❌ |
| `quality_gate/` 其餘模組（不含 runner.py/doc_checker.py） | ~50 | ❌ |

**Plan 有明確引用的核心模組**（共計約 15-20 個）：
1. `cli.py`（主入口）
2. `scripts/generate_full_plan.py`
3. `scripts/check_fr_full.py`
4. `quality_gate/constitution/runner.py`
5. `quality_gate/doc_checker.py`
6. `quality_gate/ab_enforcer.py`
7. `agent_spawner`
8. `subagent_isolator`
9. `sessions_spawn_logger`
10. `phase_hooks`
11. `hybrid_workflow`
12. `constitution/claim_verifier`
13. `constitution/citation_parser`
14. `constitution/invariant_engine`
15. `steering/steering_loop`
16. `quality_dashboard/auto_research_loop`
17. `traceability_matrix`
18. `requirement_traceability`

---

## 10. 總結

- **Plan Phase 1-8 實際使用的 Framework 組件非常集中**：主要依賴 `cli.py`（8 個子命令）+ `quality_gate/constitution/runner.py`（6 種 type）+ `scripts/`（2 個指令稿）+ 少量核心 Agent/Constitution 模組。
- **龐大的 `implement/feature-XX/` 系列（Feature 6-13）完全未在任何 Plan 中被引用**，這些是 PhaseHooks Adapter 預留的觀測點，但 plan-phase 和 run-phase 的 actual tooling 不涉及這些模組。
- **`quality_gate/` 下 50+ 模組中，Plan 實際呼叫的只有 `runner.py` 和 `doc_checker.py`**，其餘為內部 Quality Gate 基礎設施。
- Framework 目前的 **plan-phase 是"模板置換"模式**，真正動態的只有 `_parse_srs_fr_list` / `_parse_sad_modules` / `_generate_fr_table` 三個 parsing 函式，實際執行仍高度依賴 CLI 命令。
