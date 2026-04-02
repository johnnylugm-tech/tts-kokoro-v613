# 專案狀態總覽 — tts-kokoro-v613

> 建立日期：2026-04-01  
> 最近更新：2026-04-02  
> 狀態：Phase 1 ✅ 完成，Phase 2 ✅ 完成，SAD ✅ 對齊 Phase 3，待 Phase 3 實作

---

## 原始任務（Mission）

Johnny 的核心目標：

> 基於 DOCX 規格書建立完整 `kokoro-taiwan-proxy` TTS Proxy 系統，对齐 SRS.md 優化版規格（Chunk 250字、50+ LEXICON、CLI、ffmpeg），持續維護 TTS_2 的 SSML 實作。

---

## 專案背景

### 實驗架構

| 角色 | 專案 | 說明 |
|------|------|------|
| **實驗組** | `tts-kokoro-v613` | kokoro-v613（最新）+ 台灣化實作 |
| **對照組** | `kokoro-taiwan-proxy` | kokoro-v1（舊版）+ 現有實作 |
| **個人工具** | `TTS_2` | Johnny 日常使用的 SSML 實作 |

### Kokoro 後端

- **URL**：`http://localhost:8880/v1/audio/speech`
- **預設音色**：`zf_xiaoxiao`
- **用途**：台灣中文 TTS 語音合成

### GitHub

- **Repo**：`https://github.com/johnnylugm-tech/tts-kokoro-v613`
- **對照組**：`https://github.com/johnnylugm-tech/kokoro-taiwan-proxy`

---

## Phase 1 交付物（已完成）

| 交付物 | 路徑 | Commit | 狀態 |
|--------|------|--------|------|
| SRS.md | `SRS.md` | `d303bfd` | ✅ 完成 |
| SPEC_TRACKING.md | `SPEC_TRACKING.md` | `4cab893` | ✅ 完成 |
| TRACEABILITY_MATRIX.md | `TRACEABILITY_MATRIX.md` | `4cab893` | ✅ 完成 |
| DEVELOPMENT_LOG.md | `DEVELOPMENT_LOG.md` | `59e8cff` | ✅ 完成 |
| Phase1_STAGE_PASS.md | `00-summary/Phase1_STAGE_PASS.md` | `59e8cff` | ✅ 完成 |
| sessions_spawn.log | `sessions_spawn.log` | `3140ecd` | ✅ 完成 |

### Phase 1 驗證結果

| 檢查項目 | 結果 |
|----------|------|
| Constitution Score | 85.7% ✅ PASS |
| FrameworkEnforcer BLOCK | 6 項檢查, 0 項違規 ✅ |
| Sessions_spawn.log | 4 筆記錄, 2 角色, 4 sessions ✅ |
| STAGE_PASS 分數 | 70/100 ✅ |
| 真相驗證 | 100% ✅ 可能真實 |

### Phase 1 發現並修復的問題

| # | 問題 | 類型 | 修復方式 |
|----|------|------|---------|
| 1 | Constitution type 計算錯誤 | Framework Bug | musk 修復 |
| 2 | Sessions 格式解析失敗 | Framework Bug | musk 修復 |
| 3 | 路徑命名慣例不符 | Framework Bug | musk 修復 |
| 4 | Phase 1 pytest/coverage 誤判 | Framework Bug | musk 修復 |
| 5 | SPEC_TRACKING 缺少更新紀錄 | Agent 問題 | 補上 Changelog |
| 6 | TRACEABILITY 缺少 GitHub 連結 | Agent 問題 | 補上 Links 表格 |
| 7 | sessions_spawn.log 格式不符 | Agent 問題 | 轉換為 line-delimited JSON |

**Framework Bugs：4 個（musk 修復）**  
**Agent 執行問題：3 個（已自行修復）**

---

## Phase 2 交付物（已完成）

| 交付物 | 路徑 | 狀態 |
|--------|------|------|
| SAD.md | `02-architecture/SAD.md` | ✅ 完成 |
| ADR-001 FastAPI Framework | `02-architecture/adr/001-fastapi-framework.md` | ✅ 完成 |
| ADR-002 Taiwan Lexicon | `02-architecture/adr/002-taiwan-lexicon-strategy.md` | ✅ 完成 |
| ADR-003 SSML Parser | `02-architecture/adr/003-ssml-parser-approach.md` | ✅ 完成 |
| ADR-004 Async Synthesis | `02-architecture/adr/004-async-parallel-synthesis.md` | ✅ 完成 |
| ADR-005 Circuit Breaker | `02-architecture/adr/005-circuit-breaker.md` | ✅ 完成 |
| ADR-006 Redis Cache | `02-architecture/adr/006-redis-cache-strategy.md` | ✅ 完成 |

### Phase 2 Constitution 結果

| 檢查項目 | 門檻 | 實際 | 狀態 |
|----------|------|------|------|
| Constitution Score | > 80% | 92.9% | ✅ PASS |
| 正確性（Correctness） | 100% | ✅ 4/4 | ✅ |
| 安全性（Security） | 100% | ✅ 4/4 | ✅ |
| 可維護性（Maintainability） | > 80% | ✅ 4/4 | ✅ |

### SAD.md Phase 3 框架對齊（2026-04-02）

| 修正項目 | 說明 |
|----------|------|
| §0.2 Phase 3 Entry Conditions | 加入 Entry Conditions 表格 |
| §0.3 Constitution Type | 加入 Phase 3 `sad` type 門檻 |
| §0.4 Quality Gate 工具 | 加入工具對應表（constitution/runner.py, doc_checker.py, phase-verify, pytest） |
| §10 目錄結構 | 重構為 FR 模組化目錄，Layer 降為內部實作細節 |
| §10.1 FR-Layer 對照表 | FR 模組與內部 Layer 的對照關係 |

---

### Phase 2 模組設計

| 模組 | 說明 | FR 覆蓋 |
|------|------|---------|
| Module 1: TextProc | TaiwanLexicon + SSMLParser + TextSplitter | FR-01, FR-02, FR-03 |
| Module 2: Synthesis | AsyncEngine + CircuitBreaker | FR-04, FR-05 |
| Module 3: Caching | RedisCache (optional) | FR-06 |
| Module 4: AudioProc | AudioConverter (ffmpeg) | FR-08 |
| Module 5: API/CLI | FastAPI + Typer CLI | FR-07 |

---

## SRS.md 核心規格（Phase 3 需實作）

### 功能需求（FR）

| ID | 需求 | 說明 |
|----|------|------|
| FR-01 | 台灣中文詞彙映射 | LEXICON ≥ 50 詞（涵蓋科技/交通/食物/發音等） |
| FR-02 | SSML 解析 | 支援 `<speak>`、`<break>`、`<prosody>`、`<voice>`、`<phoneme>` |
| FR-03 | 智能文本切分 | Chunk ≤ 250 字，三級遞迴切分 |
| FR-04 | 並行合成引擎 | httpx.AsyncClient + MP3 串接 |
| FR-05 | 斷路器（Circuit Breaker） | 失敗 ≥ 3 → Open，10 秒後 Half-Open |
| FR-06 | Redis 快取（可選） | Key=`hash(text+voice+speed)`，TTL=24h |
| FR-07 | CLI 工具 | `tts-v610` 支援文字/SSML/檔案輸入 |
| FR-08 | ffmpeg 音訊轉換 | MP3 ↔ WAV 格式互轉 |

### 非功能需求（NFR）

| ID | 需求 | 目標 |
|----|------|------|
| NFR-01 | TTFB | < 300ms |
| NFR-02 | LEXICON 覆蓋率 | ≥ 80%（目標 ≥ 95%） |
| NFR-03 | 變調正確率 | ≥ 95% |
| NFR-04 | API 可用率 | ≥ 99% |
| NFR-05 | 錯誤恢復時間 | < 10s |
| NFR-06 | 單元測試覆蓋率 | ≥ 80% |
| NFR-07 | 斷路器恢復 | < 10s |

### 技術棧

- **後端**：Kokoro Docker（`http://localhost:8880`）
- **代理層**：FastAPI + httpx + Python 3.10+
- **可選快取**：Redis
- **CLI 工具**：ffmpeg（音訊轉換）

---

## Phase 2 規劃（✅ 完成）

### Phase 2 Constitution 門檻

| 維度 | 門檻 | 實際 |
|------|------|------|
| Correctness | 100% | ✅ |
| Security | 100% | ✅ |
| Maintainability | > 80% | ✅ 92.9% |
| Coverage | > 70% | ✅ |

### Phase 3 下一步

1. 實作 Module 1: TextProc（TaiwanLexicon + SSMLParser + TextSplitter）
2. 實作 Module 2: Synthesis（AsyncEngine + CircuitBreaker）
3. 實作 Module 3: Caching（RedisCache）
4. 實作 Module 4: AudioProc（AudioConverter）
5. 實作 Module 5: API/CLI（FastAPI + Typer）
6. 單元測試覆蓋率 ≥ 80%

---

## Phase 3 進度

Phase 3 尚未開始。SAD 已合併完成（commit 07605ac）。

等待 Johnny 指示開始 Phase 3 實作。

### Phase 3 狀態持久化設計（Experiment v1）

**原則**：每個 Step 完成後立即 commit 到 GitHub。Commit message 包含 Step 編號和 commit hash。

**Commit 格式**：`[Phase N] Step X: 模組名稱 (commit HASH)`

**持久化資訊**（每個 Step）：
| 資訊 | 儲存位置 |
|------|----------|
| 當前 Phase | `PROJECT_STATUS.md` |
| Step 完成狀態 | `PROJECT_STATUS.md` |
| 完整 source code | GitHub commit |
| Framework version | `PROJECT_STATUS.md` |

**新工具接手流程**：
1. Clone repo
2. Read `PROJECT_STATUS.md` → 知道做到哪個 Phase/Step
3. Read `PROJECT_STATUS.md` → 知道 Framework 版本
4. Install methodology-v2 (`pip install methodology-v2`)
5. 從上次 commit 繼續

---

---

---

## 系統層級原則（來自 Johnny 的第一性原理）

| 編號 | 領域 | 第一性原理 |
|------|------|-----------|
| 1 | 利潤 | 成本控制 |
| 2 | 管理 | 激發潛能 |
| 3 | 決策 | 數據支持 |
| 4 | 戰略 | 核心競爭力 |
| 5 | 財富 | 不斷積累 |
| 6 | 時間 | 優先級 |
| 7 | 成事 | 實踐 |

---

## Agent 執行原則（MEMORY.md 記錄）

1. **所有任務執行**：預設啟動 sub-agent 執行
2. **錯誤處理**：遇到問題立即修復，不問
3. **主動建議**：討論任務時主動提供建議
4. **指示不明確時**：先停止，主動確認後再繼續
5. **Git 操作**：永不強制推送、刪除分支或重寫歷史

---

## 2026-04-01 今日教訓

### Phase 1 執行中的問題

**工具存在但未執行**：

| 工具 | 問題 |
|------|------|
| `stage-pass --phase N` | 第一次 timeout，之後放棄 |
| `enforce --level BLOCK` | 跑了沒預期輸出，就跳過 |
| Constitution 分數高 | 以為交付物完整，沒逐一檢查 |

**原因**：「覺得差不多」就停了，沒有對著檢查清單逐項確認。

### 原則（已記錄進 MEMORY.md）

> **口號**：懷疑時，跑工具。  
> **Phase 結尾**：必須執行 `stage-pass --phase N` 和 `enforce --level BLOCK`。  
> ** Constitution 分數高 ≠ 交付物完整**。必須對著 SKILL.md 的要求清單確認。

### Framework vs Agent 問題分類

| 類型 | 負責人 | 修復方式 |
|------|--------|---------|
| Framework Bug | musk | GitHub push → 我 pull 驗證 |
| Agent 執行問題 | 我 | 自行修復後 push |

---

## Methodology Framework

- **Framework 路徑**：`/Users/johnny/.openclaw/workspace/methodology-v2`
- **Constitution 類型**：Phase 1 = `srs`，Phase 2 = `sad`
- **CLI 工具**：
  - `stage-pass --phase N` — 產生 STAGE_PASS
  - `enforce --level BLOCK` — Framework BLOCK 檢查
  - `quality-gate phase` — 品質閘道
  - `phase-verify` — Phase 真相驗證

### Framework 已修復的 Bugs（musk）

1. Constitution runner 使用正確的 type（srs for Phase 1）
2. Phase 1 跳過 pytest/coverage 檢查
3. 支援多目錄命名慣例
4. Framework Phase-aware checks

---

## 明日待辦

- [x] `memory/2026-04-01.md` 建立（會議紀錄）
- [x] Phase 2 啟動：讀取 SKILL.md Phase 2 指引
- [x] 產出 SAD.md
- [x] 產出 ADR
- [x] 執行 Constitution check（92.9% PASS）
- [x] Phase 2 Git commit + push
- [x] SAD.md Phase 3 框架對齊（2026-04-02）
- [ ] 請求 Johnny CONFIRM
- [ ] Phase 3 實作啟動

---

## 專案通訊架構（規劃中）

```
Telegram Group（規劃中）
├── Johnny (Human)
├── Jarvis Bot (me, openclaw-A)
└── Musk Bot (musk, openclaw-B)
```

目標：消除 Johnny 作為中間轉递者的 bottleneck。

---

---

## 持久化架構原則

**GitHub 是 Complete Source of Truth**

| 檔案 | 必要性 | 說明 |
|------|--------|------|
| `PROJECT_STATUS.md` | ✅ 必需 | 任何災難後的第一頁 |
| `memory/` | ❌ 可選 | agent 輔助用，不影響 resume |
| `USER.md` | ❌ 可選 | agent 輔助用，不影響 resume |

**依賴性 = 0**：砍掉 `memory/`、`USER.md`、methodology-v2，clone 此 repo 就能完整 resume。

