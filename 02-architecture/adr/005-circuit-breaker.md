# ADR-005 — 斷路器（Circuit Breaker）設計

> 狀態：已採納  
> 日期：2026-04-01  
> 決策者：Johnny Lu  

---

## 背景

FR-05 要求後端故障時自動保護，Kokoro Docker 可能崩潰、網路可能中斷。沒有斷路器時，後端故障會導致所有請求堆疊、超時、最終服務癱瘓。

NFR-04 要求 API 可用率 ≥ 99%，NFR-05/NFR-07 要求錯誤恢復時間 < 10s。

---

## 決策

**採用軟體斷路器模式，三態自動切換**。

### 狀態機

```
CLOSED ──(失敗 ≥ 3)──→ OPEN
  ↑                        │
  │                        │ (10 秒後)
  │                        ↓
  └──(HALF_OPEN 成功)← HALF_OPEN
```

### 替代方案分析

| 方案 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| **軟體斷路器（自研/pycircuit）** | 完全可控、可自訂閾值 | 需要實作狀態機 | ✅ 採用 |
| Nginx upstream | 簡單 | 無法精細控制（只能 upstream 級） | ❌ 放棄 |
| Hystrix（Java） | 成熟 | 語言不相容（Python 專案） | ❌ 放棄 |
| 無斷路器 | 簡單 | 後端故障影響整體服務 | ❌ 放棄 |

---

## 設計

```python
# middleware/circuit_breaker.py
from enum import Enum
from dataclasses import dataclass, field
import asyncio
import time

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    recovery_timeout: float = 10.0
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = field(default_factory=time.time)

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_failure_time = time.time()

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: 允許執行
        return True

    async def call(self, func, *args, **kwargs):
        if not self.can_execute():
            raise CircuitOpenError(f"Circuit {self.name} is OPEN")
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
            raise
```

**閾值配置**：
- 失敗閾值：3 次（可透過 `CIRCUIT_BREAKER_THRESHOLD` 調整）
- 恢復計時：10 秒（`CIRCUIT_BREAKER_TIMEOUT`）
- HTTP 503：OPEN 時直接返回，不發請求到後端

---

## 結果

### 正面
- 後端故障時快速失敗（< 10ms 返回 503）
- 10 秒後自動恢復，無需人工干預
- 避免級聯故障（後端崩潰不影響整體服務）

### 負面
- HALF_OPEN 狀態的測試需要等待計時器，增加測試複雜度
- 故障閾值需要根據實際流量調整

---

## 驗證

- FR-05：連續 3 次 5xx → Circuit OPEN → HTTP 503
- NFR-05：錯誤恢復時間 < 10s
- NFR-07：斷路器恢復 < 10s
