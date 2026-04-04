# plan-phase UX 問題回報

> 日期：2026-04-04
> 記錄者：Jarvis (小袐)
> 專案：tts-kokoro-v613

---

## 問題描述

### 問題 1：兩個檔案需要合併才能看完整內容

**現況**：
```
plan-phase --detailed
    ↓
產生兩個檔案：
1. phase3_xxxxxxxx.md（基礎 plan，HR/TH/工具）
2. phase3_FULL.md（FR 詳細任務）
    ↓
需要合併才能看完整內容
```

**期望行為**：
```
plan-phase --detailed
    ↓
只產生一個檔案：phase3_FULL.md（包含所有內容）
```

**影響**：
- 不直覺，需要手動合併
- 浪費時間
- 容易遺漏

---

## 深度對比結果（v6.40 vs 手動版本）

| 項目 | v6.40 自動生成（合併版）| 手動版本 | 勝出 |
|------|---------------------|---------|------|
| 版本 | v6.39.0 | v6.14.0 | 自動 ✅ |
| HR 數量 | 15（+HR-15）| 14 | 自動 ✅ |
| FR 詳細任務 | ✅ 8項完整 | ✅ 8項完整 | 平手 |
| 測試案例 | ✅ 直接內嵌 | ✅ 直接內嵌 | 平手 |
| Pre-Execution | ✅ 12項完整 | ✅ 12項完整 | 平手 |
| HR 約束 | ✅ 完整 | ✅ 完整 | 平手 |
| TH 閾值 | ✅ 完整 | ✅ 完整 | 平手 |
| 工具速查 | ✅ 完整 | ✅ 完整 | 平手 |
| 估計時間 | ✅ 完整 | ✅ 完整 | 平手 |
| sessions_spawn.log | ✅ 完整 | ✅ 完整 | 平手 |
| Iteration 流程 | ✅ 完整 | ✅ 完整 | 平手 |
| Commit 格式 | ✅ 完整 | ✅ 完整 | 平手 |
| Phase Truth | ✅ 完整 | ✅ 完整 | 平手 |
| **專案名稱** | ❌ 空 | ✅ `tts-kokoro-v613` | 手動 ✅ |
| 外部文檔列表 | ✅ 有 | ✅ 有 | 平手 |
| **下一步指令** | ✅ `--repair` | ❌ 無 | 自動 ✅ |
| **Reviewer Prompt** | ❌ 缺失 | ✅ 完整 | 手動 ✅ |

---

## 建議改善

### 1. 合併為單一檔案

`--detailed` 應該只產生一個完整檔案（phase3_FULL.md），包含：
- HR 規則
- TH 閾值
- FR 詳細任務
- Pre-Execution Checklist
- 工具速查
- 所有內容

### 2. 專案名稱解析

`--goal` 參數應該用於解析專案名稱，而非只是描述。

### 3. Reviewer Prompt 模板

自動生成應該包含完整的 Reviewer Prompt，而非只有 Developer Prompt。

---

## 其他觀察

### v6.40 優點
- FR 測試案例直接內嵌 ✅
- 不再需要跳轉 phase3_FULL.md ✅
- --repair 指令 ✅
- Pre-Execution Checklist 完整 ✅

### 需要改善
- 合併輸出檔案
- 專案名稱識別
- Reviewer Prompt 完整性

---

## v6.42 仍需改善的項目（截至 2026-04-04）

### 1. 專案名稱解析（仍未解決）

| 項目 | 說明 |
|------|------|
| **問題** | Plan header 的「專案」欄位為空 |
| **原因** | `--goal` 參數只當描述用，未解析為專案名稱 |
| **期望** | `plan-phase --goal "tts-kokoro-v613 Phase 3"` → 專案自動填入 `tts-kokoro-v613` |

### 2. 工具調用時機未寫入 Plan

| 項目 | 說明 |
|------|------|
| **問題** | Plan 只有 HR 規則，沒有「何時用什麼工具」 |
| **影響** | 主代理需要自己判斷什麼時候用 SubagentIsolator / ContextManager / SessionManager |
| **期望** | Plan 內有「Step X.X：派遣 Agent A」時，應說明用 SubagentIsolator.spawn() |

### 3. Need to Know 原則不明確

| 項目 | 說明 |
|------|------|
| **問題** | Developer Prompt 只說「自己讀」，沒明確禁止 dump 全文 |
| **影響** | Sub-agent 可能忽略 On Demand 自己讀的原則 |
| **期望** | Prompt FORBIDDEN 內加：「❌ dump 全文 → 任務失敗」 |

### 4. HR-15 citations 行號未在 Prompt 強調

| 項目 | 說明 |
|------|------|
| **問題** | HR-15 有「citations 必須含行號」，但 Developer Prompt 沒強調 |
| **影響** | Sub-agent 可能只給 `@covers: FR-01`，沒給行號 |
| **期望** | OUTPUT_FORMAT 內加：`"citations": ["FR-01", "SRS.md#L23-L45"]` 範例 |

### 5. Pre-flight deliverable 路徑誤報

| 項目 | 說明 |
|------|------|
| **問題** | SAD.md 在 `02-architecture/SAD.md`，plan-phase 卻在根目錄找 `SAD.md` |
| **影響** | Pre-flight 一直報 `Missing deliverables: ['SAD.md']` |
| **期望** | plan-phase 應支援多目錄搜尋（`glob("**/SAD.md")`）|

---

## 總結

| # | 問題 | 嚴重性 |
|---|------|--------|
| 1 | 專案名稱解析 | 中 |
| 2 | 工具調用時機 | 高 |
| 3 | Need to Know 不夠強制 | 中 |
| 4 | HR-15 citations 行號未強調 | 中 |
| 5 | deliverable 路徑誤報 | 低 |
