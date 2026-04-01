# ADR-003: Circuit Breaker Resilience Pattern

> **Date**: 2026-04-01  
> **Status**: Accepted  
> **Decider**: Johnny1027_bot (architect)

---

## Context

Kokoro Docker 後端可能崩潰或無回應，需要保護系統不因後端故障而完全失效。

## Decision

實現 **3-state Circuit Breaker** 模式：
- **CLOSED**: 正常操作，累計失敗計數
- **OPEN**: 快速失敗，不發送請求到後端
- **HALF-OPEN**: 測試後端是否恢復

## Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| failure_threshold | 3 | OPEN after 3 consecutive failures |
| recovery_timeout | 10.0s | Time in OPEN before HALF-OPEN |
| half_open_max_calls | 3 | Test calls in HALF-OPEN state |

## State Diagram

```
         ┌──────────────────────────────┐
         │                              │
         ▼                              │
    ┌────────┐                         │
    │ CLOSED │◄────────────────────┐   │
    └────┬───┘                     │   │
         │ success                  │   │
         │ failure (≥3)             │   │
         ▼                          │   │
    ┌────────┐                       │   │
    │  OPEN  │───────────────────────┘   │
    └────┬───┘                           │
         │ timeout (10s)                 │
         ▼                               │
    ┌───────────┐                        │
    │HALF-OPEN  │────── success ────────┘
    └───────────┘
         │
         │ failure
         ▼
    ┌────────┐
    │  OPEN  │
    └────────┘
```

## Implementation

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout=10.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
    
    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            raise CircuitOpenException("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
```

## Consequences

- **Positive**:
  - 後端故障時快速失敗
  - 避免雪崩效應
  - 自動恢復能力
- **Negative**:
  - 增加了複雜度
  - 需要正確設定閾值

---

*ADR 003 - Architecture Decision Record*
