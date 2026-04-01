# ADR-004 — 非同步並行合成引擎

> 狀態：已採納  
> 日期：2026-04-01  
> 決策者：Johnny Lu  

---

## 背景

FR-03 要求長文本切分為 ≤ 250 字 Chunk，FR-04 要求使用 `httpx.AsyncClient` 同時發出 N 個請求，並直接串接 MP3。順序執行會導致 TTFB 線性增長，無法滿足 NFR-01（TTFB < 300ms）。

---

## 決策

**採用 `httpx.AsyncClient` + `asyncio.gather` 並行合成，MP3 二進位串接**。

### 替代方案分析

| 方案 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| **httpx.AsyncClient + gather** | 標準非同步、連線池管理、超時控制 | 需要 asyncio 上下文 | ✅ 採用 |
| ThreadPoolExecutor | 簡單 | GIL 限制，Python 多執行緒效率低 | ❌ 放棄 |
| multiprocessing | 繞過 GIL | 啟動慢，進程間通信複雜 | ❌ 放棄 |
| Celery / RQ | 跨程序 | 過度工程，單機不需要任務佇列 | ❌ 放棄 |

---

## 理由

1. **異步優先**：httpx.AsyncClient 原生支援連線池、超時、重試，asyncio.gather 自然並行
2. **MP3 直接串接**：Kokoro 回傳 MP3 bytes，串接後無需重新編碼
3. **記憶體效率**：Streaming response 可邊下載邊串接
4. **自然對應 TextSplitter**：每個 Chunk 對應一個 Kokoro 請求

---

## 設計

```python
# engines/synthesis.py
import httpx
import asyncio

class AsyncSynthesisEngine:
    def __init__(self, backend_url: str, max_concurrent: int = 5):
        self.backend_url = backend_url
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def synthesize_chunk(
        self,
        client: httpx.AsyncClient,
        chunk: str,
        voice: str,
        speed: float
    ) -> bytes:
        async with self.semaphore:
            response = await client.post(
                f"{self.backend_url}/v1/audio/speech",
                json={"input": chunk, "voice": voice, "speed": speed},
                timeout=30.0
            )
            response.raise_for_status()
            return response.content

    async def synthesize(self, chunks: list[str], voice: str, speed: float) -> bytes:
        async with httpx.AsyncClient() as client:
            tasks = [
                self.synthesize_chunk(client, chunk, voice, speed)
                for chunk in chunks
            ]
            results = await asyncio.gather(*tasks)
            # MP3 直接串接（無需重新編碼）
            return b"".join(results)
```

**連接池配置**：
- `limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)`
- `max_concurrent=5`（避免對 Kokoro 後端造成壓力）

---

## 結果

### 正面
- TTFB = max(各 Chunk 時間)，比順序執行快 N 倍
- 連線池復用，減少 TCP 握手開銷
- 簡單實作，無額外訊息佇列依賴

### 負面
- 單個 Chunk 失敗會導致整體失敗（需搭配 CircuitBreaker）
- Kokoro 後端瓶頸：後端來不及處理時，並行無效

---

## 驗證

- FR-04：5 個 Chunk 並行時間 < 順序執行時間
- NFR-01：TTFB < 300ms（並行合成加持）
- CircuitBreaker：單個 Chunk 失敗不影響整體（CircuitBreaker 保護）
