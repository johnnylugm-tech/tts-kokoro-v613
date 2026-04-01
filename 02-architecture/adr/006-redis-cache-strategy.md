# ADR-006 — Redis 快取策略（Optional Graceful Degradation）

> 狀態：已採納  
> 日期：2026-04-01  
> 決策者：Johnny Lu  

---

## 背景

FR-06 要求熱門語句結果快取（Key = hash(text+voice+speed)，TTL = 24h）。Redis 是可選依賴，無 Redis 時系統必須正常降級（NFR-04 API 可用率 ≥ 99%）。

---

## 決策

**Redis 作為可選快取，url=None 時自動略過，保持 100% 功能**。

### 替代方案分析

| 方案 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| **Redis Optional + Fallback** | 快取可選、降級無縫 | Redis 不可用時無快取 | ✅ 採用 |
| 必須有 Redis | 功能完整 | 部署複雜度增加 | ❌ 放棄 |
| 磁碟檔案快取 | 簡單 | 讀寫慢，TTL 管理複雜 | ❌ 放棄 |
| 記憶體快取（LRU） | 簡單 | 进程重啟丢失，無跨實例共享 | ❌ 放棄 |

---

## 理由

1. **部署靈活性**：開源/個人使用可能沒有 Redis，系統必須能獨立運行
2. **SRS 明確定義為可選**：SRS FR-06 說明「無 Redis 時自動略過」
3. **Graceful Degradation**：Redis 連線失敗不影響 TTS 功能
4. **Hash Key 設計**：簡單可靠，text+voice+speed 三元組唯一確定快取 entry

---

## 設計

```python
# cache/redis_cache.py
import hashlib
import redis
from typing import Optional

class RedisCache:
    def __init__(self, url: Optional[str] = None, ttl: int = 86400):
        self.ttl = ttl
        self.enabled = url is not None
        if self.enabled:
            self.client = redis.from_url(url, decode_responses=False)
        else:
            self.client = None

    def _make_key(self, text: str, voice: str, speed: float) -> str:
        raw = f"{text}:{voice}:{speed}"
        return f"tts:cache:{hashlib.sha256(raw.encode()).hexdigest()}"

    def get(self, text: str, voice: str, speed: float) -> Optional[bytes]:
        if not self.enabled:
            return None
        try:
            return self.client.get(self._make_key(text, voice, speed))
        except redis.RedisError:
            # Redis 錯誤：降級，不影響服務
            return None

    def set(self, text: str, voice: str, speed: float, audio: bytes) -> None:
        if not self.enabled:
            return
        try:
            self.client.setex(
                self._make_key(text, voice, speed),
                self.ttl,
                audio
            )
        except redis.RedisError:
            # Redis 錯誤：降級，快取寫入失敗不影響服務
            pass
```

**配置**：
- `REDIS_URL=None`：停用快取
- `REDIS_URL=redis://localhost:6379`：啟用快取
- TTL：24 小時（86400 秒）

---

## 結果

### 正面
- Redis 可選，部署無負擔
- Redis 故障時零影響（降級）
- Hash Key 均勻分布，避免熱點 key

### 負面
- 無 Redis 時每次請求都需要完整合成
- Redis 單點故障（可用 Redis Sentinel 緩解，但增加複雜度）

---

## 驗證

- FR-06：相同請求第二次 → 直接返回快取（無後端請求）
- FR-06：Redis 不可用時 → 正常降級至直接合成
- NFR-01：快取命中時 TTFB ≈ 0ms
