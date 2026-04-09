"""
[FR-09] KokoroClient 單元測試。

測試案例（SRS.md#L178-L179）：
    - speech("你好", "zf_xiaoxiao", 1.0) → 回傳 MP3 bytes
    - voices() → 回傳可用音色列表

Citations:
    SRS.md#L166-L179 (FR-09 需求描述與測試案例)
    SRS.md#L178 (speech("你好", "zf_xiaoxiao", 1.0) → MP3 bytes)
    SRS.md#L179 (voices() → 可用音色列表)
    SAD.md#L421-L463 (FR-09 Kokoro Client 架構設計)
    SAD.md#L75 (FR-09 模組對映)
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.kokoro_client import (
    KokoroClient,
    KokoroConfig,
    KokoroConnectionError,
    KokoroAPIError,
    KokoroClientError,
    KokoroServerError,
    KokoroTimeoutError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_httpx_async_client(mocker):
    """Mock httpx.AsyncClient 工廠 fixture。"""
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch(
        "app.backend.kokoro_client.httpx.AsyncClient",
        return_value=mock_client,
    )
    return mock_client


@pytest.fixture
def client(mock_httpx_async_client):
    """[FR-09] 建立 KokoroClient 實例（含 mock AsyncClient）。"""
    return KokoroClient(config=KokoroConfig(base_url="http://localhost:8880"))


@pytest.fixture
def client_config():
    """[FR-09] KokoroConfig 預設值驗證。"""
    return KokoroConfig()


# ---------------------------------------------------------------------------
# KokoroConfig
# ---------------------------------------------------------------------------

class TestKokoroConfig:
    """[FR-09] KokoroConfig 預設值與欄位驗證。"""

    def test_default_base_url(self, client_config: KokoroConfig) -> None:
        assert client_config.base_url == "http://localhost:8880"

    def test_default_read_timeout(self, client_config: KokoroConfig) -> None:
        assert client_config.read_timeout == 30.0

    def test_default_max_connections(self, client_config: KokoroConfig) -> None:
        assert client_config.max_connections == 20

    def test_custom_config(self) -> None:
        cfg = KokoroConfig(
            base_url="http://custom:9999",
            read_timeout=60.0,
            max_connections=50,
        )
        assert cfg.base_url == "http://custom:9999"
        assert cfg.read_timeout == 60.0
        assert cfg.max_connections == 50


# ---------------------------------------------------------------------------
# Exceptions hierarchy
# ---------------------------------------------------------------------------

class TestKokoroExceptions:
    """[FR-09] 例外類別繼承關係驗證。"""

    def test_kokoro_api_error_is_runtime_error(self) -> None:
        exc = KokoroAPIError(500, "server error")
        assert isinstance(exc, RuntimeError)

    def test_kokoro_connection_error_is_os_error(self) -> None:
        exc = KokoroConnectionError("connection failed")
        assert isinstance(exc, OSError)

    def test_kokoro_timeout_error_is_timeout_error(self) -> None:
        exc = KokoroTimeoutError("timed out")
        assert isinstance(exc, TimeoutError)

    def test_kokoro_client_error_is_api_error(self) -> None:
        exc = KokoroClientError(400, "bad request")
        assert isinstance(exc, KokoroAPIError)
        assert exc.status_code == 400
        assert exc.detail == "bad request"

    def test_kokoro_server_error_is_api_error(self) -> None:
        exc = KokoroServerError(500, "internal error")
        assert isinstance(exc, KokoroAPIError)
        assert exc.status_code == 500
        assert exc.detail == "internal error"


# ---------------------------------------------------------------------------
# synthesize()
# ---------------------------------------------------------------------------

class TestSynthesize:
    """[FR-09] synthesize() 方法測試。"""

    @pytest.mark.asyncio
    async def test_synthesize_returns_mp3_bytes(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 正常呼叫应返回 MP3 bytes（SRS.md#L178）。"""
        fake_mp3 = b"FAKE_MP3_DATA"
        mock_response = httpx.Response(
            200,
            content=fake_mp3,
            headers={"Content-Type": "audio/mp3"},
        )
        mock_httpx_async_client.post.return_value = mock_response

        result = await client.synthesize("你好", "zf_xiaoxiao", 1.0)

        assert result == fake_mp3
        mock_httpx_async_client.post.assert_called_once()
        call_kwargs = mock_httpx_async_client.post.call_args
        assert call_kwargs.kwargs["headers"]["Accept"] == "audio/mp3"
        payload = call_kwargs.kwargs["json"]
        assert payload["input"] == "你好"
        assert payload["voice"] == "zf_xiaoxiao"
        assert payload["speed"] == 1.0

    @pytest.mark.asyncio
    async def test_synthesize_raises_connection_error_on_connect_error(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 連線失敗拋出 KokoroConnectionError。"""
        mock_httpx_async_client.post.side_effect = httpx.ConnectError("refused")

        with pytest.raises(KokoroConnectionError):
            await client.synthesize("test", "zf_xiaoxiao", 1.0)

    @pytest.mark.asyncio
    async def test_synthesize_raises_timeout_error(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 逾時拋出 KokoroTimeoutError。"""
        mock_httpx_async_client.post.side_effect = httpx.TimeoutException("timeout")

        with pytest.raises(KokoroTimeoutError):
            await client.synthesize("test", "zf_xiaoxiao", 1.0)

    @pytest.mark.asyncio
    async def test_synthesize_raises_client_error_on_4xx(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 4xx 錯誤拋出 KokoroClientError（不計入 CB）。"""
        mock_response = httpx.Response(422, text="Unprocessable Entity")
        mock_httpx_async_client.post.return_value = mock_response

        with pytest.raises(KokoroClientError) as exc_info:
            await client.synthesize("test", "zf_xiaoxiao", 1.0)

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_synthesize_raises_server_error_on_5xx(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 5xx 錯誤拋出 KokoroServerError（計入 CB）。"""
        mock_response = httpx.Response(500, text="Internal Server Error")
        mock_httpx_async_client.post.return_value = mock_response

        with pytest.raises(KokoroServerError) as exc_info:
            await client.synthesize("test", "zf_xiaoxiao", 1.0)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_synthesize_with_custom_speed(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 自訂 speed 參數傳遞驗證。"""
        fake_mp3 = b"MP3"
        mock_response = httpx.Response(200, content=fake_mp3)
        mock_httpx_async_client.post.return_value = mock_response

        await client.synthesize("hello", "zf_xiaoxiao", 0.8)

        payload = mock_httpx_async_client.post.call_args.kwargs["json"]
        assert payload["speed"] == 0.8


# ---------------------------------------------------------------------------
# list_voices()
# ---------------------------------------------------------------------------

class TestListVoices:
    """[FR-09] list_voices() 方法測試。"""

    @pytest.mark.asyncio
    async def test_list_voices_returns_voice_list(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 正常呼叫返回音色列表（SRS.md#L179）。"""
        voice_data = [
            {"name": "zf_xiaoxiao", "lang": "zh-TW", "gender": "female"},
            {"name": "zf_aiyun", "lang": "zh-TW", "gender": "female"},
        ]
        mock_response = httpx.Response(200, json=voice_data)
        mock_httpx_async_client.get.return_value = mock_response

        result = await client.list_voices()

        assert result == voice_data
        mock_httpx_async_client.get.assert_called_once_with("/v1/audio/voices")

    @pytest.mark.asyncio
    async def test_list_voices_raises_connection_error(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 連線失敗拋出 KokoroConnectionError。"""
        mock_httpx_async_client.get.side_effect = httpx.ConnectError("refused")

        with pytest.raises(KokoroConnectionError):
            await client.list_voices()

    @pytest.mark.asyncio
    async def test_list_voices_raises_server_error_on_5xx(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 5xx 錯誤拋出 KokoroServerError。"""
        mock_response = httpx.Response(503, text="Service Unavailable")
        mock_httpx_async_client.get.return_value = mock_response

        with pytest.raises(KokoroServerError) as exc_info:
            await client.list_voices()

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_list_voices_returns_json_on_4xx(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 4xx 不拋例外，直接回傳 JSON（SAD.md#L456 備註）。"""
        error_json = [{"name": "error", "lang": "en", "gender": "unknown"}]
        mock_response = httpx.Response(404, json=error_json)
        mock_httpx_async_client.get.return_value = mock_response

        result = await client.list_voices()
        assert result == error_json


# ---------------------------------------------------------------------------
# health_check()
# ---------------------------------------------------------------------------

class TestHealthCheck:
    """[FR-09] health_check() 方法測試。"""

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] /health 返回 200 時回傳 True。"""
        mock_response = httpx.Response(200)
        mock_httpx_async_client.get.return_value = mock_response

        result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_non_200(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] /health 返回非 200 時回傳 False。"""
        mock_response = httpx.Response(503)
        mock_httpx_async_client.get.return_value = mock_response

        result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_connect_error(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 連線錯誤回傳 False（不拋例外）。"""
        mock_httpx_async_client.get.side_effect = httpx.ConnectError("refused")

        result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_timeout(
        self, client: KokoroClient, mock_httpx_async_client
    ) -> None:
        """[FR-09] 逾時回傳 False（不拋例外）。"""
        mock_httpx_async_client.get.side_effect = httpx.TimeoutException("timeout")

        result = await client.health_check()

        assert result is False


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------

class TestClose:
    """[FR-09] close() 方法測試。"""

    @pytest.mark.asyncio
    async def test_close_acloses_client(self, client: KokoroClient) -> None:
        """[FR-09] close() 應呼叫 aclose() 並清除實例。"""
        await client._get_client()  # Force init
        assert client._client is not None

        await client.close()

        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self, client: KokoroClient) -> None:
        """[FR-09] close() 多次呼叫不拋例外。"""
        await client.close()
        await client.close()  # Should not raise
