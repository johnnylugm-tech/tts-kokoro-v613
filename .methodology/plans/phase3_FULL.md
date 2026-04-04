# Phase 3 完整執行計劃 — 

> **版本**: v6.39.0
> **專案**: 
> **日期**: 2026-04-04
> **Framework**: methodology-v2 v6.39.0
> **Phase**: 3 - 代碼實作
> **狀態**: 完整版（含 Phase 3 詳細任務）

---

## Phase 3 任務：代碼實作

### Phase 3 概述
Phase 3 依據 SAD 實作所有 FR 模組，包含單元測試。

### FR 實作任務（共 8 項）

#### FR-01: FR-01：台灣中文詞彙映射
**任務**：在文本傳入 TTS 引擎前，進行台灣特有詞彙與發音的 LEXICON 映射。
**測試案例**：
- 輸入「我要坐地鐵去看視頻」→ 輸出「我要坐捷運去看影片」
- 輸入「菠蘿麵包」→ 輸出「鳳梨麵包」
**SAD 對應**：
- 模組：`lexicon_mapper`
- 檔案：`app/processing/lexicon_mapper.py`
**Forbidden**：
- ❌ app/infrastructure/（已廢除）
- ❌ @covers: L1 Error
- ❌ @type: edge

#### FR-02: FR-02：SSML 解析（含 `<voice>` 標籤）
**任務**：解析 SSML 標籤並映射為 Kokoro API 參數，支援音色切換。
**SAD 對應**：
- 模組：`ssml_parser`
- 檔案：`app/processing/ssml_parser.py`
**Forbidden**：
- ❌ app/infrastructure/（已廢除）
- ❌ @covers: L1 Error
- ❌ @type: edge

#### FR-03: FR-03：智能文本切分（Chunk ≤ 250 字）
**任務**：將長文本依三級遞迴邏輯切分，確保每段 ≤ 250 字。
**SAD 對應**：
- 模組：`text_chunker`
- 檔案：`app/processing/text_chunker.py`
**Forbidden**：
- ❌ app/infrastructure/（已廢除）
- ❌ @covers: L1 Error
- ❌ @type: edge

#### FR-04: FR-04：並行合成引擎
**任務**：使用 httpx.AsyncClient 同時發出 N 個請求，MP3 直接串接。
**SAD 對應**：
- 模組：`synth_engine`
- 檔案：`app/synth/synth_engine.py`
**Forbidden**：
- ❌ app/infrastructure/（已廢除）
- ❌ @covers: L1 Error
- ❌ @type: edge

#### FR-05: FR-05：斷路器（Circuit Breaker）
**任務**：後端故障時自動保護，失敗計數達閾值後断路。
**SAD 對應**：
- 模組：`circuit_breaker`
- 檔案：`app/infrastructure/circuit_breaker.py`
**Forbidden**：
- ❌ app/infrastructure/（已廢除）
- ❌ @covers: L1 Error
- ❌ @type: edge

#### FR-06: FR-06：Redis 快取（可選）
**任務**：熱門語句結果快取，24 小時 TTL。
**SAD 對應**：
- 模組：`redis_cache`
- 檔案：`app/infrastructure/redis_cache.py`
**Forbidden**：
- ❌ app/infrastructure/（已廢除）
- ❌ @covers: L1 Error
- ❌ @type: edge

#### FR-07: FR-07：CLI 命令列工具（tts-v610）
**任務**：提供命令列工具支援快速語音合成。
**SAD 對應**：
- 模組：`routes`
- 檔案：`app/api/routes.py`
**Forbidden**：
- ❌ app/infrastructure/（已廢除）
- ❌ @covers: L1 Error
- ❌ @type: edge

#### FR-08: FR-08：ffmpeg 音訊格式轉換
**任務**：使用 ffmpeg 將 MP3 轉換為 WAV，或 WAV 轉 MP3。
**SAD 對應**：
- 模組：`audio_converter`
- 檔案：`app/infrastructure/audio_converter.py`
**Forbidden**：
- ❌ app/infrastructure/（已廢除）
- ❌ @covers: L1 Error
- ❌ @type: edge

### Phase 3 交付物
- [ ] `app/processing/` - 處理模組
- [ ] `app/synth/` - 合成模組
- [ ] `app/infrastructure/` - 基礎設施模組
- [ ] `app/api/` - API 路由
- [ ] `tests/` - 單元測試
