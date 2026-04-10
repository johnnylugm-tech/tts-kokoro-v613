"""
[FR-09] Kokoro TTS API 代理客戶端 (Kokoro Proxy).

封裝 HTTP 呼叫、處理音色選擇、控制速度參數。
Lazy Init + 雙重檢查鎖定，非執行緒安全（asyncio 情境下安全）。

端點對應：
- POST /v1/audio/speech → synthesize()
- GET  /v1/audio/voices → list_voices()
- GET  /health           → health_check()

錯誤分類（L4）：
- KokoroConnectionError  (OSError)：網路中斷、無法連線
- KokoroAPIError          (RuntimeError)：API 層級錯誤（父類）
  - KokoroClientError     (ClientSideError sub)：4xx 不計入 CB
  - KokoroServerError     (5xx 計入 CB)
- KokoroTimeoutError      (TimeoutError)：請求逾時

測試案例（SRS.md#L178-L179）：
- speech("你好", "zf_xiaoxiao", 1.0) → 回傳 MP3 bytes
- voices() → 回傳可用音色列表

Citations:
    SRS.md#L166-L179 (FR-09 需求描述與測試案例)
    SAD.md#L421-L463 (FR-09 Kokoro Client 架構設計)
    SAD.md#L75 (FR-09 模組對映)
"""

from __future__ import annotations

import asyncio

import httpx
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class KokoroAPIError(RuntimeError):
    """[FR-09] L4：Kokoro API 層級錯誤（父類）。

    Citations:
        SRS.md#L166-L179
        SAD.md#L421-L463
    """

    def __init__(self, status_code: int, detail: str) -> None:
        """Citations: SRS.md#L166-L179, SAD.md#L421-L463"""
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"KokoroAPIError {status_code}: {detail}")


class KokoroConnectionError(OSError):
    """[FR-09] L4：網路中斷、無法連線至 Kokoro 後端。

    Citations:
        SRS.md#L166-L179
        SAD.md#L421-L463
    """


class KokoroTimeoutError(TimeoutError):
    """[FR-09] L4：請求逾時。

    Citations:
        SRS.md#L166-L179
        SAD.md#L421-L463
    """


class KokoroClientError(KokoroAPIError):
    """[FR-09] L4 sub：客戶端錯誤（4xx），不計入 CB。

    Citations:
        SRS.md#L166-L179
        SAD.md#L421-L463
    """


class KokoroServerError(KokoroAPIError):
    """[FR-09] L4 sub：伺服器錯誤（5xx），計入 CB。

    Citations:
        SRS.md#L166-L179
        SAD.md#L421-L463
    """


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class KokoroConfig(BaseModel):
    """[FR-09] Kokoro 後端連線設定。

    Citations:
        SRS.md#L166-L179
        SAD.md#L595-L610
    """

    base_url: str = Field(default="http://localhost:8880")
    """Kokoro Docker HTTP 端點。"""

    read_timeout: float = Field(default=30.0)
    """單次請求讀取逾時（秒）。"""

    max_connections: int = Field(default=20)
    """最大並發連線數。"""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class KokoroClient:
    """[FR-09] Kokoro TTS API 代理客戶端。Lazy Init + 雙重檢查鎖定。

    Citations:
        SRS.md#L166-L179
        SAD.md#L421-L463
    """

    def __init__(self, config: KokoroConfig | None = None) -> None:
        self._config = config or KokoroConfig()
        self._client: httpx.AsyncClient | None = None
        self._init_lock = asyncio.Lock()  # Double-check locking for async

    async def _get_client(self) -> httpx.AsyncClient:
        """[FR-09] Lazy Init + 雙重檢查鎖定，取得 httpx.AsyncClient 實例。

        Citations:
            SRS.md#L166-L179
            SAD.md#L433-L442
        """
        if self._client is None:
            async with self._init_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        base_url=self._config.base_url,
                        timeout=httpx.Timeout(
                            connect=5.0,
                            read=self._config.read_timeout,
                            write=10.0,
                            pool=5.0,
                        ),
                        limits=httpx.Limits(
                            max_connections=self._config.max_connections,
                            max_keepalive_connections=10,
                        ),
                    )
        return self._client

    async def synthesize(
        self, text: str, voice: str, speed: float
    ) -> bytes:
        """[FR-09] POST 到 Kokoro /v1/audio/speech，回傳 MP3 位元組。

        Args:
            text: 待合成文字。
            voice: 音色名稱（如 zf_xiaoxiao）。
            speed: 語速倍率（0.5 ~ 2.0）。

        Returns:
            bytes: MP3 音訊資料。

        Raises:
            KokoroConnectionError: 網路中斷、無法連線。
            KokoroClientError: 4xx 客戶端錯誤。
            KokoroServerError: 5xx 伺服器錯誤。
            KokoroTimeoutError: 請求逾時。

        Citations:
            SRS.md#L178 (speech("你好", "zf_xiaoxiao", 1.0) → MP3 bytes)
            SRS.md#L166-L179
            SAD.md#L448-L455
        """
        client = await self._get_client()
        payload = {
            "model": "kokoro",
            "input": text,
            "voice": voice,
            "speed": speed,
        }
        try:
            response = await client.post(
                "/v1/audio/speech",
                json=payload,
                headers={"Accept": "audio/mp3"},
            )
        except httpx.ConnectError as e:
            raise KokoroConnectionError(
                f"Failed to connect to Kokoro backend: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise KokoroTimeoutError(
                f"Kokoro request timed out: {e}"
            ) from e

        if 200 <= response.status_code < 300:
            return response.content

        if 400 <= response.status_code < 500:
            raise KokoroClientError(
                status_code=response.status_code,
                detail=response.text,
            )
        # 5xx
        raise KokoroServerError(
            status_code=response.status_code,
            detail=response.text,
        )

    async def list_voices(self) -> list[dict]:
        """[FR-09] GET /v1/audio/voices，回傳可用音色列表。

        Returns:
            list[dict]: 音色清單，每項包含 name、lang、gender 等欄位。

        Raises:
            KokoroConnectionError: 網路中斷。
            KokoroServerError: 5xx 錯誤。
            KokoroTimeoutError: 逾時。

        Citations:
            SRS.md#L179 (voices() → 可用音色列表)
            SRS.md#L166-L179
            SAD.md#L456
        """
        client = await self._get_client()
        try:
            response = await client.get("/v1/audio/voices")
        except httpx.ConnectError as e:
            raise KokoroConnectionError(
                f"Failed to connect to Kokoro backend: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise KokoroTimeoutError(
                f"Kokoro request timed out: {e}"
            ) from e

        if response.status_code >= 500:
            raise KokoroServerError(
                status_code=response.status_code,
                detail=response.text,
            )
        # 2xx / 4xx — 4xx 不拋例外，回傳空或錯誤語音列表
        return response.json()

    async def health_check(self) -> bool:
        """[FR-09] 健康檢查，嘗試連線到 /health 端點。

        Returns:
            bool: 後端可達返回 True，否則 False。

        Citations:
            SRS.md#L166-L179
            SAD.md#L456
        """
        client = await self._get_client()
        try:
            response = await client.get("/health", timeout=5.0)
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def close(self) -> None:
        """[FR-09] 關閉 HTTP 客戶端，釋放連線池。

        Citations:
            SRS.md#L166-L179
            SAD.md#L421-L463
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None
