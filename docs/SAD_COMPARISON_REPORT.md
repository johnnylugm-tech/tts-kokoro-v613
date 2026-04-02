# SAD 比對分析報告

> 專案：tts-kokoro-v613  
> 比對：main branch vs `phase2-claude-code-comparison` branch  
> 日期：2026-04-01

---

## 1. 摘要

| 維度 | main (Sub-agent) | Claude Code branch |
|------|------------------|-------------------|
| 語言 | 中文 | 英文 |
| 結構完整性 | 中等（5 modules） | 完整（5 layers + diagrams） |
| Constitution 分數 | 92.9% ✅ | 未知 |
| 章節數量 | 較少 | 13 個章節 |
| FR 覆蓋 | FR-01~08 | FR-01~08 |
| ADR 數量 | 6 個 | 未比較 |

---

## 2. 結構差異

### main（SAD.md）

```
1. 概覽
2. 模組架構（Module 1-5）
3. 介面定義
4. NFR 對應
5. 目錄結構
6. 錯誤處理
```

### Claude Code

```
1. Overview
2. System Context Diagram（ASCII）
3. Architecture Layers（Layer 1-5）
4. Module Boundary Map
5. Data Flow Diagram
6. Module Interface Definitions
7. L1-L4 Error Handling Strategy
8. Security Architecture
9. NFR Implementation Strategy
10. Directory Structure
11. Configuration Schema
12. Dependency Graph
13. ADR Reference Table
```

---

## 3. 深度差異

| 項目 | main | Claude Code |
|------|------|-------------|
| ASCII 架構圖 | ✅ 有 | ✅ 有（更詳細） |
| Layer Dependency Rule | ⚠️ 提及 | ✅ 明確定義 |
| 接口格式 | 段落描述 | 表格 + 程式碼範例 |
| NFR 測量方式 | 描述性 | 有具體 metric |
| FR → Module 對應 | Table | 明確的 ownership |
| ADR 引用 | Table with links | 獨立章節 |

---

## 4. 結論

### Claude Code 版本較佳的點

1. **完整的 ASCII 架構圖** — 5 layers 的邊界和依賴關係清晰
2. **Layer Dependency Rule 明確定義** — "Layer N may only import from Layer N+1 or lower"
3. **Module Interface Tables** — 每個介面的 input/output 格式清楚
4. **NFR 有具體 metric** — 不是只有「目標」，而有測量方式

### main 版本較佳的點

1. **中文描述** — 直接對應 Johnny 的需求（台灣中文 TTS）
2. **FR-01 具體實作** — TaiwanLexicon 有 ≥50 詞的具體對映
3. **更符合 Constitution 要求** — Constitution 分數 92.9% 證明結構合規

---

## 5. 建議

**Phase 3 實作時，建議採用以下混合策略：**

1. **模組劃分**：參考 main 版本的 Module 1-5（符合 Johnny 的需求描述）
2. **介面定義**：參考 Claude Code 的 Table 格式（更清楚）
3. **錯誤處理**：採用 Claude Code 的 L1-L4 分類（更完整）
4. **目錄結構**：兩者一致（`app/api/`, `app/processing/`, `app/infrastructure/`）

**最終目錄結構（合併後）：**
```
app/
├── api/routes.py           # Layer 1
├── orchestrator/speech_orchestrator.py  # Layer 2
├── processing/              # Layer 3
│   ├── ssml_parser.py     # FR-02
│   ├── lexicon_mapper.py   # FR-01
│   └── text_chunker.py    # FR-03
├── synth/                  # Layer 3（async I/O）
│   └── synth_engine.py    # FR-04
└── infrastructure/          # Layer 5
    ├── circuit_breaker.py # FR-05
    ├── redis_cache.py     # FR-06
    └── audio_converter.py # FR-08
```

---

## 6. 實驗結論

不同工具適合不同面向：

| 面向 | 適合工具 |
|------|----------|
| 中文結構化輸出 | Sub-agent |
| 深層架構設計 | Claude Code |
| 深層分析、系統圖 | Claude Code |
| 快速產出、對應需求 | Sub-agent |

**建議**：Phase 3 實作時，採用 Claude Code 的 SAD 結構作為實作藍圖。

---

*由 methodology-v2 framework 自動產生*
