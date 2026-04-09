"""
[FR-05] 斷路器模組 (Circuit Breaker).

後端故障時自動保護，失敗計數達閾值後断路。
- 失敗 ≥ 3 次 → Open
- Open 後 10 秒 → Half-Open
- 成功 → Closed

Citations:
    SRS.md#L97-L105 (FR-05 需求描述與行為定義)
    SAD.md#L182 (CircuitBreaker 模組對映)
    ADR-005 (斷路器設計決策)
"""
from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Final, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAILURE_THRESHOLD: Final[int] = 3
"""失敗計數閾值，達到此值則断路。"""

RECOVERY_TIMEOUT: Final[float] = 10.0
"""Open 狀態後自動進入 Half-Open 的等待秒數。"""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CircuitBreakerOpen(Exception):
    """
    斷路器處於 Open 狀態，請求被拒絕。
    """

    def __init__(self, message: str = "Circuit breaker is OPEN") -> None:
        """
        [FR-05] 斷路器處於 Open 狀態，請求被拒絕。

        Citations:
            SRS.md#L97-L105 (FR-05 需求描述與行為定義)
            SAD.md#L182 (CircuitBreaker 模組對映)
        """
        self.message = message
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    """斷路器狀態枚舉。"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """
    [FR-05] 斷路器，保護後端免受連續故障影響。

    狀態機行為：
    - CLOSED：正常通行，失敗計數遞增；達到閾值 → OPEN
    - OPEN：拒絕所有請求；超時後 → HALF_OPEN
    - HALF_OPEN：允許一個試探請求；成功 → CLOSED；失敗 → OPEN

    Args:
        failure_threshold: 觸發断路的連續失敗次數，預設 3。
        recovery_timeout: Open 後進入 Half-Open 的秒數，預設 10.0。

    Attributes:
        state (CircuitState): 目前斷路器狀態。
        failure_count (int): 目前的連續失敗計數。

    Example:
        >>> cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        >>> try:
        ...     result = cb.call(some_flaky_function)
        ... except CircuitBreakerOpen:
        ...     print("Service unavailable")
    """

    def __init__(
        self,
        failure_threshold: int = FAILURE_THRESHOLD,
        recovery_timeout: float = RECOVERY_TIMEOUT,
    ) -> None:
        """
        [FR-05] 初始化斷路器。

        Citations:
            SRS.md#L97-L105 (FR-05 需求描述與行為定義)
            SAD.md#L182 (CircuitBreaker 模組對映)

        Args:
            failure_threshold: 觸發断路的連續失敗次數，預設 3。
            recovery_timeout: Open 後進入 Half-Open 的秒數，預設 10.0。
        """
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be a positive integer")
        if recovery_timeout < 0:
            raise ValueError("recovery_timeout must be non-negative")

        self._failure_threshold: Final[int] = failure_threshold
        self._recovery_timeout: Final[float] = recovery_timeout

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_attempted: bool = False

    # ---- Properties -------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """
        [FR-05] 取得目前狀態，自動處理計時器切換。

        Citations:
            SRS.md#L97-L105 (FR-05 需求描述與行為定義)
            SAD.md#L182 (CircuitBreaker 模組對映)
        """
        self._check_auto_transition()
        return self._state

    @property
    def failure_count(self) -> int:
        """
        [FR-05] 取得目前連續失敗計數。

        Citations:
            SRS.md#L97-L105 (FR-05 需求描述與行為定義)
            SAD.md#L182 (CircuitBreaker 模組對映)
        """
        return self._failure_count

    # ---- Public API --------------------------------------------------------

    def call(self, func: callable, *args: object, **kwargs: object) -> object:
        """
        [FR-05] 帶断路器保護的同步函式呼叫。

        Citations:
            SRS.md#L97-L105 (FR-05 需求描述與行為定義)
            SAD.md#L182 (CircuitBreaker 模組對映)

        Args:
            func: 要執行的函式。
            *args: 位置引數。
            **kwargs: 關鍵字引數。

        Returns:
            函式回傳值。

        Raises:
            CircuitBreakerOpen: 斷路器處於 Open/Half-Open 且試探失敗。
        """
        self._check_auto_transition()

        if self._state == CircuitState.OPEN:
            raise CircuitBreakerOpen(
                f"Circuit breaker is OPEN. Retry after {self._recovery_timeout}s."
            )

        if self._state == CircuitState.HALF_OPEN:
            # 在 Half-Open 只允許一次試探
            return self._half_open_call(func, *args, **kwargs)

        # CLOSED 狀態：正常執行
        return self._closed_call(func, *args, **kwargs)

    async def call_async(self, coro: object, *args: object, **kwargs: object) -> object:
        """
        [FR-05] 帶断路器保護的非同步協程呼叫。

        Citations:
            SRS.md#L97-L105 (FR-05 需求描述與行為定義)
            SAD.md#L182 (CircuitBreaker 模組對映)

        Args:
            coro: 非同步協程工廠（傳入協程物件本身，而非尚未包裝的函式）。
            *args: 位置引數。
            **kwargs: 關鍵字引數。

        Returns:
            協程回傳值。

        Raises:
            CircuitBreakerOpen: 斷路器處於 Open/Half-Open 且試探失敗。
        """
        self._check_auto_transition()

        if self._state == CircuitState.OPEN:
            raise CircuitBreakerOpen(
                f"Circuit breaker is OPEN. Retry after {self._recovery_timeout}s."
            )

        if self._state == CircuitState.HALF_OPEN:
            return await self._half_open_call_async(coro, *args, **kwargs)

        return await self._closed_call_async(coro, *args, **kwargs)

    def record_success(self) -> None:
        """
        [FR-05] 記錄一次成功呼叫。

        Citations:
            SRS.md#L97-L105 (FR-05 需求描述與行為定義)
            SAD.md#L182 (CircuitBreaker 模組對映)

        任何成功都會重置失敗計數並將狀態設為 CLOSED。
        """
        self._failure_count = 0
        self._half_open_attempted = False
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """
        [FR-05] 記錄一次失敗呼叫。


        Citations:
            SRS.md#L97-L105 (FR-05 需求描述與行為定義)
            SAD.md#L182 (CircuitBreaker 模組對映)
        達到閾值後將狀態設為 OPEN，並記錄首次失敗時間。
        """
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        """
        [FR-05] 重置斷路器至初始 CLOSED 狀態，清除所有計數。

        Citations:
            SRS.md#L97-L105 (FR-05 需求描述與行為定義)
            SAD.md#L182 (CircuitBreaker 模組對映)
        """
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_attempted = False

    # ---- Internal helpers --------------------------------------------------

    def _check_auto_transition(self) -> None:
        """檢查計時器，必要時自動將 OPEN 轉為 HALF_OPEN。"""
        if self._state != CircuitState.OPEN:
            return

        if self._last_failure_time is None:
            return

        elapsed = time.monotonic() - self._last_failure_time
        if elapsed >= self._recovery_timeout:
            self._state = CircuitState.HALF_OPEN
            self._half_open_attempted = False

    def _closed_call(self, func: callable, *args: object, **kwargs: object) -> object:
        """CLOSED 狀態的執行包裝。"""
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    async def _closed_call_async(
        self, coro: object, *args: object, **kwargs: object
    ) -> object:
        """CLOSED 狀態的 async 執行包裝。"""
        try:
            result = await coro
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    def _half_open_call(self, func: callable, *args: object, **kwargs: object) -> object:
        """HALF_OPEN 狀態的單次試探執行。"""
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self._state = CircuitState.OPEN
            self._half_open_attempted = True
            self._last_failure_time = time.monotonic()
            raise

    async def _half_open_call_async(
        self, coro: object, *args: object, **kwargs: object
    ) -> object:
        """HALF_OPEN 狀態的 async 單次試探執行。"""
        try:
            result = await coro
            self.record_success()
            return result
        except Exception:
            self._state = CircuitState.OPEN
            self._half_open_attempted = True
            self._last_failure_time = time.monotonic()
            raise
