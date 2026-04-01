# ADR-004：SSML 解析策略與 Kokoro API 映射

> 日期：2026-04-01  
> 狀態：ACCEPTED  
> 決策者：Phase 2 Architect Agent  
> 專案：tts-kokoro-v613

---

## 背景

FR-02 要求支援 SSML 標籤，並映射為 Kokoro API 參數。Kokoro 原生 API 參數：
- `text` — 合成文本
- `voice` — 音色名稱
- `speed` — 語速
- `返回` — MP3 音訊

SSML 標籤需轉換為這些參數的組合。

---

## 決策

**實作 SSML Parser，支援以下標籤，並在解析失敗時 fallback 純文字**

---

## 支援標籤對照表

| SSML 標籤 | 屬性 | Kokoro 映射 |
|-----------|------|------------|
| `<speak>` | — | 根元素，無映射 |
| `<break>` | `time="500ms"` | 插入停頓符（`...` 或 `[pause]`） |
| `<prosody>` | `rate="0.9"` | 映射為 `speed=0.9` |
| `<emphasis>` | `level="strong"` | 映射為 `speed *= 1.1` |
| `<voice>` | `name="zf_yunxi"` | 音色切換 |
| `<phoneme>` | `alphabet="ipa"` | 保留原生（直接輸出） |

---

## 實作策略

### 策略 1：標籤內聯（Inline）

將 SSML 標籤轉換為特殊標記，直接嵌入 Kokoro 請求文字：

```python
# 轉換後的文字格式
"大家好，這是[<voice:zf_yunxi>]語音合成[<voice:zf_xiaoxiao>]系統"
```

**優點**：簡單，單次請求  
**缺點**：Kokoro 需支援特殊標記解析

### 策略 2：分段多請求（採用）

將 SSML 解析為多個 segment，分別請求後拼接：

```python
# 解析後的結構
[
    {"text": "大家好，這是", "voice": "zf_xiaoxiao", "speed": 1.0},
    {"text": "語音合成", "voice": "zf_yunxi", "speed": 1.0},
    {"text": "系統", "voice": "zf_xiaoxiao", "speed": 1.0},
]
```

**優點**：兼容所有後端行為  
**缺點**：多次請求，增加延遲

### 策略 3：混合模式

- 無 `<voice>` 切換：單次請求（strategy 1）
- 有 `<voice>` 切換：分段多請求（strategy 2）

---

## Fallback 策略

```python
def parse_ssml(ssml_text: str) -> ParsedSSML:
    try:
        # 嘗試 XML 解析
        root = ET.fromstring(ssml_text)
        return _parse_element(root)
    except ET.ParseError:
        # Fallback：視為純文字
        return ParsedSSML(
            segments=[{"text": ssml_text, "voice": "zf_xiaoxiao", "speed": 1.0}]
        )
```

---

## 後果

### 正面
- SSML 解析失敗不影響整體服務（NFR-02 錯誤自動降級）
- 音色切換功能完整支援
- prosody/emphasis 正確映射

### 負面
- 多音色請求增加請求數量
- 需要 text_splitter 配合

---

## 審查狀態

| 項目 | 狀態 |
|------|------|
| 提案日期 | 2026-04-01 |
| 接受日期 | 2026-04-01 |
| Phase | Phase 2 |
