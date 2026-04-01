# ADR-003 — SSML 解析策略

> 狀態：已採納  
> 日期：2026-04-01  
> 決策者：Johnny Lu  

---

## 背景

FR-02 要求解析 SSML 標籤（`<speak>`, `<break>`, `<prosody>`, `<voice>`, `<phoneme>`, `<emphasis>`）並映射為 Kokoro API 參數。Kokoro 後端本身不支援 SSML，需在代理層解析並轉換為 HTTP 參數。

---

## 決策

**採用手寫 XML Parser + AST 結構**，解析後轉換為 Kokoro 參數。

### 替代方案分析

| 方案 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| **手寫 XML Parser** | 輕量、控制精確、易於除錯 | 需自行處理邊界情況 | ✅ 採用 |
| lxml / xml.etree | 標準庫，處理命名空間 | 額外依賴、SSML 不需要完整 XML 功能 | ❌ 放棄 |
| 正規表達式 | 簡單 | 無法處理巢狀標籤 | ❌ 放棄 |

---

## 理由

1. **SSML 子集可控**：本系統只支援 6 種標籤，不需要完整 XML 解析器
2. **輕量優先**：NFR-01 TTFB < 300ms，額外 XML 解析器增加延遲
3. **易於除錯**：手寫解析器產生的 AST 可直接序列化為日誌
4. **Fallback 簡單**：解析失敗時可 fallback 為純文字（不丟失功能）

---

## 設計

```python
# engines/ssml_parser.py
from dataclasses import dataclass
from enum import Enum

class SSMLTag(Enum):
    SPEAK = "speak"
    BREAK = "break"
    PROSODY = "prosody"
    VOICE = "voice"
    PHONEME = "phoneme"
    EMPHASIS = "emphasis"

@dataclass
class SSMLElement:
    tag: SSMLTag
    attrs: dict
    text: str = ""
    children: list["SSMLElement"] = None

class SSMLParser:
    def parse(self, ssml: str) -> SSMLDocument:
        """Parse SSML string into AST"""
        ...

    def to_kokoro_params(self, doc: SSMLDocument) -> list[dict]:
        """Convert SSML AST to Kokoro API parameters"""
        ...
```

**Kokoro 參數映射**：

| SSML 標籤 | Kokoro 參數 |
|----------|-------------|
| `<prosody rate="0.9">` | `speed=0.9` |
| `<voice name="zf_yunxi">` | `voice=zf_yunxi` |
| `<break time="500ms">` | 插入停頓字元 |
| `<emphasis level="strong">` | `speed *= 1.1` |
| `<phoneme alphabet="ipa">` | 保留原生 IPA |

---

## 結果

### 正面
- 最小依賴，無額外套件
- 解析邏輯完全可控
- 可單元測試每個標籤的解析

### 負面
- 需要處理 XML 逃逸字元（`&lt;` → `<`）
- 巢狀標籤邊界情況需小心處理

---

## 驗證

- FR-02：各標籤解析結果單元測試
- 失敗 Fallback：XML 解析失敗時返回純文字（不中斷服務）
