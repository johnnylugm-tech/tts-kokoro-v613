# methodology-v2 開發流程用到之組件清單

> **口徑**：以 Plan Phase 1-8 實際引用為準（`.methodology/outputs/Plan_Phase_1~8.md`）
> **Framework 版本**：v9.1 (`af11ee8`)
> **產生日期**：2026-04-24
> **驗證日期**：2026-04-24（已通過逐項驗證）

---

## 驗證摘要

| 類別 | 狀態 | 備註 |
|------|------|------|
| CLI 子命令（存在性） | ✅ 12/12 全數驗證通過 | 全部存在於 cli.py |
| Scripts | ✅ 2/2 驗證通過 | |
| Quality Gate Modules | ✅ 9/9 驗證通過 | |
| Core Modules | ✅ 9/9 驗證通過 | |
| Constitution runner --type | ✅ 9/9 驗證通過 | |
| Templates | ✅ 2/2 驗證通過 | |
| SOP docs | ✅ 8/8 驗證通過 | |

---

## 1. CLI 主工具

### 1.1 cli.py（單一入口）

| 子命令 | 用途 | 驗證 |
|--------|------|------|
| `python3 cli.py run-phase --phase N --goal "..."` | 執行指定 Phase | ✅ P1-P8 全部 |
| `python3 cli.py plan-phase --phase N --repair --step N.N` | 修復特定步驟 | ✅ P1-P8 全部 |
| `python3 cli.py stage-pass --phase N` | 品質閘道通關 | ✅ P1-P8 全部 |
| `python3 cli.py end-phase --phase N` | 結束 Phase | ✅ P1-P8 全部 |
| `python3 cli.py update-step --step N` | 更新目前步驟 | ✅ P1-P8 全部 |
| `python3 cli.py phase-verify --phase N` | Phase Truth 驗證（→ `cmd_phase_truth`） | ✅ **P1-P8 全部** |
| `python3 cli.py trace-check` | 代碼↔SAD 映射率驗證 | ✅ **P1-P5, P7, P8** |
| `python3 cli.py enforce --level BLOCK` | FrameworkEnforcer BLOCK 等級 | ✅ **僅 P3** |
| `python3 cli.py auto-research` | AutoResearch 品質改善 | ✅ **P1-P5, P7, P8** |
| `python3 cli.py quality-gate` | CQG（Linter + Complexity + Coverage） | ✅ **P1-P5, P7, P8** |
| `python3 cli.py verify-artifact` | Verify_Agent 獨立產物驗證 | ✅ **P1-P5, P7, P8** |
| `python3 cli.py steering run --phase N` | Steering Loop 引導 | ✅ **P1-P5, P7, P8** |

---

## 2. Scripts

### 2.1 主要指令稿

| 檔案 | 用途 | CLI 引用 | 驗證 |
|------|------|---------|------|
| `scripts/generate_full_plan.py --phase N --repo /path [--no-output]` | 產生完整 FR 詳細任務 | P1-P8（`--detailed` 模式） | ✅ |
| `scripts/check_fr_full.py --fr FR-XX --project /path [--loop]` | 每個 FR APPROVE 後完整檢查 | P1-P5, P7, P8（四維度表格） | ✅ |

---

## 3. Quality Gate 品質閘道

### 3.1 Constitution 執行器

**檔案**：`quality_gate/constitution/runner.py`

| `--type` 值 | 含義 | **驗證：實際使用 Phase** |
|-------------|------|----------------------|
| `srs` | SRS Constitution 檢查 | P1（與 `implementation` 共同） |
| `sad` | SAD Constitution 檢查 | P2（與 `implementation` 共同） |
| `implementation` | 實作 Constitution 檢查 | **P1, P2, P3, P4, P5, P7, P8**（幾乎全部） |
| `verification` | 驗證 Constitution 檢查 | P5（與 `implementation` 共同） |
| `test_plan` | Test Plan Constitution 檢查 | P4（與 `implementation` 共同） |
| `all` | 全項檢查 | P6（唯一） |
| `quality_report` | Quality Report Constitution | ❌ Plan 未直接引用 |
| `risk_management` | Risk Management Constitution | ❌ Plan 未直接引用 |
| `configuration` | Configuration Constitution | ❌ Plan 未直接引用 |

### 3.2 其他 Quality Gate 模組（Plan 實際引用）

| 檔案 | 用途 | Plan 實際 CLI 引用 |
|------|------|------------------|
| `quality_gate/doc_checker.py` | 規格完整性檢查 | ✅ P1（顯式 QG 命令） |
| `quality_gate/ab_enforcer.py` | A/B Agent 分離驗證（HR-01） | ❌ **未直接CLI呼叫**（僅 HR-01 規則文字） |
| `quality_gate/phase_artifact_enforcer.py` | Phase 交付物強制檢查 | ❌ **未直接CLI呼叫** |
| `quality_gate/coverage_checker.py` | 測試覆蓋率檢查 | ❌ **未直接CLI呼叫** |
| `quality_gate/fr_coverage_checker.py` | FR 覆蓋率檢查 | ❌ **未直接CLI呼叫** |
| `quality_gate/citation_enforcer.py` | Citations 強制（HR-15） | ❌ **未直接CLI呼叫** |
| `quality_gate/claims_verifier.py` | Claims 驗證（HR-09） | ❌ **未直接CLI呼叫** |
| `quality_gate/phase_truth_verifier.py` | Phase Truth 分數驗證 | ❌ **未直接CLI呼叫**（透過 `phase-verify`） |
| `quality_gate/integrity_tracker.py` | Integrity 分數追蹤（HR-14） | ❌ **未直接CLI呼叫** |

---

## 4. 核心模組

### 4.1 Agent 協作與隔離

| 模組 | 用途 | **驗證：Plan 引用次數** |
|------|------|----------------------|
| `agent_spawner.AgentSpawner` | A/B Agent spawn 介面 | HR-01 規則文字（P1-P8 各 5 次） |
| `subagent_isolator.SubagentIsolator` | Subagent 訊息隔離（fresh_messages） | ✅ **P1-P5, P7, P8**（各 8 次）|
| `sessions_spawn_logger.SessionsSpawnLogger` | sessions_spawn.log 記錄 | HR-10 規則文字（P1-P5, P7, P8 各 28 次）|

### 4.2 Phase Hooks 與執行框架

| 模組 | 用途 | **驗證：Plan 引用** |
|------|------|--------------------|
| `phase_hooks.PhaseHooks` | Phase 鉤子點監控（7 個鉤子） | ✅ **P1-P5, P7, P8**（各 1 次）|
| `automation/phase_runner.PhaseRunner` | Phase 自動化執行引擎 | （基礎設施） |
| `hybrid_workflow.HybridWorkflow` | HybridWorkflow mode=ON（A/B 強制） | ✅ **P1-P8 全部**（HR-04 規則）|

### 4.3 Constitution 核心

| 模組 | 用途 | **驗證** |
|------|------|---------|
| `constitution/claim_verifier.ClaimVerifier` | Claims 驗證（HR-09） | ❌ **Plan 未直接引用** |
| `constitution/citation_parser.CitationParser` | Citation 解析 | HR-15 規則文字（P1-P8） |
| `constitution/invariant_engine.InvariantEngine` | 不變量引擎 | HR-09 規則文字 |

### 4.4 Steering 與 Auto-Research

| 模組 | 用途 | **驗證** |
|------|------|---------|
| `steering/steering_loop.SteeringLoop` | Steering Loop 引導 | ✅ P1-P5, P7, P8 |
| `quality_dashboard/auto_research_loop.AutoResearchLoop` | AutoResearch 品質改善 | ✅ P1-P5, P7, P8 |

---

## 5. 模板（Templates）

| 檔案 | 用途 | 驗證 |
|------|------|------|
| `templates/plan_phase_template.md` | Plan Phase 1-5, 7, 8 產生模板 | ✅ |
| `templates/plan_phase_6_template.md` | Plan Phase 6 專用模板 | ✅ |

**Lazy-loaded 執行細節**：
| 檔案 | Phase | 驗證 |
|------|-------|------|
| `docs/P1_SOP.md` | P1 | ✅ |
| `docs/P2_SOP.md` | P2 | ✅ |
| `docs/P3_SOP.md` | P3 | ✅ |
| `docs/P4_SOP.md` | P4 | ✅ |
| `docs/P5_SOP.md` | P5 | ✅ |
| `docs/P6_SOP.md` | P6 | ✅ |
| `docs/P7_SOP.md` | P7 | ✅ |
| `docs/P8_SOP.md` | P8 | ✅ |

---

## 6. Phase 專用產出模板（不透過 CLI 叫用）

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

## 7. Phase 1-8 完整工具使用矩陣（已驗證）

> ⚠️ **重要修正**：已修正初版多項錯誤，下表為驗證後正確版本。

| 工具/模組 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 |
|----------|----|----|----|----|----|----|----|----|
| **CLI 入口** |
| `cli.py run-phase` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py plan-phase` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py stage-pass` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py end-phase` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py update-step` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py phase-verify` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cli.py trace-check` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `cli.py enforce --level BLOCK` | — | — | ✅ | — | — | — | — | — |
| `cli.py auto-research` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `cli.py quality-gate` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `cli.py verify-artifact` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `cli.py steering` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| **Scripts** |
| `generate_full_plan.py` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `check_fr_full.py` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| **Quality Gate** |
| `constitution/runner.py --type srs` | ✅+impl | — | — | — | — | — | — | — |
| `constitution/runner.py --type sad` | — | ✅+impl | — | — | — | — | — | — |
| `constitution/runner.py --type implementation` | ✅+srs | ✅+sad | ✅ | ✅+test_plan | ✅+verification | — | ✅ | ✅ |
| `constitution/runner.py --type test_plan` | — | — | — | ✅ | — | — | — | — |
| `constitution/runner.py --type verification` | — | — | — | — | ✅ | — | — | — |
| `constitution/runner.py --type all` | — | — | — | — | — | ✅ | — | — |
| `quality_gate/doc_checker.py` | ✅ | — | — | — | — | — | — | — |
| **Framework 核心** |
| `ABEnforcer`（HR-01） | 規則 | 規則 | 規則 | 規則 | 規則 | 規則 | 規則 | 規則 |
| `SubagentIsolator` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `HybridWorkflow`（HR-04） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `PhaseHooks` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `ClaimVerifier`（HR-09） | 規則 | 規則 | 規則 | 規則 | 規則 | 規則 | 規則 | 規則 |
| **Sessions Log** |
| `sessions_spawn.log`（HR-10） | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| **pytest** |
| `pytest tests/ -v` | — | — | ✅ | ✅ | — | — | — | — |
| `pytest --cov=03-development/src/` | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |

> **符號說明**：`✅+xxx` = 該 CLI 與另一 type 共同出現。`規則` = 以 HR 規則文字出現（未直接 CLI 呼叫）。

---

## 8. TH 閾值矩陣（已驗證）

| TH | 指標 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 |
|----|------|----|----|----|----|----|----|----|----|
| TH-01 | ASPICE 合規率 >80% | — | — | — | ✅ | — | — | — | — |
| TH-02 | Constitution 總分 ≥80% | — | — | — | — | ✅ | ✅ | ✅ | ⚠️ |
| TH-03 | Constitution 正確性 =100% | ✅ | ✅ | — | ✅ | — | — | — | — |
| TH-04 | Constitution 安全性 =100% | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| TH-05 | Constitution 可維護性 >90% | — | ✅ | — | ✅ | — | — | — | — |
| TH-06 | Constitution 測試覆蓋率 >90% | — | — | ✅ | ✅ | — | — | — | — |
| TH-07 | 邏輯正確性分數 ≥90 | — | — | — | — | ✅ | ✅ | ✅ | — |
| TH-08 | AgentEvaluator 標準 ≥80 | ✅ | ✅ | — | — | — | — | — | — |
| TH-09 | AgentEvaluator 嚴格 ≥90 | — | — | ✅ | — | — | — | — | — |
| TH-10 | 測試通過率 =100% | — | — | ✅ | ✅ | — | — | — | — |
| TH-11 | 單元測試覆蓋率 ≥70% | — | — | ✅ | — | — | — | — | — |
| TH-12 | 單元測試覆蓋率 ≥80% | — | — | — | ✅ | — | — | — | — |
| TH-13 | SRS FR 覆蓋率 =100% | — | — | — | ✅ | ✅ | ✅ | ✅ | — |
| TH-14 | 規格完整性 =100% | ✅ | — | — | — | — | — | — | — |
| TH-15 | Phase Truth >90% | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| TH-16 | 代碼↔SAD 映射率 =100% | — | — | ✅ | — | — | — | — | — |
| TH-17 | FR↔測試 ≥90% | — | — | — | ✅ | — | — | — | — |

> ⚠️ P8：TH-02 在 TH 表頭；TH-15 在 Phase Truth POST-FLIGHT 區塊（`phase-verify` 驗證），但不在 TH compact header 表格。

---

## 9. 初版文件錯誤更正記錄

| 錯誤項目 | 初版內容 | 正確內容 |
|---------|---------|---------|
| `auto-research` | 僅 P3,P4,P7,P8 | **P1,P2,P3,P4,P5,P7,P8**（P6 除外） |
| `verify-artifact` | 僅 P3 | **P1,P2,P3,P4,P5,P7,P8**（P6 除外） |
| `quality-gate` | 僅 P6 | **P1,P2,P3,P4,P5,P7,P8**（P6 除外） |
| `phase-verify` | P3,P4,P6 | **P1-P8 全部** |
| `trace-check` | P3,P4 | **P1,P2,P3,P4,P5,P7,P8**（P6 除外） |
| `steering` | P7,P8 | **P1,P2,P3,P4,P5,P7,P8**（P6 除外） |
| `ABEnforcer`（CLI） | P3 | **—（未直接CLI呼叫，僅 HR-01 規則文字）** |
| `SubagentIsolator` | P3,P4 | **P1,P2,P3,P4,P5,P7,P8**（P6 除外） |
| `PhaseHooks` | P3,P4,P7,P8 | **P1,P2,P3,P4,P5,P7,P8**（P6 除外） |
| `ClaimVerifier`（CLI） | P3 | **—（未直接CLI呼叫）** |
| `citation_enforcer`（CLI） | P3 | **—（未直接CLI呼叫）** |
| `phase_artifact_enforcer`（CLI） | P3 | **—（未直接CLI呼叫）** |
| `fr_coverage_checker`（CLI） | P4 | **—（未直接CLI呼叫）** |
| `check_fr_full.py` | P2,P3,P4,P5,P7,P8 | **P1,P2,P3,P4,P5,P7,P8**（P6 除外） |
| Constitution `srs` | P1 | P1 **+ P1 有 `implementation`** |
| Constitution `sad` | P2 | P2 **+ P2 有 `implementation`** |
| Constitution `implementation` | P3 | **幾乎全部（P1-P5, P7, P8）** |
| Constitution `verification` | P5 | P5 **+ P5 有 `implementation`** |
| Constitution `test_plan` | — | **P4（+ `implementation`）** |
| `quality_gate/doc_checker.py` | P1 | ✅ 正確 |

---

## 10. 關鍵觀察

1. **P6 是最特殊的 Phase**：幾乎不呼叫任何額外工具（除了 `phase-verify` 和 `constitution/runner.py --type all`），有獨立的完整驗收流程。

2. **多數工具（P1-P5, P7, P8）共享相同的工具集合**，差異僅在於 `constitution/runner.py --type` 的具體 type 值。

3. **HR 規則文字 ≠ 實際 CLI 呼叫**：多個 QG 模組（`ab_enforcer`, `citation_enforcer`, `phase_artifact_enforcer`, `claims_verifier`）出現在 HR 規則說明中，但從未作為獨立的 CLI 命令被真正呼叫。

4. **`HybridWorkflow` 是真正的 HR-01 執行機制**（P1-P8 全部），而非 `ab_enforcer.py`（從未作為 CLI 呼叫）。

5. **Phase Truth（TH-15）是全 Phase 統一機制**，透過 `cli.py phase-verify` 在所有 Phase 執行。
