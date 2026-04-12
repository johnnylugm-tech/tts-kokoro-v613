"""[FR-07] CLI 命令列工具核心路由。

提供命令列工具支援快速語音合成的核心邏輯。

使用範例（SRS.md#L130-L135）：
    tts-v610 "你好世界" -o output.mp3
    tts-v610 --ssml "<speak>...</speak>" -o out.mp3
    tts-v610 --file input.txt -o output/

支援參數：
    -i, --input：輸入文字或檔案
    -o, --output：輸出檔案
    -v, --voice：音色或混合配方
    -s, --speed：語速 0.5-2.0
    -f, --format：mp3/wav
    --ssml：SSML 模式
    --backend：後端 URL

Citations:
    SRS.md#L128-L146 (FR-07 需求描述與測試案例)
    SAD.md#L648-L666 (FR-07 CLI Tool 架構設計)
    SAD.md#L73 (FR-07 對應模組)
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

import httpx


@dataclass
class CLIConfig:
    """[FR-07] CLI 設定組態。

    儲存命令列工具的所有配置參數。

    Attributes:
        input: 輸入文字或檔案路徑
        output: 輸出檔案路徑
        voice: 音色或混合配方
        speed: 語速 (0.5-2.0)
        format: 音訊格式 (mp3/wav)
        ssml: 是否使用 SSML 模式
        backend: 後端 URL
        api_key: API 金鑰

    Citations:
        SRS.md#L128-L146 (FR-07 需求描述)
        SAD.md#L648-L666 (架構設計)
        SAD.md#L73 (對應模組)
    """
    input: str
    output: str
    voice: str = "zh-TW-1"
    speed: float = 1.0
    format: str = "mp3"
    ssml: bool = False
    backend: str = "http://localhost:8000"
    api_key: str = ""


@dataclass
class CLIResult:
    """[FR-07] CLI 執行結果。

    Attributes:
        success: 是否成功
        output_path: 輸出檔案路徑
        error: 錯誤訊息（若有）

    Citations:
        SRS.md#L128-L146 (FR-07 需求描述)
        SAD.md#L648-L666 (架構設計)
        SAD.md#L73 (對應模組)
    """
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None


def validate_speed(speed: float) -> bool:
    """[FR-07] 驗證語速範圍。

    驗證 speed 是否在允許範圍 0.5-2.0 內。

    Args:
        speed: 語速值

    Returns:
        True 若在範圍內，否則 False

    Citations:
        SRS.md#L136-L140 (speed 參數定義)
        SAD.md#L648-L666 (CLI 架構)
        SAD.md#L73 (對應模組)
    """
    return 0.5 <= speed <= 2.0


def validate_format(format: str) -> bool:
    """[FR-07] 驗證音訊格式。

    驗證格式是否為支援的 mp3 或 wav。

    Args:
        format: 音訊格式

    Returns:
        True 若格式支援，否則 False

    Citations:
        SRS.md#L136-L140 (format 參數定義)
        SAD.md#L648-L666 (CLI 架構)
        SAD.md#L73 (對應模組)
    """
    return format.lower() in ("mp3", "wav")


def validate_input(input_str: str) -> bool:
    """[FR-07] 驗證輸入參數。

    驗證輸入是否為有效文字或檔案路徑。

    Args:
        input_str: 輸入文字或檔案路徑

    Returns:
        True 若有效，否則 False

    Citations:
        SRS.md#L130-L135 (使用範例)
        SRS.md#L136-L140 (input 參數定義)
        SAD.md#L648-L666 (CLI 架構)
    """
    if not input_str or not input_str.strip():
        return False
    return True


def is_file_input(input_str: str) -> bool:
    """[FR-07] 判斷輸入是否為檔案路徑。

    Args:
        input_str: 輸入字串

    Returns:
        True 若為檔案路徑，否則為文字輸入

    Citations:
        SRS.md#L130-L135 (檔案輸入範例)
        SRS.md#L136-L140 (input 參數定義)
        SAD.md#L648-L666 (CLI 架構)
    """
    return os.path.isfile(input_str)


async def synthesize_speech(
    config: CLIConfig,
    timeout: float = 30.0
) -> CLIResult:
    """[FR-07] 執行語音合成。

    呼叫後端 API 執行語音合成並產出音訊檔案。

    Args:
        config: CLI 設定組態
        timeout: 請求逾時時間（秒）

    Returns:
        CLIResult: 包含執行結果的資料類別

    Citations:
        SRS.md#L130 (使用範例)
        SRS.md#L136-L140 (支援參數)
    """
    try:
        if not validate_input(config.input):
            return CLIResult(success=False, error="Invalid input: empty or whitespace")

        if not validate_speed(config.speed):
            return CLIResult(success=False, error="Speed must be between 0.5 and 2.0")

        if not validate_format(config.format):
            return CLIResult(success=False, error="Format must be mp3 or wav")

        input_text = config.input
        if is_file_input(config.input):
            try:
                with open(config.input, "r", encoding="utf-8") as f:
                    input_text = f.read()
            except Exception as e:
                return CLIResult(success=False, error=f"Failed to read input file: {e}")

        headers = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            payload = {
                "text": input_text,
                "voice": config.voice,
                "speed": config.speed,
                "format": config.format,
                "ssml": config.ssml,
            }

            response = await client.post(
                f"{config.backend}/v1/synthesize",
                json=payload,
                headers=headers
            )

            if response.status_code != 200:
                return CLIResult(
                    success=False,
                    error=f"API error: {response.status_code}"
                )

            os.makedirs(os.path.dirname(config.output) or ".", exist_ok=True)
            with open(config.output, "wb") as f:
                f.write(response.content)

            return CLIResult(success=True, output_path=config.output)

    except httpx.TimeoutException:
        return CLIResult(success=False, error="Request timeout")
    except httpx.RequestError as e:
        return CLIResult(success=False, error=f"Request failed: {e}")
    except Exception as e:
        return CLIResult(success=False, error=f"Unexpected error: {e}")


async def synthesize_stream(
    config: CLIConfig,
    chunk_callback: Callable[..., Any],
    timeout: float = 30.0
) -> CLIResult:
    """[FR-07] 串流語音合成（未來擴充）。

    Args:
        config: CLI 設定組態
        chunk_callback: 區塊回調函數
        timeout: 請求逾時時間（秒）

    Returns:
        CLIResult: 包含執行結果的資料類別

    Citations:
        SRS.md#L128-L146 (FR-07 需求描述)
        SAD.md#L648-L666 (串流架構設計)
        SAD.md#L73 (對應模組)
    """
    try:
        if not validate_input(config.input):
            return CLIResult(success=False, error="Invalid input: empty or whitespace")

        return CLIResult(success=False, error="Streaming not yet implemented")

    except Exception as e:
        return CLIResult(success=False, error=f"Unexpected error: {e}")


def build_cli_parser() -> dict:
    """[FR-07] 建立 CLI 參數解析器。

    Returns:
        dict: 支援的 CLI 參數定義

    Citations:
        SRS.md#L128-L146 (FR-07 需求與參數)
        SAD.md#L648-L666 (CLI 架構設計)
        SAD.md#L73 (對應模組)
    """
    return {
        "input": {
            "flags": ["-i", "--input"],
            "required": True,
            "help": "輸入文字或檔案路徑"
        },
        "output": {
            "flags": ["-o", "--output"],
            "required": True,
            "help": "輸出檔案路徑"
        },
        "voice": {
            "flags": ["-v", "--voice"],
            "default": "zh-TW-1",
            "help": "音色或混合配方"
        },
        "speed": {
            "flags": ["-s", "--speed"],
            "default": 1.0,
            "help": "語速 (0.5-2.0)"
        },
        "format": {
            "flags": ["-f", "--format"],
            "default": "mp3",
            "help": "音訊格式 (mp3/wav)"
        },
        "ssml": {
            "flags": ["--ssml"],
            "default": False,
            "help": "啟用 SSML 模式"
        },
        "backend": {
            "flags": ["--backend", "-b"],
            "default": "http://localhost:8000",
            "help": "後端 URL"
        },
    }
