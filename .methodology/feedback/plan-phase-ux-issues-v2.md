# methodology-v2 v6.42 仍需改善的問題

> 日期：2026-04-04
> 記錄者：Jarvis (小袐)

---

## 問題 1：專案名稱解析（Feature: Project Name Parsing）

### 現況
執行：
```bash
plan-phase --phase 3 --goal "tts-kokoro-v613 Phase 3 代碼實作"
```

產出的 Plan header：
```
> **專案**: 
> **Framework**: methodology-v2 v6.40.0
```

### 問題
「專案」欄位為空，`--goal` 的內容完全沒被用來填入專案名稱。

### 期望行為
```
> **專案**: tts-kokoro-v613
> **Framework**: methodology-v2 v6.40.0
```

### 如何修復
在 `--goal` 字串中解析第一個「詞」（或 URL/path）作為專案名稱，例如：
- `"tts-kokoro-v613 Phase 3"` → 專案 = `tts-kokoro-v613`
- `"/path/to/my-project"` → 專案 = `my-project`

---

## 問題 2：工具調用時機未寫入 Plan（Feature: Tool Invocation Triggers）

### 現況
Plan 內有「HR 規則」，但沒有「何時用什麼工具」。

例如：
```
## 7. Developer Prompt 模板（On Demand）
```

但主代理不知道何時應該用：
- `SubagentIsolator.spawn()`
- `ContextManager.compress()`
- `SessionManager.save()`

### 問題
主代理需要自己猜測工具使用時機，可能導致：
- 忘記記錄 session_id（HR-07）
- 忘記壓縮 context（HR 效率問題）
- 忘記 save 狀態（HR-13）

### 期望行為
Plan 內每個 Step 應該明確標示工具調用：
```
### Step 1.1：派遣 Developer

工具調用：
- SubagentIsolator.spawn(role=DEVELOPER, task="FR-01")
- SessionManager.save("fr01", state) [30 分鐘後自動]

### Step 1.2：驗證產出

工具調用：
- ContextManager.compress_if_needed() [context > 50]
```

---

## 問題 3：Need to Know 原則不夠強制（HR Enforcement: Anti-Dump Rule）

### 現況
Developer Prompt 的 FORBIDDEN：
```
FORBIDDEN:
- ❌ app/infrastructure/
- ❌ @covers: L1 Error
- ❌ @type: edge
- ❌ ... 省略 → 任務失敗
```

沒有明確禁止「dump 全文」。

### 問題
Sub-agent 可能忽略「自己讀」的原則，反而要求主代理給他完整的 artifact 內容。

### 期望行為
FORBIDDEN 內加一條：
```
FORBIDDEN:
- ❌ dump 全文（要求主代理給完整 artifact）→ 任務失敗
- ❌ app/infrastructure/
- ❌ @covers: L1 Error
- ❌ @type: edge
```

---

## 問題 4：HR-15 citations 行號未在 Prompt 強調（HR Enforcement: Citation Line Numbers）

### 現況
HR-15 規則：
```
| HR-15 | citations 必須含行號 + artifact_verification | -15 |
```

但 Developer Prompt 的 OUTPUT_FORMAT：
```json
{
 "citations": ["FR-01", "SRS.md#L23-L45"],
}
```

只給了範例，沒有明確要求「沒有行號 = 任務失敗」。

### 問題
Sub-agent 可能只給：
```json
{
 "citations": ["FR-01", "SRS.md"],
}
```

### 期望行為
OUTPUT_FORMAT 的說明文字加強：
```
citations: 必須包含檔案行號，如 ["FR-01", "SRS.md#L23-L45"]
            沒有行號 → 任務失敗（HR-15）
```

---

## 問題 5：Pre-flight deliverable 路徑誤報（Bug: False Positive in Deliverable Check）

### 現況
```
⚠️  Missing deliverables: ['SAD.md', 'app/processing/']
```

但 SAD.md 實際存在於：`02-architecture/SAD.md`
app/processing/ 預期是 Phase 3 產出，還沒建立是正常的。

### 問題
plan-phase 的 deliverable 檢查邏輯：
```python
for d in deliverables:
    d_path = repo_path / d  # 只在根目錄找
    if not d_path.exists():
        missing.append(d)
```

沒有遞迴搜尋，也沒有區分「預期尚未存在」和「真的遺漏」。

### 期望行為
1. 支援 glob 搜尋：`glob("**/SAD.md")`
2. 區分「Phase N 預期產出」（尚不存在是正常的）和「Phase N-1 必須存在」

```
例如 Phase 3：
- SAD.md 應存在（Phase 2 產出）→ 檢查
- app/processing/ 是 Phase 3 產出 → 跳過
```

---

## 總結

| # | 問題 | 嚴重性 | 類型 |
|---|------|--------|------|
| 1 | 專案名稱解析 | 中 | Feature |
| 2 | 工具調用時機 | 高 | Feature |
| 3 | Need to Know 不夠強制 | 中 | HR Enforcement |
| 4 | HR-15 citations 行號未強調 | 中 | HR Enforcement |
| 5 | deliverable 路徑誤報 | 低 | Bug |

---

## v6.45 Phase 3 執行評估 - 待處理問題（2026-04-04）

### Issue 1：目錄建立初始化
| 類別 | Framework | Plan 生成 | 專案輔助 |
|-------|-----------|-----------|-----------|
| ❌ | ❌ | ✅ |

**說明**：Plan 沒有「Step 0：初始化」的說明（mkdir、touch tests/__init__.py 等）
**歸屬**：專案輔助（SKILL_DOMAIN.md 或初始化文件）

### Issue 2：pytest 環境
| 類別 | Framework | Plan 生成 | 專案輔助 |
|-------|-----------|-----------|-----------|
| ❌ | ❌ | ✅ |

**說明**：測試環境應在 Phase 1-2 建立，不屬於 Phase 3 職責
**歸屬**：專案輔助（Phase 1-2 交付物）

### Issue 3：ContextManager 觸發條件
| 類別 | Framework | Plan 生成 | 專案輔助 |
|-------|-----------|-----------|-----------|
| ✅ | ⚠️ | ❌ |

**說明**：
- Framework：ContextManager 應是自動鉤子，不是主動呼叫
- Plan 生成：§9 有提到，但觸發條件「context > 50」不夠具體

**建議**：ContextManager 應在每次 tool call 後自動檢查並壓縮

### Issue 4：HR-12 計數（REJECT 輪數）
| 類別 | Framework | Plan 生成 | 專案輔助 |
|-------|-----------|-----------|-----------|
| ✅ | ⚠️ | ❌ |

**說明**：
- Framework：SubagentIsolator 應內建 REJECT 計數
- Plan 生成：§8 有「HR-12 PAUSE」，但沒說誰計數

**建議**：Reviewer 回傳結果時，framework 自動更新計數並判斷是否 > 5

### Issue 5：HR-13 計時（>3x 預估時間）
| 類別 | Framework | Plan 生成 | 專案輔助 |
|-------|-----------|-----------|-----------|
| ✅ | ⚠️ | ❌ |

**說明**：
- Framework：SessionManager 應是自動鉤子，自動計時
- Plan 生成：§13 有估計時間，但觸發條件不在 plan

**建議**：SessionManager 在每次 save/load 時自動檢查是否 > 3x 預估

---

## 總結

| Issue | 問題 | 優先級 |
|-------|------|--------|
| 1 | 目錄建立初始化 | 低（專案輔助）|
| 2 | pytest 環境 | 低（Phase 1-2 交付物）|
| 3 | ContextManager 自動觸發 | **高（Framework）** |
| 4 | HR-12 自動計數 | **高（Framework）** |
| 5 | HR-13 自動計時 | **高（Framework）** |

**核心問題**：Framework 的「工具自動化鉤子」需完善（Issue 3, 4, 5）
