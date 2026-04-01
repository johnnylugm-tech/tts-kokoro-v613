# ADR-001 — 採用 FastAPI + httpx 作為代理框架

> 狀態：已採納  
> 日期：2026-04-01  
> 決策者：Johnny Lu  

---

## 背景

tts-kokoro-v613 需要一個代理層，將 Kokoro Docker 的舊版 API 包裝為符合台灣本地化需求的 TTS 系統。該代理層需要支援：
- 非同步 HTTP 請求（並行合成）
- SSML 解析與音色標籤處理
- CLI 工具
- 可選的 Redis 快取

---

## 決策

**採用 FastAPI + httpx 作為代理框架**，不放棄以下任一方案。

### 替代方案分析

| 方案 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| **FastAPI + httpx** | 非同步優先、類型提示完整、CLI 可用 Typer 整合 | 需要額外學習 FastAPI | ✅ 採用 |
| Flask + requests | 簡單 | 同步，無並行支援 | ❌ 放棄 |
| aiohttp | 非同步 | API 較低階，缺少類型提示 | ❌ 放棄 |
| gRPC | 高效能 | 與 Kokoro HTTP API不相容 | ❌ 放棄 |

---

## 理由

1. **非同步優先**：FR-04 要求並行合成 N 個 Chunk，httpx.AsyncClient + asyncio.gather 可自然實現
2. **類型提示完整**：NFR-06 要求單元測試覆蓋率 ≥ 80%，FastAPI 的 Pydantic 模型提供完整類型，助於測試
3. **生態豐富**：FastAPI 內建 OpenAPI 文件、依賴注入、middleware，方便擴展
4. **CLI 整合**：可用 Typer（基於 FastAPI 同一生態）實作 FR-07 CLI 工具

---

## 結果

### 正面
- 非同步並行合成易於實現
- Pydantic 模型驗證 SSML 解析結果
- OpenAPI 自動生成，降低 API 使用摩擦

### 負面
- 新增一個外部依賴（httpx）
- 需要管理異步生命週期（startup/shutdown）

---

## 驗證

- FR-04（並行合成）：使用 `httpx.AsyncClient` 實現
- NFR-01（TTFB < 300ms）：FastAPI 非同步路由確保低延遲
- NFR-06（測試覆蓋 ≥ 80%）：FastAPI TestClient 可直接測試端點
