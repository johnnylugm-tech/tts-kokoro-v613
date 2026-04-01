# ADR-001: FastAPI + httpx Proxy Layer

> **Date**: 2026-04-01  
> **Status**: Accepted  
> **Decider**: Johnny1027_bot (architect)

---

## Context

需要選擇代理層框架來轉發客戶端請求到 Kokoro Docker 後端。

## Decision

使用 **FastAPI + httpx** 作為代理層。

## Reasons

| Option | Pros | Cons |
|--------|------|------|
| **FastAPI + httpx** | Async-native, Pydantic validation, OpenAPI auto-generation, type hints | Learning curve |
| Flask + requests | Simple, familiar | Synchronous only, no type validation |
| gRPC | High performance | Complex setup, Kokoro doesn't support |

## Consequences

- **Positive**: 
  - httpx.AsyncClient 支援非同步 HTTP，適合並行合成
  - Pydantic 提供自動請求驗證
  - 自動生成 OpenAPI 文檔
- **Negative**:
  - 需要學習 FastAPI 框架

## Implementation

```python
from fastapi import FastAPI
import httpx

app = FastAPI()
client = httpx.AsyncClient(timeout=30.0)

@app.post("/v1/proxy/speech")
async def speech(data: SpeechRequest) -> StreamingResponse:
    # Proxy to Kokoro backend
    response = await client.post(f"{KOKORO_URL}/v1/audio/speech", json=data.model_dump())
    return StreamingResponse(response.iter_bytes(), media_type="audio/mp3")
```

---

*ADR 001 - Architecture Decision Record*
