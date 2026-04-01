# ADR-002: Redis Caching Strategy

> **Date**: 2026-04-01  
> **Status**: Accepted  
> **Decider**: Johnny1027_bot (architect)

---

## Context

需要快取熱門 TTS 請求結果，減少對 Kokoro 後端的重複呼叫。

## Decision

使用 **Redis** 作為快取層，Key = `hash(text + voice + speed)`，TTL = 24h。

## Reasons

| Option | Pros | Cons |
|--------|------|------|
| **Redis** | 高效能、TTL 支援、記憶體儲存 | 需要額外服務 |
| Memcached | 簡單、記憶體儲存 | No TTL, 不支援複雜 key |
| In-memory dict | No extra service | 重啟後快取消失 |

## Key Design

```python
def make_cache_key(text: str, voice: str, speed: float) -> str:
    """Generate cache key from request parameters"""
    content = f"{text}:{voice}:{speed}"
    return f"tts:v1:{hashlib.sha256(content.encode()).hexdigest()}"
```

## Consequences

- **Positive**:
  - 24h TTL 平衡快取新舊
  - 減少後端負載
  - 相同請求秒級回應
- **Negative**:
  - 需要 Redis 服務
  - 快取記憶體管理

## Graceful Degradation

若 Redis 不可用，系統應正常降級到直接合成，不影響可用性。

---

*ADR 002 - Architecture Decision Record*
