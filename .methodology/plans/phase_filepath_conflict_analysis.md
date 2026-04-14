# Framework vs Plan Phase 目錄不一致問題分析

> 日期：2026-04-13
> 問題：Phase 6 FSM 阻斷，原因是 Phase 5 產出路徑不符合 Framework tool 預期

---

## 1. 三層定義來源

### Layer 1：SKILL.md §4 Phase 路由

```
Phase 5: 驗證交付 | devops/architect | BASELINE, MONITORING_PLAN
Phase 6: 品質保證 | qa/architect | QUALITY_REPORT
```

**-note：SKILL.md 只定義交付物名稱（BASELINE、QUALITY_REPORT），不定義目錄路徑。**

---

### Layer 2：phase_artifact_enforcer.py（Framework Tool）

```python
Phase.SYSTEM_TEST: {  # Phase 5
    "required": ["TEST_PLAN.md", "TEST_RESULTS.md", "BASELINE.md"],
    "output_dir": "05-baseline",
    "alt_dirs": ["05-system-test", "05-baseline", "baseline"],
    "depends_on": [Phase.VERIFY],
},
Phase.QUALITY: {  # Phase 6
    "required": ["QUALITY_REPORT.md", "MONITORING_PLAN.md"],
    "output_dir": "06-quality",
    "alt_dirs": ["06-quality", "quality"],
    "depends_on": [Phase.SYSTEM_TEST],
},
```

| Phase | output_dir | alt_dirs |
|-------|-----------|---------|
| Phase 4（VERIFY）| `04-testing` | `04-verify, 04-testing, testing, verify` |
| **Phase 5（SYSTEM_TEST）** | **`05-baseline`** | `05-system-test, 05-baseline, baseline` |
| **Phase 6（QUALITY）** | **`06-quality`** | `06-quality, quality` |

**note：`05-verify/` 不在 Phase 5 或 Phase 6 的 alt_dirs 列表中。**

---

### Layer 3：Phase5_Plan_5W1H_AB.md（Framework Plan Doc，v5.56）

```
WHERE：`05-verify/` 目錄；監控結果在 `MONITORING_PLAN.md`；Quality Gate 在 `quality_gate/`
```

| 交付物 | Phase5_Plan 規定位置 |
|--------|---------------------|
| BASELINE.md | `05-verify/` |
| VERIFICATION_REPORT.md | `05-verify/` |
| QUALITY_REPORT.md | `05-verify/` |
| MONITORING_PLAN.md | 專案根目錄 |

---

## 2. 問題矩陣

| 問題 | Framework Tool（phase_artifact_enforcer）| Framework Plan Doc（Phase5_Plan）| 兩者差異 |
|------|----------------------------------------|----------------------------------|---------|
| BASELINE.md 位置 | `05-baseline/` 或 `05-system-test/` 或 `baseline/` | `05-verify/` | ❌ 不一致 |
| QUALITY_REPORT.md 位置 | `06-quality/` 或 `quality/` | `05-verify/`（Phase 5 位置）| ❌ 不一致 |
| 適用於 | Phase 6 FSM pre-flight check | Phase 5 執行時 | — |
| 誰受影响 | cli.py run-phase --phase 6 | Phase 5 執行時 | — |

---

## 3. 我們的 tts-kokoro-v613 選擇

| 決策 | 選擇 | 理由 |
|------|------|------|
| Phase 5 產出路徑 | `05-verify/` | 跟 Framework Plan Doc（Phase5_Plan）的 WHERE 條款 |
| Phase 6 產出路徑 | `05-verify/`（跟 Phase 5 一致）| 保持一致性，Phase6_Plan 也說 `05-verify/` |
| Phase 4 產出路徑 | `04-testing/` | 符合 phase_artifact_enforcer 的 alt_dirs |
| 結果 | Phase 5 完成了，但 Phase 6 FSM 被阻斷 | Phase 5 產出不在 Framework Tool 的預期目錄 |

---

## 4. 為什麼會變這樣

1. **Framework Plan Doc 說** `05-verify/`，所以 Phase 5 放在那裡 ✅
2. **Phase 6 Plan 也說** `05-verify/`，所以 Phase 6 跟著放在那裡 ✅
3. **Framework Tool（phase_artifact_enforcer）** 的 `alt_dirs` 是 `["05-system-test", "05-baseline", "baseline"]`，不包含 `05-verify/` ❌
4. **結果**：Phase 5 和 Phase 6 都在 `05-verify/`，但 FSM 搜尋 `05-baseline/`，找不到

---

## 5. 哪些環節有問題

### 問題 1：Framework Plan Doc vs Framework Tool 不一致

| 來源 | Phase 5 BASELINE.md 位置 |
|------|------------------------|
| Phase5_Plan_5W1H_AB.md（WHERE 條款）| `05-verify/` |
| phase_artifact_enforcer.py（output_dir）| `05-baseline/` |
| 差異 | **不一致** |

**這不是我們的問題，是 Framework 內部不一致。**

---

### 問題 2：我們的 Phase5 Plan 沒有檢查 Framework Tool 的 output_dir

Phase5_Plan_5W1H_AB.md 的 WHERE 是 `05-verify/`，但沒驗證這是否和 phase_artifact_enforcer.py 的 output_dir 一致。

**我們的 Phase5 Plan 服從了 Framework Plan Doc，但忽略了 Framework Tool 的約束。**

---

### 問題 3：Phase6 Plan 跟 Phase5 保持一致，但沒確認 Framework 整體約束

Phase 6 Plan 選擇 `05-verify/QUALITY_REPORT.md` 為了和 Phase 5 一致，但：
- phase_artifact_enforcer.py 預期 `06-quality/QUALITY_REPORT.md`
- Phase 5 的 `BASELINE.md` 在 `05-verify/`，但 FSM 預期 `05-baseline/`

---

## 6. SKILL.md 的規定

**SKILL.md §4 Phase 路由**：
```
Phase 5: 驗證交付 | devops/architect | BASELINE, MONITORING_PLAN
Phase 6: 品質保證 | qa/architect | QUALITY_REPORT
```

**SKILL.md 沒有規定目錄路徑**。只有交付物名稱。

---

## 7. 建議方案

### 方案 A：修復 Framework Plan Doc（長期）

修改 `Phase5_Plan_5W1H_AB.md` 的 WHERE 條款：
- 從 `05-verify/` → 改為 `05-baseline/`
- 同時更新交付物位置表

**需要 musk 處理**（Framework maintainer）

---

### 方案 B：擴展 phase_artifact_enforcer.py 的 alt_dirs（長期）

在 phase_artifact_enforcer.py 的 Phase 5 和 Phase 6 定義中，加入 `05-verify/` 和 `05-verify/`：
```python
Phase.SYSTEM_TEST: {  # Phase 5
    "alt_dirs": ["05-system-test", "05-baseline", "baseline", "05-verify"],
}
Phase.QUALITY: {  # Phase 6
    "alt_dirs": ["06-quality", "quality", "05-verify"],  # 加入 05-verify
}
```

**需要 musk 處理**（Framework maintainer）

---

### 方案 C：臨時遷移（立即可用）

把 Phase 5/6 的產出遷移到 Framework Tool 預期的位置：

```
Phase 5:
  05-verify/BASELINE.md → 05-baseline/BASELINE.md
  05-verify/QUALITY_REPORT.md → 05-quality/QUALITY_REPORT.md（Phase 6 專用）

Phase 6:
  05-verify/QUALITY_REPORT.md（Phase 6 更新版）→ 06-quality/QUALITY_REPORT.md
  STAGE_PASS → 00-summary/Phase6_STAGE_PASS.md
```

**優點**：立即可用，繞過 FSM 阻斷
**缺點**：遷移後 Phase5 Plan 需要更新（因為 Plan 說的位置和實際位置不一致）

---

### 方案 D：Phase 5 重做（最乾淨）

廢除 `05-verify/` 下的 Phase 5 產出，在 `05-baseline/` 重新建立，並在 Phase6 Plan 加入路徑修正。

**優點**：完全符合 Framework Tool
**缺點**：Phase 5 全部重做（需要估算時間）

---

## 8. 我的建議

| 方案 | 建議 | 理由 |
|------|------|------|
| **短期** | **方案 C（臨時遷移）** | 立即可用，不阻斷 Phase 6 執行 |
| **長期** | **方案 B（Framework fix）** | 根本解決，musk 擴展 alt_dirs |
| **放棄** | 方案 D（Phase 5 重做） | 成本太高，產出功能上沒問題 |

**立即行動**：執行方案 C，然後向 musk 報告 Framework Plan Doc 和 Tool 的不一致，請求 B。

---

## 9. 總結

| 層級 | 問題 | 負責方 |
|------|------|--------|
| Framework Plan Doc（Phase5_Plan）| WHERE 條款說 `05-verify/`，但 Framework Tool 預期 `05-baseline/` | musk |
| Framework Tool（phase_artifact_enforcer）| alt_dirs 不包含 `05-verify/` | musk |
| 我們的 Phase5 Plan | 服從 Framework Plan Doc，但沒驗證 Framework Tool 約束 | 我們（跟著 Plan 走） |
| 我們的 Phase6 Plan | 跟 Phase5 保持一致，但忽略了 Framework Tool 約束 | 我們 |

**核心問題**：Framework 的 Plan Doc 和 Tool 的約束不一致，我們沒發現這個 gap。

---

*生成時間：2026-04-13 16:10 GMT+8*
*Framework: methodology-v2 v6.14.0*