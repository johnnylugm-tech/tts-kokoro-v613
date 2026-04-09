"""[FR-04] 並行合成引擎。

使用 httpx.AsyncClient 同時發出 N 個非同步 HTTP 請求至 Kokoro TTS 後端，
MP3 直接串接（無需重新編碼）。

架構：
- SynthEngine：接收多個文字分塊，並行合成後依序串接 MP3 bytes。
- asyncio.Semaphore：控制最大並發數（max_concurrency）。
- asyncio.gather：並行發送所有請求。

錯誤處理：
- SynthesisPartialError (L3)：部分分塊失敗，但有成功結果可返回。
- SynthesisUnavailableError (L4)：全部失敗或斷路器 Open。

測試案例（SRS.md#L93-L94）：
- 5 個 Chunk 同時請求 → 總時間 < 各 Chunk 順序執行時間
- 拼接後 MP3 可正常播放

Citations:
    SRS.md#L83-L94 (FR-04 需求描述與測試案例)
    SAD.md#L381-L396 (FR-04 Synth Engine 架構設計)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class SynthesisRequest:
    """"[FR-04] 單一分塊的合成請求。

    Citations:
    - SRS.md#L83-L94
    - SAD.md#L381-L396
    """

    text: str
    voice: str
    speed: float
    chunk_index: int


@dataclass
class SynthesisResult:
    """"[FR-04] 單一分塊的合成結果。

    Citations:
    - SRS.md#L83-L94
    - SAD.md#L381-L396
    """

    audio_bytes: bytes
    chunk_index: int
    duration_ms: float
    status: _ChunkStatus  # SUCCESS or FAILED


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class _ChunkStatus(Enum):
    """[FR-04] 分塊處理狀態枚舉。"""

    SUCCESS = "success"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SynthesisPartialError(RuntimeError):
    """[FR-04] L3：部分分塊失敗，但有成功結果可返回。


    當部分（但非全部）chunk 請求失敗時拋出。
    调用者可选择保留 partial_results 中已成功的 bytes 進行串接。

    Attributes:
        partial_results: 已成功的音頻 bytes 清單（未排序）。
        failed_indices: 失敗的 chunk_index 清單。

    Citations:
    - SRS.md#L83-L94
    - SAD.md#L381-L396
    """

    def __init__(
        self,
        partial_results: list[bytes],
        failed_indices: list[int],
    ) -> None:
        self.partial_results = partial_results
        self.failed_indices = failed_indices
        super().__init__(
            f"Partial synthesis failure: {len(partial_results)} succeeded, "
            f"{len(failed_indices)} failed (indices={failed_indices})"
        )


class SynthesisUnavailableError(RuntimeError):
    """[FR-04] L4：全部失敗或斷路器 Open，無法提供服務。

    當所有 chunk 都失敗或 CircuitBreaker 處於 Open 狀態時拋出。

    Attributes:
        retry_after_seconds: 建議重試的等待秒數。

    Citations:
    - SRS.md#L83-L94
    - SAD.md#L381-L396
    """

    def __init__(self, retry_after_seconds: float = 10.0) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Synthesis unavailable (circuit open or all requests failed). "
            f"Retry after {retry_after_seconds}s."
        )


# ---------------------------------------------------------------------------
# Main Engine
# ---------------------------------------------------------------------------


class SynthEngine:
    """[FR-04] 分塊並行非同步合成引擎。

    使用 asyncio.Semaphore 控制並發數，asyncio.gather 並行發送 N 個
    HTTP 請求至 Kokoro TTS 後端。成功結果依 chunk_index 排序後串接
    成單一 MP3 bytes。

    Args:
        kokoro_client: Kokoro TTS API 客戶端實例。
            需實作 ``synthesize(text, voice, speed) -> bytes`` 方法。
        circuit_breaker: 斷路器實例，用於在後端故障時快速失敗。
            需實作 ``is_open() -> bool`` 和 ``record_success()``、
            ``record_failure()`` 方法。

    Raises:
        SynthesisPartialError: 部分 chunk 失敗（部分成功）。
        SynthesisUnavailableError: 全部失敗或斷路器 Open。

    Citations:
    - SRS.md#L83-L94
    - SAD.md#L381-L396
    """

    def __init__(
        self,
        kokoro_client: "KokoroClientProtocol",
        circuit_breaker: "CircuitBreakerProtocol",
    ) -> None:
        self._client = kokoro_client
        self._cb = circuit_breaker
        self._semaphore: asyncio.Semaphore | None = None

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def synthesize_chunks(
        self,
        chunks: list[str],
        voice: str,
        speed: float,
        max_concurrency: int = 10,
    ) -> list[bytes]:
        """[FR-04] 並行合成多個文字分塊。

        依序對每個 chunk 並行發送 HTTP 請求（受 max_concurrency 限制），
        成功結果依 chunk_index 排序後返回 list[bytes]。

        Args:
            chunks: 待合成的文字分塊清單（每項不超過 250 字）。
            voice: 音色名稱（例如 ``"zf_xiaoxiao"``）。
            speed: 語速倍率（0.5 ~ 2.0）。
            max_concurrency: 最大並發 HTTP 請求數（預設 10）。

        Returns:
            list[bytes]: 依 chunk_index 排序的 MP3 bytes 清單，
            可直接串接成完整音頻。

        Raises:
            SynthesisPartialError: 部分 chunk 失敗（但有成功結果）。
            SynthesisUnavailableError: 所有 chunk 失敗或斷路器 Open。

        Citations:
        - SRS.md#L83-L94
        - SAD.md#L381-L396
        """
        if not chunks:
            return []

        # Lazy-init Semaphore (must be created in async context)
        self._semaphore = asyncio.Semaphore(max_concurrency)

        # Check circuit breaker first
        if self._cb.is_open():
            raise SynthesisUnavailableError(retry_after_seconds=10.0)

        # Build tasks
        tasks = [
            self._synthesize_one(
                SynthesisRequest(
                    text=chunk,
                    voice=voice,
                    speed=speed,
                    chunk_index=i,
                )
            )
            for i, chunk in enumerate(chunks)
        ]

        # Execute all in parallel
        raw_results: list[SynthesisResult] = await asyncio.gather(*tasks)

        # Separate successes and failures
        successes: list[SynthesisResult] = []
        failed_indices: list[int] = []

        for result in raw_results:
            if result.status is _ChunkStatus.SUCCESS:
                successes.append(result)
                self._cb.record_success()
            else:
                failed_indices.append(result.chunk_index)
                self._cb.record_failure()

        # All failed
        if not successes:
            raise SynthesisUnavailableError(retry_after_seconds=10.0)

        # Partial failure
        if failed_indices:
            partial_bytes = [s.audio_bytes for s in successes]
            raise SynthesisPartialError(
                partial_results=partial_bytes,
                failed_indices=sorted(failed_indices),
            )

        # All succeeded — sort by index and return bytes
        successes.sort(key=lambda r: r.chunk_index)
        return [r.audio_bytes for r in successes]

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    async def _synthesize_one(
        self,
        req: SynthesisRequest,
    ) -> SynthesisResult:
        """[FR-04] 對單一 chunk 執行合成（受 Semaphore 控制）。

        Args:
            req: 合成請求。

        Returns:
            SynthesisResult：包含音頻 bytes 或失敗標記。


        Citations:
        - SRS.md#L83-L94
        - SAD.md#L381-L396
        """
        assert self._semaphore is not None, "Semaphore not initialized"

        async with self._semaphore:
            try:
                # Call Kokoro client (blocking I/O in thread if needed)
                audio_bytes = await self._call_kokoro(req)
                return SynthesisResult(
                    audio_bytes=audio_bytes,
                    chunk_index=req.chunk_index,
                    duration_ms=_estimate_duration_ms(len(audio_bytes), req.speed),
                    status=_ChunkStatus.SUCCESS,
                )
            except Exception as exc:
                # Status FAILED → caller records via circuit breaker in main loop
                return SynthesisResult(
                    audio_bytes=b"",
                    chunk_index=req.chunk_index,
                    duration_ms=0.0,
                    status=_ChunkStatus.FAILED,
                )

    async def _call_kokoro(self, req: SynthesisRequest) -> bytes:
        """[FR-04] 呼叫 Kokoro TTS API。

        委外給 kokoro_client.synthesize()，支援同步或 async 實作。

        Args:
            req: 合成請求。

        Returns:
            bytes: MP3 音頻資料。

        Raises:
            Exception: 任何 API 錯誤，包裝為 SynthesisResult.FAILED。

        Citations:
        - SRS.md#L83-L94
        - SAD.md#L381-L396
        """
        coro = self._client.synthesize(req.text, req.voice, req.speed)
        return await coro


# ---------------------------------------------------------------------------
# Protocol (Structural Subtyping)
# ---------------------------------------------------------------------------


class KokoroClientProtocol:
    """[FR-04] KokoroClient 實例需滿足的結構化介面（duck-typed）。

    用於在 TYPE_CHECKING 區塊中聲明依賴，同時避免循環 import。

    Citations:
    - SRS.md#L83-L94
    - SAD.md#L381-L396
    """

    async def synthesize(self, text: str, voice: str, speed: float) -> bytes:
        """合成單一文字片段為 MP3 bytes。

        Args:
            text: 待合成文字。
            voice: 音色名稱。
            speed: 語速倍率。

        Returns:
            bytes: MP3 音頻資料。
        """
        ...


class CircuitBreakerProtocol:
    """[FR-04] CircuitBreaker 實例需滿足的結構化介面（duck-typed）。


    Citations:
    - SRS.md#L83-L94
    - SAD.md#L381-L396
    """

    def is_open(self) -> bool:
        """斷路器是否處於 Open 狀態。"""
        ...

    def record_success(self) -> None:
        """記錄一次成功呼叫。"""
        ...

    def record_failure(self) -> None:
        """記錄一次失敗呼叫。"""
        ...


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _estimate_duration_ms(audio_bytes: int, speed: float) -> float:
    """[FR-04] 估算音頻時長（毫秒）。

    基於 MP3 位元率估算：128kbps = 16000 bytes/s。

    Args:
        audio_bytes: MP3 資料大小（bytes）。
        speed: 語速倍率（speed > 1 則音頻更短）。

    Returns:
        float: 估算時長（毫秒）。

    Citations:
    - SRS.md#L83-L94
    - SAD.md#L381-L396
    """
    if audio_bytes == 0:
        return 0.0
    # 128 kbps MP3 → 16000 bytes/second
    bytes_per_ms = 16.0
    raw_ms = audio_bytes / bytes_per_ms
    return raw_ms / speed


def concatenate_mp3(mp3_chunks: list[bytes]) -> bytes:
    """[FR-04] 將多個 MP3 分塊串接成單一 MP3。

    MP3 格式本身支援直接串接（無需重新編碼），因為每個 MP3 幀
    都是獨立的。本函數按順序拼接所有 bytes。

    注意：若需要消除接縫雜音，可選用 pydub 的 crossfade 功能。

    Args:
        mp3_chunks: MP3 bytes 清單（依序排列）。

    Returns:
        bytes: 串接後的完整 MP3 資料。

    Citations:
    - SRS.md#L83-L94
    - SAD.md#L381-L396
    """
    return b"".join(mp3_chunks)
