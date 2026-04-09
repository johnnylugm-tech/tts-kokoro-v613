"""
[FR-05] 測試案例：斷路器 (Circuit Breaker).

後端故障時自動保護，失敗計數達閾值後断路。
- 失敗 ≥ 3 次 → Open
- Open 後 10 秒 → Half-Open
- 成功 → Closed

測試案例（對應 SRS.md#L101-L104）：
- 連續 3 次 5xx 錯誤 → 斷路器 Open
- 斷路後請求 → HTTP 503（本模組拋出 CircuitBreakerOpen）

Citations:
    SRS.md#L97-L105 (FR-05 需求描述與測試案例)
    SRS.md#L101-L104 (邏輯驗證方法與測試案例)
    SAD.md#L182 (CircuitBreaker 模組對映)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

# Ensure the project root is on the import path.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    FAILURE_THRESHOLD,
    RECOVERY_TIMEOUT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cb() -> CircuitBreaker:
    """建立一個使用預設參數的全新断路器。"""
    return CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)


@pytest.fixture
def fast_cb() -> CircuitBreaker:
    """建立一個 recovery_timeout=0.1s 的快速断路器（用於計時測試）。"""
    return CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)


# ---------------------------------------------------------------------------
# Constants verification
# ---------------------------------------------------------------------------

class TestConstants:
    """驗證模組常數符合 SRS 規格。"""

    def test_failure_threshold_is_3(self) -> None:
        assert FAILURE_THRESHOLD == 3

    def test_recovery_timeout_is_10(self) -> None:
        assert RECOVERY_TIMEOUT == 10.0


# ---------------------------------------------------------------------------
# State machine transitions — CLOSED
# ---------------------------------------------------------------------------

class TestClosedState:
    """CLOSED 狀態行為測試。"""

    def test_initial_state_is_closed(self, cb: CircuitBreaker) -> None:
        assert cb.state == CircuitState.CLOSED

    def test_success_in_closed_keeps_closed(self, cb: CircuitBreaker) -> None:
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_one_failure_below_threshold_stays_closed(self, cb: CircuitBreaker) -> None:
        """1 次失敗 < 閾值 3，仍為 CLOSED。"""
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1

    def test_two_failures_below_threshold_stays_closed(self, cb: CircuitBreaker) -> None:
        """2 次失敗 < 閾值 3，仍為 CLOSED。"""
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 2

    def test_call_with_exception_records_failure(self, cb: CircuitBreaker) -> None:
        """CLOSED 狀態：成功執行（不拋例外）。"""
        def flaky() -> int:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            cb.call(flaky)

        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# State machine transitions — OPEN
# ---------------------------------------------------------------------------

class TestOpenState:
    """OPEN 狀態行為測試。"""

    def test_third_failure_opens_circuit(self, cb: CircuitBreaker) -> None:
        """失敗計數達到閾值 3 → OPEN（SRS#L98）。"""
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_call_raises_when_open(self, cb: CircuitBreaker) -> None:
        """斷路後請求拋出 CircuitBreakerOpen（SRS#L103）。"""
        # 觸發 OPEN
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            cb.call(lambda: 42)
        assert "OPEN" in str(exc_info.value)

    def test_failure_in_open_increments_count(self, cb: CircuitBreaker) -> None:
        """OPEN 狀態下 record_failure 只遞增計數，不改變狀態。"""
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        initial_count = cb.failure_count

        cb.record_failure()
        assert cb.failure_count == initial_count + 1
        assert cb.state == CircuitState.OPEN

    def test_success_in_open_closes_circuit(self, cb: CircuitBreaker) -> None:
        """OPEN 狀態下 record_success 重置為 CLOSED。"""
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


# ---------------------------------------------------------------------------
# State machine transitions — HALF_OPEN
# ---------------------------------------------------------------------------

class TestHalfOpenState:
    """HALF_OPEN 狀態行為測試。"""

    def test_auto_transition_to_half_open_after_timeout(
        self, fast_cb: CircuitBreaker
    ) -> None:
        """Open 後經過 recovery_timeout → HALF_OPEN（SRS#L99）。"""
        for _ in range(3):
            fast_cb.record_failure()
        assert fast_cb.state == CircuitState.OPEN

        # 等待 recovery_timeout
        time.sleep(0.15)

        # 存取 state property 觸發自動轉換檢查
        assert fast_cb.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_closes_circuit(
        self, fast_cb: CircuitBreaker
    ) -> None:
        """HALF_OPEN 成功 → CLOSED（SRS#L100）。"""
        for _ in range(3):
            fast_cb.record_failure()
        assert fast_cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert fast_cb.state == CircuitState.HALF_OPEN

        result = fast_cb.call(lambda: "ok")
        assert result == "ok"
        assert fast_cb.state == CircuitState.CLOSED

    def test_failure_in_half_open_reopens_circuit(
        self, fast_cb: CircuitBreaker
    ) -> None:
        """HALF_OPEN 失敗 → 回到 OPEN。"""
        for _ in range(3):
            fast_cb.record_failure()
        assert fast_cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert fast_cb.state == CircuitState.HALF_OPEN

        def boom() -> int:
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            fast_cb.call(boom)

        assert fast_cb.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# Integration: full failure → open → recover → close cycle
# ---------------------------------------------------------------------------

class TestFullCycle:
    """完整狀態機生命週期測試。"""

    def test_full_cycle_open_to_close(self, fast_cb: CircuitBreaker) -> None:
        """完整循環：CLOSED → 3次失敗 → OPEN → timeout → HALF_OPEN → 成功 → CLOSED。"""
        # Phase 1: CLOSED → OPEN
        for _ in range(3):
            fast_cb.record_failure()
        assert fast_cb.state == CircuitState.OPEN

        # Phase 2: OPEN → HALF_OPEN
        time.sleep(0.15)
        assert fast_cb.state == CircuitState.HALF_OPEN

        # Phase 3: HALF_OPEN → CLOSED
        result = fast_cb.call(lambda: 200)
        assert result == 200
        assert fast_cb.state == CircuitState.CLOSED

    def test_full_cycle_open_half_open_fail_open(self, fast_cb: CircuitBreaker) -> None:
        """HALF_OPEN 失敗：OPEN → timeout → HALF_OPEN → 失敗 → OPEN。"""
        for _ in range(3):
            fast_cb.record_failure()
        assert fast_cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert fast_cb.state == CircuitState.HALF_OPEN

        def fail() -> None:
            raise ConnectionError("backend down")

        with pytest.raises(ConnectionError):
            fast_cb.call(fail)

        assert fast_cb.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# Async support
# ---------------------------------------------------------------------------

class TestAsync:
    """非同步 API 測試。"""

    @pytest.mark.asyncio
    async def test_async_success_transitions_to_closed(
        self, fast_cb: CircuitBreaker
    ) -> None:
        """Async 成功呼叫 → CLOSED。"""
        async def ok_coro() -> str:
            return "async ok"

        result = await fast_cb.call_async(ok_coro())
        assert result == "async ok"
        assert fast_cb.state == CircuitState.CLOSED
        assert fast_cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_async_failure_transitions_to_open(
        self, fast_cb: CircuitBreaker
    ) -> None:
        """Async 失敗 3 次 → OPEN。"""
        async def fail_coro() -> None:
            raise RuntimeError("async fail")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await fast_cb.call_async(fail_coro())
            assert fast_cb.state == CircuitState.CLOSED

        with pytest.raises(RuntimeError):
            await fast_cb.call_async(fail_coro())
        assert fast_cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_async_open_raises_on_call(self, fast_cb: CircuitBreaker) -> None:
        """OPEN 狀態下 async 呼叫拋出 CircuitBreakerOpen。"""
        for _ in range(3):
            fast_cb.record_failure()
        assert fast_cb.state == CircuitState.OPEN

        # Create the coroutine outside the raises block so it's never entered
        # when the circuit is already OPEN (avoids "coroutine never awaited" warning).
        async def any_coro() -> int:
            return 1

        coro = any_coro()
        with pytest.raises(CircuitBreakerOpen):
            await fast_cb.call_async(coro)
        # Manually close to suppress warning since OPEN rejects before await.
        coro.close()


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    """reset() 行為測試。"""

    def test_reset_from_open_to_closed(self, cb: CircuitBreaker) -> None:
        """從 OPEN 狀態 reset → CLOSED。"""
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_reset_clears_all_state(self, cb: CircuitBreaker) -> None:
        """reset() 清除所有內部狀態。"""
        cb.record_failure()
        cb.record_failure()
        cb.reset()
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """邊界條件測試。"""

    def test_callable_with_return_value(self, cb: CircuitBreaker) -> None:
        """驗證斷路器正確傳回函式回傳值。"""
        result = cb.call(lambda: "hello world")
        assert result == "hello world"

    def test_callable_with_args(self, cb: CircuitBreaker) -> None:
        """驗證 args 正確傳遞。"""
        def add(a: int, b: int) -> int:
            return a + b

        result = cb.call(add, 2, 3)
        assert result == 5

    def test_callable_with_kwargs(self, cb: CircuitBreaker) -> None:
        """驗證 kwargs 正確傳遞。"""
        def greet(name: str, greeting: str = "Hi") -> str:
            return f"{greeting}, {name}"

        result = cb.call(greet, "Jarvis", greeting="Hello")
        assert result == "Hello, Jarvis"

    def test_negative_threshold_raises(self) -> None:
        """閾值必須為正整數。"""
        with pytest.raises(ValueError):
            CircuitBreaker(failure_threshold=0)

    def test_negative_timeout_raises(self) -> None:
        """超時時間必須為非負數。"""
        with pytest.raises(ValueError):
            CircuitBreaker(recovery_timeout=-1.0)
