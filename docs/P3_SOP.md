# Phase 3 SOP — 代碼實作

> 本檔案為 On-demand Lazy Load 檔案，僅在執行 Phase 3 時載入。
> 基於：SKILL.md v6.26 + PLAN_PHASE_SPEC.md

> **核心理念**：工具不缺，缺的是紀律。主代理 = 專案經理，Sub-agent = 執行者。

---

## 單一入口：run-phase（v6.26 新增）

> ⚠️ **所有 Phase 執行必須經過此入口**，不可繞過。

```bash
python cli.py run-phase --phase 3
python cli.py run-phase --phase 3 --step 3.1 --task "FR-01 實作"
```

### run-phase 執行流程

```
┌─────────────────────────────────────────────────────────────┐
│  Johnny: 「執行 Phase 3」                                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  PRE-FLIGHT CHECKS（強制，不通過就停止）                       │
│                                                             │
│  1. FSM State Check → FREEZE/PAUSED 阻擋                    │
│  2. Phase Sequence → 不可跳過 Phase                          │
│  3. Constitution Check → <80% 阻擋                           │
│  4. Tool Registry Check → 工具狀態                            │
│  5. Session Save → Pre-flight 存檔                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    ✅ 全部通過
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  EXECUTE                                                     │
│  6. Load docs/P3_SOP.md                                      │
│  7. Execute steps via SubagentIsolator (不直接 sessions_spawn)│
│  8. PermissionGuard.check() before exec/rm                  │
│  9. Log to .methodology/run-phase.log                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  POST-FLIGHT                                                 │
│  10. Final Constitution Check                                │
│  11. Update state.json                                       │
│  12. Report Summary                                          │
└─────────────────────────────────────────────────────────────┘
```

### run-phase 合規宣言

```
本命令：
- ✅ 調用 SubagentIsolator.spawn()，不直接用 sessions_spawn
- ✅ 讀取 state.json 並服從 FSM 狀態
- ✅ Pre-flight 失敗時停在 Pre-flight，不進入執行
- ✅ Post-flight 自動執行 Constitution check
- ✅ HR-12/13/14 觸發時自動服從（pause/freeze）
- ❌ 不繞過任何 HR 規則
- ❌ 不跳過 Phase 順序
```

---

## 核心參考

- **Main Agent Playbook**：`methodology-v2/docs/MAIN_AGENT_PLAYBOOK.md`（v6.26）
- **v6.26 單一入口**：`run-phase`（所有 Phase 執行必經）
- **v6.22 新工具**：KnowledgeCurator / ContextManager / SubagentIsolator / PermissionGuard / ToolRegistry / SessionManager / Enhanced Exceptions

---

## Sub-Agent 管理原則

### On Demand / Need to Know

| 原則 | 實踐 |
|------|------|
| **Need to Know** | 只給必要資訊（L1/NFR 在被問時再提供）|
| **On Demand** | Sub-agent 自己讀 artifact paths，不主動 dump |
| **職責單一** | 每個 Sub-agent 只做一件事 |
| **結構化溝通** | JSON/Pydantic 產出格式，强制 confidence + citations |

---

## 四大工具定位

| 工具 | 解決的問題 | 觸發時機 |
|------|-----------|---------|
| `KnowledgeCurator` | 知識一致性 | **派遣前**（驗證 FR 覆蓋率）|
| `ContextManager` | 上下文膨脹 | **派遣後**（context > 50 時）|
| `SubagentIsolator` | 結果污染 / 合併混亂 | **派遣時**（嚴格隔離）|
| `PermissionGuard` | 危險操作失控 | **任何時刻**（exec / rm 前）|

---

## 產出格式標準（Sub-Agent 必須遵守）

```json
{
  "status": "success | error | unable_to_proceed",
  "result": "實際產出",
  "confidence": 1-10,
  "citations": ["FR-01", "SRS.md#section"],
  "summary": "50 字內摘要"
}
```

### citations 強制格式（HR-15）

```json
{
  "citations": [
    "FR-01",
    "SRS.md#L23-L45",
    "SAD.md#§Module-1"
  ],
  "artifact_verification": {
    "SRS.md": "已讀 §FR-01",
    "SAD.md": "已讀 §Module-1"
  }
}
```

**規定**：
- citations 必須包含檔案名 + 行號或段落
- artifact_verification 必須列出所有已讀的 artifact
- 若無 artifact_verification，視為 HR-15 違規

| 分數 | 意義 | 動作 |
|------|------|------|
| 9-10 | 高度確定，有引用 | 繼續 |
| 7-8 | 確定，無引用 | 標記，繼續 |
| 5-6 | 不確定 | 重新派遣 |
| 1-4 | 嚴重懷疑 | 上報 Johnny |

---

### 每個 FR 的最小執行單位

| Step | 角色 | 動作 |
|------|------|------|
| N.1 | Developer | 代碼實作 → commit |
| N.2 | Developer | 測試實作 → commit |
| N.3 | Reviewer | 代碼 + 測試 審查 → APPROVE/REJECT |

**sessions_spawn.log 每 FR 3 筆記錄**：
- developer → FR-0X Code
- developer → FR-0X Tests
- reviewer → FR-0X Review

## 完整工作流（6+3 步）

### Step 0: 派遣前驗證（KnowledgeCurator）

```
1. Johnny 說任務
       ↓
2. KnowledgeCurator.load_skill("methodology-v2")
       ↓
3. KnowledgeCurator.verify_coverage(["FR-01", "FR-02", ...])
       ↓
4. 若覆蓋率 < 90% → 報警，拒絕開始
       ↓
5. ContextManager.create_task(task_id, title, dependencies)
```

### Step 1: 派遣（SubagentIsolator）

**Prompt 只給這四樣**：

```
1. 任務名稱：FR-01 LexiconMapper
2. TaskContext ID：task-001
3. Artifact paths：
   - SRS.md
   - 02-architecture/SAD.md
   - SKILL.md
4. 禁止事項（少數關鍵）：
   - ❌ @covers: L1 Error（應寫 @covers: FR-0X）
   - ❌ @type: edge（應寫 positive/negative/boundary）
   - ❌ 省略任何內容（視為任務失敗）
5. 產出格式（JSON）：
   {status, result, confidence, citations, summary}
```

**SubagentIsolator.spawn()**：
```python
result = si.spawn(
    role=AgentRole.DEVELOPER,
    task="Implement FR-01 LexiconMapper",
    context={
        "task_id": "task-001",
        "artifact_paths": ["SRS.md", "SAD.md", "SKILL.md"],
        "forbidden": ["03-development/src/infrastructure/", "03-development/src/processing/", "03-development/src/synth/", "03-development/src/cache/", "03-development/src/audio/", "03-development/src/api/", "03-development/src/backend/", "@covers: L1 Error"]
    },
    timeout=600
)
```

### Step 2: Sub-agent 執行中（主代理被動）

```
Sub-agent 執行中：
- 不主動介入
- 若 Sub-agent 問：「L1 錯誤設計是什麼？」→ 提供
- 若 Sub-agent 問：「NFR-02 約束是？」→ 提供
- 若 Sub-agent 偏離任務 → 糾正
- 若 confidence < 6 → 準備重新派遣
```

### Step 3: 派遣後檢查（ContextManager）

```
每次工具回傳後：
- 若 context_length > 200 → ContextManager.compress(level="L3")
- 若 context_length > 100 → ContextManager.compress(level="L2")
- 若 context_length > 50  → ContextManager.compress(level="L1")
```

**三層壓縮明確門檻**：

| 等級 | 觸發條件 | 效果 |
|------|---------|------|
| L1 | context_length > 50 | 摘要最後 50 條，拋棄其餘 |
| L2 | context_length > 100 | 提取關鍵資訊（FR、架構、決策），拋棄細節 |
| L3 | context_length > 200 | 存檔到 `.methodology/archives/`，新建乾淨 context |

### Step 4: 結果驗收

```
1. 檢查 confidence < 6？
   - 是 → 重新派遣（最多 3 次）
   - 否 → 繼續
       ↓
2. 本地驗證：
   - pytest 100% passed
   - coverage ≥ 70%
   - NFR-02 約束滿足
       ↓
3. 若通過 → 派遣 Reviewer
       ↓
4. Reviewer APPROVE → commit → 繼續下一個
   Reviewer REJECT → 修復 → re-verify → re-spawn
```

### Step 5: 危險把關（PermissionGuard）

```
任何 exec / rm / network 前：
PermissionGuard.check(Operation(...))
       ↓
DENIED → 立即停止
PENDING → 等待審批（最多 30 秒）
BLOCKED → 全面停止，觸發 HR-14
```

### Step 6: 長期任務保存（SessionManager）

```
預計任務超過 30 分鐘：
       ↓
session-save --id <session_name>
       ↓
中斷後可還原：
session-load --id <session_name>
```

**CLI 命令**：
```bash
# 保存當前 session state
python cli.py session-save --id fr01-impl --state .methodology/session_state.json

# 列出所有 saved sessions
python cli.py session-list

# 還原指定 session
python cli.py session-load --id fr01-impl --output restored_state.json

# 刪除廢棄 session
python cli.py session-delete --id fr01-impl
```

### Step 7: 工具註冊（ToolRegistry）

```
新工具引入前：
       ↓
ToolRegistry.register("NewTool", new_tool_handler)
       ↓
日後統一調用：
ToolRegistry.dispatch("NewTool", **kwargs)
```

**CLI 命令**：
```bash
# 列出所有已註冊工具
python cli.py tool-registry --list

# 查詢特定工具
python cli.py tool-registry --get NewTool

# 分發調用
python cli.py tool-registry --dispatch NewTool --kwargs key=value
```

### Step 8: 錯誤處理（Enhanced Exceptions）

```
遇到錯誤時：
       ↓
try:
    # 操作
except MethodologyError as e:
    print(e.suggest_fix())  # 自動取得修復建議
       ↓
具體異常類型：
- PhaseTransitionError → Phase 轉換失敗
- ToolExecutionError     → 工具執行失敗
- ConstitutionViolationError → Constitution 違規
- IntegrityError        → Integrity < 40，HR-14
- AgentSpawnError       → Sub-agent 派遣失敗
```

---

## Reviewer 派遣

**Prompt 只給**：

```
1. 任務名稱：Review FR-01 LexiconMapper
2. TaskContext ID：task-001
### Artifact paths 說明

> ⚠️ 注意：Convention 標準使用 `03-development/src/` 作為 Phase 3 代碼目錄。
> 實際專案若使用不同結構（如 `app/`），應在 Phase 2 SAD 中明確定義，並在 Phase 3 執行時嚴格遵守。

3. Artifact paths（Convention 標準）：
   - 03-development/src/processing/lexicon_mapper.py
   - 03-development/tests/test_fr01_lexicon.py
   - SRS.md（用於對照規格）
4. 禁止事項：
   - ❌ 沒有 @FR annotation → REJECT
   - ❌ NFR-02 約束違背 → REJECT
   - ❌ confidence < 6 → REJECT
   - ❌ 缺少 citations → REJECT
5. 產出格式：
   {status: APPROVE/REJECT, confidence, violations, summary}
```

---

## 禁止事項（Sub-Agent Prompt 必含）

```
❌ 禁止省略任何內容（...、請自行填寫視為任務失敗）
❌ 禁止在未確認的情況下聲稱完成
❌ 禁止回傳無法驗證的引用
❌ 禁止在 LLM 無法達成時編造答案（應回傳 UNABLE_TO_PROCEED）
```

---

## 健康度檢查清單（每次 Heartbeat）

```
□ active_subagents 是否有超時 session？（> timeout）
□ context_length > 50？（是 → ContextManager.compress(level="L1/L2/L3")）
□ pending_approval 是否有待審批危險操作？
□ Sub-agent confidence 是否 < 6？
□ integrity_score 是否 < 0.7？
□ 長期任務是否已 session-save？
□ 新工具是否已 ToolRegistry.register？
□ 遇到錯誤是否已呼叫 suggest_fix()？
```

---

## sessions_spawn.log 格式

```json
{"timestamp":"{ISO8601}","role":"{developer|reviewer}","task":"FR-0X {Name}","session_id":"{uuid}","confidence":8}
```

---

## Pre-Execution Checklist

| # | 檢查項目 | 工具 |
|---|---------|------|
| 1 | KnowledgeCurator.verify_coverage() 已執行 | KnowledgeCurator |
| 2 | ContextManager.create_task() 已執行 | ContextManager |
| 3 | Artifact paths 已確認 | — |
| 4 | Forbidden 事項已定義 | — |
| 5 | 產出格式已定義 | — |
| 6 | sessions_spawn.log 已寫入（spawn 前）| SubagentIsolator |
| 7 | state.json 已更新（update-step CLI）| CLI |
| 8 | 長期任務已 session-save | SessionManager |
| 9 | 新工具已 ToolRegistry.register | ToolRegistry |

---

## 常見錯誤

### ❌ 錯誤：一次 dump 所有資訊

```
Prompt 塞入：SRS 全文 + SAD 全文 + L1-L6 + NFR-01~10 + 禁止事項 20 條
→ 冗長，干擾任務，違背 Need to Know
```

### ✅ 正確：On Demand

```
Prompt 只有：任務名稱 + TaskContext ID + artifact_paths + 禁止事項 + 產出格式
→ Sub-agent 自己讀需要的檔案
→ 有問題才問
```

### ❌ 錯誤：Raw sessions_spawn 而非 SubagentIsolator

```python
# 錯誤
sessions_spawn(task="...", mode="run")

# 正確
si = SubagentIsolator()
result = si.spawn(role=AgentRole.DEVELOPER, task="...", context={...}, timeout=600)
```

### ❌ 錯誤：Raw exec 而非 PermissionGuard

```python
# 錯誤
exec("rm -rf /tmp/build")

# 正確
pg = PermissionGuard()
result = pg.check(Operation(type="exec", permission=Permission.EXEC_BASH, target="rm -rf /tmp/build"))
if result.status == ApprovalStatus.DENIED:
    raise ToolExecutionError("危險操作被拒", {"tool": "rm", "target": "/tmp/build"})
```

### ❌ 錯誤：遇到錯誤只說「失敗了」

```python
# 錯誤
except Exception as e:
    print("失敗了")

# 正確
except MethodologyError as e:
    print(e.suggest_fix())  # 自動修復建議
```

---

## Phase 3 Quality Gate

| Threshold | 標準 | 工具 | 備註 |
|-----------|------|------|------|
| TH-06 | Constitution ≥ 80% | constitution runner | Phase 3 Constitution 門檻 |
| TH-09 | AgentEvaluator 嚴格 ≥90 | agent_evaluator | Phase 3-8 嚴格標準（TH-09，非 TH-08）|
| TH-10 | 測試通過率 =100% | pytest | Phase 3-8 統一門檻 |
| TH-11 | 單元測試覆蓋率 ≥70% | pytest --cov | Phase 3 模組覆蓋 |
| TH-15 | Phase Truth ≥70% | phase-verify | HR-11 進階條件 |
| TH-16 | SAD↔代碼映射 =100% | trace-check | Phase 3 SAD→代碼對照 |

---

## v6.22 新工具速查

### ToolRegistry（新）

```python
from tool_registry import ToolRegistry

# 註冊
ToolRegistry.register("MyTool", my_handler)

# 分發
ToolRegistry.dispatch("MyTool", arg1=value1, arg2=value2)

# 查詢
handler = ToolRegistry.get_handler("MyTool")

# 列出
all_tools = ToolRegistry.list_tools()

# 取消
ToolRegistry.unregister("MyTool")
```

### SessionManager（新）

```python
from checkpoint_manager import SessionManager

sm = SessionManager()

# 保存
sm.save("my-session", state_dict)

# 還原
state = sm.load("my-session")

# 列出
sessions = sm.list()

# 刪除
sm.delete("my-session")
```

### Enhanced Exceptions（新）

```python
from exceptions import (
    MethodologyError,
    PhaseTransitionError,
    ToolExecutionError,
    ConstitutionViolationError,
    IntegrityError,
    AgentSpawnError,
)

# 拋出具體異常
raise PhaseTransitionError(
    "Phase 2→3 失敗",
    {"current_phase": 2, "target_phase": 3}
)
# → "Phase 2 → 3 轉換失敗。請檢查是否滿足進入條件。"

raise IntegrityError(
    "Integrity過低",
    {"integrity_score": 35}
)
# → "Integrity 35% < 40%，已觸發 HR-14，請執行全面審計"
```

### context_compressor（新 CLI）

```bash
# 三層壓縮 CLI
python cli.py context-compress --level L1
python cli.py context-compress --level L2
python cli.py context-compress --level L3
python cli.py context-compress --level auto  # 自動選擇等級
```

---

## 教訓（經驗累積）

### Phase 3 Module 1 學到的教訓（2026-04-02）

| # | 教訓 | 防止方式 |
|---|------|---------|
| 1 | L1 設計被忽視 | On Demand：被問時再提供 |
| 2 | NFR-02 約束被忽視 | Prompt 只列禁止事項，讓 sub-agent 自己對照 |
| 3 | Annotation 格式自由發揮 | Forbidden 事項列清楚 |
| 4 | 目錄用錯 | Forbidden 事項：`app/infrastructure/` 已廢除 |
| 5 | sessions_spawn.log 落後 | spawn 前就寫入 |
| 6 | 直接信任 sub-agent | confidence 機制：< 6 就重新派遣 |
| 7 | 上下文污染 | SubagentIsolator.spawn() 嚴格隔離 |
| 8 | 一次 dump 所有資訊 | On Demand：只給任務名稱 + paths |

### v6.22 新增教訓

| # | 教訓 | 防止方式 |
|---|------|---------|
| 9 | Raw sessions_spawn 導致結果污染 | 嚴格使用 SubagentIsolator.spawn() |
| 10 | 危險操作無審批 | PermissionGuard.check() 強制執行 |
| 11 | 長期任務中斷無法恢復 | 預計 >30 分鐘 → session-save |
| 12 | 新工具引入後無法追蹤 | ToolRegistry.register() 強制登記 |
| 13 | 錯誤發生時無修復方向 | Enhanced exceptions + suggest_fix() |

---

## SAD §10 Phase 3 目錄（標準版）

```
app/
├── processing/              # FR-01,02,03
│   ├── lexicon_mapper.py   # FR-01
│   ├── ssml_parser.py      # FR-02
│   └── text_chunker.py     # FR-03
├── synth/                  # FR-04,05
│   ├── async_engine.py      # FR-04
│   └── circuit_breaker.py  # FR-05
├── cache/                  # FR-06
│   └── redis_cache.py
├── audio/                  # FR-08
│   └── audio_converter.py
├── api/                    # FR-07
│   ├── server.py
│   └── cli.py
├── backend/                # FR-09
│   └── kokoro_client.py
├── main.py
└── models/
    ├── speech.py
    └── errors.py
tests/
├── test_fr01_lexicon.py
├── test_fr02_ssml.py
├── test_fr03_chunker.py
├── test_fr04_synth.py
├── test_fr05_circuit.py
├── test_fr06_cache.py
├── test_fr07_api.py
├── test_fr08_audio.py
└── test_fr09_backend.py
```

---

*本 SOP 整合 Main Agent Playbook (v6.26) + run-phase 單一入口 + On Demand 管理原則 + Phase 3 實作經驗 + v6.26 新工具*
