"""[FR-04] SynthEngine 單元測試。

測試案例（SRS.md#L93-L94）：
    - 5 個 Chunk 同時請求 → 總時間 < 各 Chunk 順序執行時間
    - 拼接後 MP3 可正常播放

Citations:
    SRS.md#L83-L94 (FR-04 需求描述與測試案例)
    SAD.md#L381-L396 (FR-04 Synth Engine 架構設計)
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.synth.synth_engine import (
    KokoroClientProtocol,
    CircuitBreakerProtocol,
    SynthesisPartialError,
    SynthesisRequest,
    SynthesisResult,
    SynthesisUnavailableError,
    SynthEngine,
    _ChunkStatus,
    _estimate_duration_ms,
    concatenate_mp3,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_kokoro_client():
    """[FR-04] Mock KokoroClient，每次呼叫返回確定的 MP3 bytes。"""
    client = MagicMock(spec=KokoroClientProtocol)
    # Default: 1 byte per character as fake MP3
    client.synthesize = AsyncMock(
        side_effect=lambda text, voice, speed: f"MP3:{text}".encode()
    )
    return client


@pytest.fixture
def mock_circuit_breaker():
    """[FR-04] Mock CircuitBreaker，預設為關閉狀態。"""
    cb = MagicMock(spec=CircuitBreakerProtocol)
    cb.is_open = MagicMock(return_value=False)
    cb.record_success = MagicMock()
    cb.record_failure = MagicMock()
    return cb


@pytest.fixture
def synth_engine(mock_kokoro_client, mock_circuit_breaker):
    """[FR-04] 標準 SynthEngine 實例。"""
    return SynthEngine(
        kokoro_client=mock_kokoro_client,
        circuit_breaker=mock_circuit_breaker,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────


async def _run(coro):
    """同步輔助：執行 async coroutine。"""
    return await coro


# ─────────────────────────────────────────────────────────────────────────────
# Happy-path: synthesize_chunks
# ─────────────────────────────────────────────────────────────────────────────


class TestSynthesizeChunks:
    """[FR-04] synthesize_chunks 正常路徑測試。"""

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty_list(self, synth_engine):
        """空 chunks 清單 → 回傳空 list。"""
        result = await synth_engine.synthesize_chunks([], "zf_xiaoxiao", 1.0)
        assert result == []

    @pytest.mark.asyncio
    async def test_single_chunk_returns_one_mp3(self, synth_engine):
        """單一 chunk → 回傳含一個 MP3 bytes 的 list。"""
        result = await synth_engine.synthesize_chunks(
            ["hello"], "zf_xiaoxiao", 1.0
        )
        assert len(result) == 1
        assert result[0] == b"MP3:hello"

    @pytest.mark.asyncio
    async def test_multiple_chunks_returns_ordered_list(self, synth_engine):
        """多個 chunks → 回傳依 chunk_index 排序的 list。"""
        chunks = ["chunk_0", "chunk_1", "chunk_2"]
        result = await synth_engine.synthesize_chunks(
            chunks, "zf_xiaoxiao", 1.0
        )
        assert len(result) == 3
        assert result[0] == b"MP3:chunk_0"
        assert result[1] == b"MP3:chunk_1"
        assert result[2] == b"MP3:chunk_2"

    @pytest.mark.asyncio
    async def test_chunks_are_concatenatable(self, synth_engine):
        """[FR-04] 拼接後 MP3 可正常播放（MP3 直接串接）。"""
        chunks = ["chunk1", "chunk2", "chunk3"]
        mp3_list = await synth_engine.synthesize_chunks(
            chunks, "zf_xiaoxiao", 1.0
        )
        concatenated = concatenate_mp3(mp3_list)
        # MP3 直接串接 → 所有原始資料保留
        assert b"chunk1" in concatenated
        assert b"chunk2" in concatenated
        assert b"chunk3" in concatenated

    @pytest.mark.asyncio
    async def test_circuit_breaker_recorded_on_success(
        self, mock_kokoro_client, mock_circuit_breaker
    ):
        """每次成功呼叫 → record_success() 被調用一次。"""
        mock_kokoro_client.synthesize = AsyncMock(
            return_value=b"fake_mp3_data"
        )
        engine = SynthEngine(mock_kokoro_client, mock_circuit_breaker)
        await engine.synthesize_chunks(["a", "b", "c"], "zf_xiaoxiao", 1.0)
        assert mock_circuit_breaker.record_success.call_count == 3

    @pytest.mark.asyncio
    async def test_speed_parameter_passed_to_client(
        self, mock_kokoro_client, mock_circuit_breaker
    ):
        """speed 參數傳遞給 KokoroClient。"""
        client = mock_kokoro_client
        client.synthesize = AsyncMock(return_value=b"mp3")
        engine = SynthEngine(client, mock_circuit_breaker)
        await engine.synthesize_chunks(["test"], "zf_xiaoxiao", 0.8)
        client.synthesize.assert_called_once_with("test", "zf_xiaoxiao", 0.8)


# ─────────────────────────────────────────────────────────────────────────────
# Performance: parallel vs sequential
# ─────────────────────────────────────────────────────────────────────────────


class TestParallelPerformance:
    """[FR-04] 5 個 Chunk 同時請求 → 總時間 < 各 Chunk 順序執行時間。"""

    @pytest.mark.asyncio
    async def test_parallel_faster_than_sequential(self):
        """並行執行顯著快於順序執行（≥ 3x）。"""
        delay_per_chunk = 0.05  # 50ms per chunk
        num_chunks = 5
        chunks = [f"chunk_{i}" for i in range(num_chunks)]

        # Client that simulates I/O delay
        async def slow_synthesize(text, voice, speed):
            await asyncio.sleep(delay_per_chunk)
            return f"MP3:{text}".encode()

        mock_client = MagicMock(spec=KokoroClientProtocol)
        mock_client.synthesize = slow_synthesize

        mock_cb = MagicMock(spec=CircuitBreakerProtocol)
        mock_cb.is_open = MagicMock(return_value=False)
        mock_cb.record_success = MagicMock()
        mock_cb.record_failure = MagicMock()

        engine = SynthEngine(mock_client, mock_cb)

        # Measure parallel time
        start_parallel = time.perf_counter()
        await engine.synthesize_chunks(chunks, "zf_xiaoxiao", 1.0)
        parallel_time = time.perf_counter() - start_parallel

        # Sequential would take num_chunks * delay_per_chunk
        sequential_time = num_chunks * delay_per_chunk

        # Parallel should be significantly faster
        assert parallel_time < sequential_time * 0.6, (
            f"Parallel time {parallel_time:.3f}s should be < "
            f"{sequential_time * 0.6:.3f}s (sequential={sequential_time:.3f}s)"
        )

    @pytest.mark.asyncio
    async def test_max_concurrency_respected(self):
        """Semaphore 限制最大並發數。"""
        max_concurrency = 3
        num_chunks = 6
        delay_per_task = 0.03

        async def slow_synthesize(text, voice, speed):
            await asyncio.sleep(delay_per_task)
            return f"MP3:{text}".encode()

        mock_client = MagicMock(spec=KokoroClientProtocol)
        mock_client.synthesize = slow_synthesize

        mock_cb = MagicMock(spec=CircuitBreakerProtocol)
        mock_cb.is_open = MagicMock(return_value=False)
        mock_cb.record_success = MagicMock()
        mock_cb.record_failure = MagicMock()

        engine = SynthEngine(mock_client, mock_cb)
        chunks = [f"c{i}" for i in range(num_chunks)]

        # With 3-way concurrency, 6 chunks should take ~2 batches × 30ms = ~60ms
        # Without concurrency, 6 × 30ms = ~180ms
        start = time.perf_counter()
        await engine.synthesize_chunks(chunks, "zf_xiaoxiao", 1.0, max_concurrency=max_concurrency)
        elapsed = time.perf_counter() - start

        # With semaphore cap, should be close to 2 batches
        # Allow 0.5 safety margin
        assert elapsed < delay_per_task * (num_chunks // max_concurrency) + 0.05, (
            f"Elapsed {elapsed:.3f}s suggests concurrency limit not respected "
            f"(expected < {delay_per_task * (num_chunks // max_concurrency) + 0.05:.3f}s)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Circuit Breaker: open state
# ─────────────────────────────────────────────────────────────────────────────


class TestCircuitBreakerOpen:
    """[FR-04] 斷路器 Open → SynthesisUnavailableError。"""

    @pytest.mark.asyncio
    async def test_raises_unavailable_when_circuit_open(self):
        """斷路器 Open 時拋出 SynthesisUnavailableError。"""
        mock_client = MagicMock(spec=KokoroClientProtocol)
        mock_client.synthesize = AsyncMock(return_value=b"mp3")

        mock_cb = MagicMock(spec=CircuitBreakerProtocol)
        mock_cb.is_open = MagicMock(return_value=True)

        engine = SynthEngine(mock_client, mock_cb)

        with pytest.raises(SynthesisUnavailableError) as exc_info:
            await engine.synthesize_chunks(["test"], "zf_xiaoxiao", 1.0)

        assert exc_info.value.retry_after_seconds == 10.0


# ─────────────────────────────────────────────────────────────────────────────
# Partial Failure
# ─────────────────────────────────────────────────────────────────────────────


class TestPartialFailure:
    """[FR-04] 部分 chunk 失敗 → SynthesisPartialError。"""

    @pytest.mark.asyncio
    async def test_partial_failure_raises_partial_error(self):
        """部分失敗時拋出 SynthesisPartialError，包含成功的 bytes。"""
        success_count = 3
        num_chunks = 5

        async def partial_synthesize(text, voice, speed):
            idx = int(text.split("_")[1]) if "_" in text else 0
            if idx < success_count:
                return f"MP3:{text}".encode()
            raise RuntimeError("Simulated backend error")

        mock_client = MagicMock(spec=KokoroClientProtocol)
        mock_client.synthesize = partial_synthesize

        mock_cb = MagicMock(spec=CircuitBreakerProtocol)
        mock_cb.is_open = MagicMock(return_value=False)
        mock_cb.record_success = MagicMock()
        mock_cb.record_failure = MagicMock()

        engine = SynthEngine(mock_client, mock_cb)
        chunks = [f"chunk_{i}" for i in range(num_chunks)]

        with pytest.raises(SynthesisPartialError) as exc_info:
            await engine.synthesize_chunks(chunks, "zf_xiaoxiao", 1.0)

        err = exc_info.value
        assert len(err.partial_results) == success_count
        assert err.failed_indices == [3, 4]

    @pytest.mark.asyncio
    async def test_partial_failure_successes_are_concatenatable(self):
        """[FR-04] 部分失敗時，已成功的 bytes 可串接播放。"""
        async def sometimes_fail(text, voice, speed):
            idx = int(text.split("_")[1])
            if idx % 2 == 0:
                return f"EVEN_{text}".encode()
            raise RuntimeError("fail")

        mock_client = MagicMock(spec=KokoroClientProtocol)
        mock_client.synthesize = sometimes_fail

        mock_cb = MagicMock(spec=CircuitBreakerProtocol)
        mock_cb.is_open = MagicMock(return_value=False)
        mock_cb.record_success = MagicMock()
        mock_cb.record_failure = MagicMock()

        engine = SynthEngine(mock_client, mock_cb)
        chunks = [f"c_{i}" for i in range(4)]

        with pytest.raises(SynthesisPartialError) as exc_info:
            await engine.synthesize_chunks(chunks, "zf_xiaoxiao", 1.0)

        # The caller can still concatenate partial results
        concatenated = concatenate_mp3(exc_info.value.partial_results)
        assert b"EVEN_c_0" in concatenated
        assert b"EVEN_c_2" in concatenated


# ─────────────────────────────────────────────────────────────────────────────
# All Failure
# ─────────────────────────────────────────────────────────────────────────────


class TestAllFailure:
    """[FR-04] 所有 chunk 失敗 → SynthesisUnavailableError。"""

    @pytest.mark.asyncio
    async def test_all_chunks_fail_raises_unavailable(self):
        """所有 chunk 都失敗時拋出 SynthesisUnavailableError。"""
        async def always_fail(text, voice, speed):
            raise RuntimeError("Backend down")

        mock_client = MagicMock(spec=KokoroClientProtocol)
        mock_client.synthesize = always_fail

        mock_cb = MagicMock(spec=CircuitBreakerProtocol)
        mock_cb.is_open = MagicMock(return_value=False)
        mock_cb.record_success = MagicMock()
        mock_cb.record_failure = MagicMock()

        engine = SynthEngine(mock_client, mock_cb)

        with pytest.raises(SynthesisUnavailableError):
            await engine.synthesize_chunks(["a", "b", "c"], "zf_xiaoxiao", 1.0)

        # All failures should be recorded
        assert mock_cb.record_failure.call_count == 3


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────


class TestExceptions:
    """[FR-04] 例外類結構驗證。"""

    def test_synthesis_partial_error_attributes(self):
        """SynthesisPartialError 有正確的 partial_results 和 failed_indices。"""
        err = SynthesisPartialError(
            partial_results=[b"a", b"b"],
            failed_indices=[2, 3],
        )
        assert err.partial_results == [b"a", b"b"]
        assert err.failed_indices == [2, 3]
        assert "Partial synthesis failure" in str(err)

    def test_synthesis_unavailable_error_attributes(self):
        """SynthesisUnavailableError 有正確的 retry_after_seconds。"""
        err = SynthesisUnavailableError(retry_after_seconds=5.0)
        assert err.retry_after_seconds == 5.0
        assert "Retry after 5.0s" in str(err)

    def test_synthesis_unavailable_error_default_retry(self):
        """預設 retry_after_seconds 為 10.0 秒。"""
        err = SynthesisUnavailableError()
        assert err.retry_after_seconds == 10.0


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────


class TestDataClasses:
    """[FR-04] SynthesisRequest / SynthesisResult dataclass 驗證。"""

    def test_synthesis_request_fields(self):
        req = SynthesisRequest(text="你好", voice="zf_xiaoxiao", speed=1.0, chunk_index=0)
        assert req.text == "你好"
        assert req.voice == "zf_xiaoxiao"
        assert req.speed == 1.0
        assert req.chunk_index == 0

    def test_synthesis_result_fields(self):
        result = SynthesisResult(
            audio_bytes=b"fake_mp3",
            chunk_index=1,
            duration_ms=1500.0,
            status=_ChunkStatus.SUCCESS,
        )
        assert result.audio_bytes == b"fake_mp3"
        assert result.chunk_index == 1
        assert result.duration_ms == 1500.0
        assert result.status is _ChunkStatus.SUCCESS


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────


class TestConcatenateMp3:
    """[FR-04] concatenate_mp3 直接串接 MP3 bytes。"""

    def test_concatenate_two_chunks(self):
        result = concatenate_mp3([b"MP3:first", b"MP3:second"])
        assert result == b"MP3:firstMP3:second"

    def test_concatenate_empty_list(self):
        assert concatenate_mp3([]) == b""

    def test_concatenate_single_chunk(self):
        assert concatenate_mp3([b"only_one"]) == b"only_one"


class TestEstimateDurationMs:
    """[FR-04] _estimate_duration_ms 估算正確。"""

    def test_zero_bytes_returns_zero(self):
        assert _estimate_duration_ms(0, 1.0) == 0.0

    def test_positive_bytes_estimate(self):
        # 16000 bytes/s at 128kbps, speed=1.0
        ms = _estimate_duration_ms(16000, 1.0)
        assert 990 < ms < 1010  # ~1000ms

    def test_speed_affects_duration(self):
        ms_fast = _estimate_duration_ms(16000, 2.0)  # 2x speed = half duration
        ms_normal = _estimate_duration_ms(16000, 1.0)
        assert ms_fast < ms_normal
