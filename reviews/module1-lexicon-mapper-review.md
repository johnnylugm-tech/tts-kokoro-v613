# Logic Review — Module 1: LexiconMapper (FR-01)

> Phase 3, Module 1 Logic Review
> Reviewer Role: developer (Agent A self-review — for Architect/Reviewer Agent B to confirm)
> Date: 2026-04-02

---

## 模組資訊

| 項目 | 值 |
|------|-----|
| 模組名稱 | LexiconMapper |
| 檔案 | `app/processing/lexicon_mapper.py` |
| 對應需求 | FR-01: 台灣中文詞彙映射 |
| 詞典檔案 | `app/data/lexicon_tw.json`（60 詞） |
| 測試檔案 | `tests/test_lexicon_mapper.py`（25 測試） |

---

## Developer 自我審查

### FR-01 邏輯約束驗證

| 約束 | 實作方式 | 驗證狀態 |
|------|---------|---------|
| 詞典在首次 apply() 才載入 | `LexiconMapper.__init__` 只設定路徑，`_load_lexicon()` 在 `apply()` 首次呼叫時執行 | ✅ |
| 單次正則穿越，長詞優先匹配 | 按 `from` 長度降序排列 + re alternation + callback 精確比對 | ✅ |
| L1 錯誤處理：輸入驗證失敗立即返回錯誤 | `LexiconMapperError` 例外，錯誤碼 L1-001~L1-007 | ✅ |
| 詞彙數 ≥ 50 | `lexicon_tw.json` 含 60 詞（科技/交通/食物/發音/職業/稱謂） | ✅ |
| SRS 邏輯驗證案例通過 | `test_srs_example_1` 和 `test_srs_example_2` 覆蓋 | ✅ |

### SKILL.md Core Modules 驗證

| 規範項目 | 實作狀態 |
|---------|---------|
| docstring 標注對應章節 | ✅ `SKILL.md - Core Modules`, `SKILL.md - Error Handling (L1-L6)`, `SRS.md FR-01` |
| 型別提示完整 | ✅ `__init__`, `apply()`, `reload()`, `reset()`, `lexicon_size` 均有 TypeHint |
| 錯誤碼命名一致（L1） | ✅ L1-001~L1-007 |
| 單一職責（SRP） | ✅ LexiconMapper 只負責詞彙映射 |

### 設計決策說明

#### 決策 1：單字符詞彙不做 word-boundary lookbehind

**問題**：若對單字符詞（如「和」「吧」）加 `(?<!CJK)` lookbehind，幾乎所有出現都會被阻擋（因相鄰字總是 CJK）。若加 `(?<![\u4e00-\u9fff])` 會導致句尾/句中單字全部不匹配。

**解決方案**：
- 單字符詞彙：直接替換所有出現
- 多字符詞彙（≥2）：長度排序確保正確優先順序，callback 精確比對

**代價**：「和」在「你和我是」中會被替換為「ㄏㄢˋ」。若未來需精確邊界，需引入 NLP 工具（非本模組範圍）。

#### 決策 2：lexicon_size 不觸發 lazy load

**理由**：若 `lexicon_size` 主動觸發 `_load_lexicon()`，則 `lexicon_size` 本身就成為 lazy load 觸發點，破壞「只在 `apply()` 觸發」的設計約束。

#### 決策 3：JSON 詞典根節點為 `{"lexicon_tw": [...]}`

**理由**：避免直接 expose 全域命名空間，預留未來擴充其他 `lexicon_*` 欄位的彈性。

### 錯誤碼對照表

| 錯誤碼 | 意義 | 觸發時機 |
|--------|------|---------|
| L1-001 | 詞典檔案不存在或非檔案 | `__init__` 時路徑檢查 |
| L1-002 | 詞典路徑未設定 | `_load_lexicon()` 無路徑 |
| L1-003 | 詞典檔案讀取失敗 | `_load_lexicon()` `open()` 例外 |
| L1-004 | 詞典 JSON 格式錯誤 | `_load_lexicon()` `json.load()` 例外 |
| L1-005 | lexicon_tw 非 list | `_load_lexicon()` JSON 結構檢查 |
| L1-006 | 輸入必須為 str 類型 | `apply()` 型別檢查 |
| L1-007 | reload 時詞典檔案不存在 | `reload()` 路徑檢查 |

### 測試覆蓋矩陣

| 測試類別 | 數量 | 覆蓋內容 |
|---------|------|---------|
| 正向測試 | 7 | 單詞/多詞/SRS案例/發音/職業/長詞優先 |
| 邊界測試 | 6 | 空字串/無匹配/特殊字元/標點/大文件/重複from |
| 負面測試 | 7 | 無效路徑/錯誤JSON/缺失key/錯誤類型 |
| LazyInit 測試 | 4 | 延遲載入/lexicon_size/reload/reset |
| SRS門檻測試 | 1 | 詞彙數 ≥ 50 |

**總計：25 測試，全部通過**
**覆蓋率：94%（門檻 ≥ 70%）**

---

## Architect / Reviewer Agent B 填寫區

### 邏輯正確性確認

| 項目 | 確認結果 | 備註 |
|------|---------|------|
| FR-01 詞彙數 ≥ 50 | ⬜ | |
| 單次正則穿越邏輯正確 | ⬜ | |
| Lazy Init 未在 `__init__` 觸發 | ⬜ | |
| L1 錯誤碼完整性 | ⬜ | |
| 測試覆蓋率 ≥ 70% | ⬜ | |
| SRS 邏輯驗證案例通過 | ⬜ | |

### 審查結論

- [ ] **APPROVE** — 符合 FR-01 規範，可進入 Phase 3 下一模組
- [ ] **REJECT** — 需修復以下問題：______

### 審查人
- session_id: ______
- 審查時間: ______

---

*本檔由 Developer Agent A 填寫，經 Reviewer Agent B 確認後生效*
