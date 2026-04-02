# Phase 2 檢討報告

> 專案：tts-kokoro-v613  
> 日期：2026-04-01  
> 作者：Jarvis (agent:main)

---

## 1. Phase 2 執行摘要

| 項目 | 數值 |
|------|------|
| Constitution 分數 | 92.9% ✅ |
| Auditor 分數 | 92.8% ✅ |
| 交付物 | SAD.md + 6 ADRs ✅ |
| Framework Bugs 發現 | 6 個 |
| 實驗問題 | 4 個 |

---

## 2. 發現的 Framework Bugs（已修復）

| # | Bug | 檔案 | 修復 commit |
|---|-----|------|------------|
| 1 | `enforce --level BLOCK` 零輸出 | `cli.py` | `06a65c5` |
| 2 | `phase_truth_verifier` 缺少 `import sys` | `phase_truth_verifier.py` | `06a65c5` |
| 3 | Constitution runner 只認 `docs/`，不認 phase 目錄 | `constitution/runner.py` | `06a65c5` |
| 4 | Phase artifact 路徑期望錯誤（`SAD.md` vs `02-architecture/SAD.md`）| `phase_truth_verifier.py` | `06a65c5` |
| 5 | `verify_phase_link` 只用 `output_dir`，忽略 `alt_dirs` | `phase_artifact_enforcer.py` | `06a65c5` |
| 6 | Stage Pass 缺少「階段目標達成」「SIGN-OFF」章節 | `stage_pass_generator.py` | `8e33878` |

---

## 3. 實驗發現的流程問題

### 3.1 Stage Pass 內容與實際不符

**問題**：Sub-agent 宣稱完成的 ADR 檔案名稱，和磁碟上實際存在的檔案不符。

**原因**：
- Sub-agent 產出後沒有立即執行 `stage-pass` 工具
- Stage Pass 由 sub-agent 想像生成，不是工具實際產出
- 沒有 cross-check 機制

**改善方案**：
```
流程更新：
1. Sub-agent 完成 Phase
2. 立即執行 stage-pass（工具自動產生）
3. 工具輸出 → GitHub commit
4. 不允許「人工想像」的 Stage Pass
```

### 3.2 Git Reset 不夠徹底

**問題**：`git reset --hard ef85a4a` 後，sub-agent 工作目錄殘留舊檔案，導致新 commit 混入舊 artifact。

**原因**：
- Reset 前未確認 target commit 的完整狀態
- 未執行 `git clean -fd` 清理工作目錄

**改善方案**：
```
每個 Phase 重來前：
1. git ls-tree <target> --name-only（確認目標狀態）
2. git clean -fd（清理工作目錄）
3. git reset --hard <target>
4. 確認 ls 後只有預期檔案
```

### 3.3 Constitution 分數與 Stage Pass 分數混淆

**問題**：
- Stage Pass 信心分數：70/100
- Constitution 實際分數：85.7% / 92.9%
- Auditor 混淆兩者

**原因**：
- `stage_pass_generator.py` 計算的是「信心分數」（信心 x40 + log x20 + pytest x10）
- 沒有直接呼叫 Constitution 檢查

**改善方案**：
- Stage Pass 生成時，直接呼叫 `check_constitution()` 取得 Constitution 分數
- 信心分數（70/100）≠ Constitution 分數（85.7%）

### 3.4 Framework Alt_dirs 設計缺陷

**問題**：`alt_dirs` 讓 artifact 可以放在任意位置，違背了目錄結構紀律。

**原因**：
- `alt_dirs: ["docs"]` 允許 Phase 2 artifact 放在 `docs/` 而非 `02-architecture/`
- Phase 1 結束後 reset，`02-architecture/` 不存在，所以 Phase 2 接受 `docs/` 作為 valid alt

**改善方案**：
- Phase 目錄是固定的，不允許 `docs/` 作為 Phase artifact 的替代
- SKILL.md 的目錄結構是 single source of truth

---

## 4. Phase 3 實驗重點：狀態持久化

### 4.1 問題定義

現有流程：
- Sub-agent 完成後一次 commit
- 如果中途當機，需要從頭開始
- 切換工具（sub-agent ↔ Claude Code）需要重建狀態

### 4.2 提出的改善

**每個 step 完成後立即 commit：**

```
[Phase 3] Step 1: TaiwanLexicon 模組 (commit abc1234)
[Phase 3] Step 2: SSMLParser 模組 (commit def5678)
...
```

**PROJECT_STATUS.md 更新進度：**
```markdown
## Phase 3 進度

| Step | 模組 | Commit | 狀態 |
|------|------|--------|------|
| 1 | TaiwanLexicon | abc1234 | ✅ |
| 2 | SSMLParser | def5678 | ✅ |
| 3 | TextSplitter | ... | 🔄 |
```

### 4.3 實驗設計

**假設**：如果每個 step 都即時 commit，則：
1. 任何工具（我、Claude Code、或其他）都可以從中途接手
2. 當機後不需要重做已完成的工作
3. 不同工具可以針對不同 step 貢獻

**驗證方式**：
- Phase 3 每個模組完成後 commit
- 嘗試中途 clone 並從某個 step 繼續
- 觀察是否有任何狀態遺失

---

## 5. 具體改善行動清單

### Framework 層級（methodology-v2）

| # | 行動 | 負責人 | 優先 |
|---|------|--------|------|
| 1 | stage-pass 強制在 artifact 產生後立即執行 | musk | 高 |
| 2 | session spawn 時必須記錄 task 內容到 sessions_spawn.log | musk | 高 |
| 3 | phase_auditor.py 更新以支援 phase 目錄結構 | musk | 中 |
| 4 | DEVELOPMENT_LOG 需記錄所有 QG 工具輸出（不只是 Constitution） | musk | 中 |
| 5 | 信心分數和 Constitution 分數要明確區分 | musk | 中 |

### Agent 流程層級

| # | 行動 | 負責人 | 優先 |
|---|------|--------|------|
| 1 | Phase 重來前執行 git clean -fd + reset --hard | 我 | 高 |
| 2 | Sub-agent 完成後立即 stage-pass，不等 | 我 | 高 |
| 3 | Phase 3 每個 step 即時 commit | 我 | 高 |
| 4 | Stage Pass 內容 cross-check（與磁碟實際檔案比對） | 我 | 高 |

---

## 6. Phase 3 具體下一步

基於 SAD.md 的模組設計，Phase 3 的 step 拆分：

| Step | 模組 | 交付物 |
|------|------|--------|
| 1 | Directory Setup | `03-implementation/src/`, `tests/` |
| 2 | Module 1: TaiwanLexicon | `engines/taiwan_linguistic.py` |
| 3 | Module 1: SSMLParser | `engines/ssml_parser.py` |
| 4 | Module 1: TextSplitter | `engines/text_splitter.py` |
| 5 | Module 2: SynthEngine | `synth/synth_engine.py` |
| 6 | Module 2: CircuitBreaker | `infrastructure/circuit_breaker.py` |
| 7 | Module 3: RedisCache | `infrastructure/redis_cache.py` |
| 8 | Module 4: AudioConverter | `infrastructure/audio_converter.py` |
| 9 | Module 5: FastAPI routes | `api/routes.py` |
| 10 | Module 5: Typer CLI | `cli/tts_cli.py` |
| 11 | 合規矩陣 | `COMPLIANCE_MATRIX.md` |
| 12 | 單元測試 | `tests/` |

---

*由 methodology-v2 framework 自動產生*
