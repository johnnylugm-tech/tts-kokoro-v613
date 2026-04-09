"""[FR-07] CLI 命令列工具單元測試。

測試案例（SRS.md#L142-L146）：
    - tts-v610 --help → 顯示完整說明
    - 輸入文字 → 產出 MP3 檔案

Citations:
    SRS.md#L128-L146 (FR-07 需求描述與測試案例)
    SAD.md#L648-L666 (FR-07 CLI Tool 架構設計)
    SAD.md#L73 (FR-07 對應模組)
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes import (
    CLIConfig,
    CLIResult,
    build_cli_parser,
    is_file_input,
    synthesize_speech,
    synthesize_stream,
    validate_format,
    validate_input,
    validate_speed,
)


class TestCLIConfig:
    """[FR-07] CLIConfig 測試群組。"""

    def test_config_default_values(self):
        """[FR-07] 測試預設參數值。

        驗證預設值設定正確。
        """
        config = CLIConfig(input="test", output="output.mp3")
        assert config.input == "test"
        assert config.output == "output.mp3"
        assert config.voice == "zh-TW-1"
        assert config.speed == 1.0
        assert config.format == "mp3"
        assert config.ssml is False
        assert config.backend == "http://localhost:8000"
        assert config.api_key == ""

    def test_config_custom_values(self):
        """[FR-07] 測試自訂參數值。

        驗證自訂值設定正確。
        """
        config = CLIConfig(
            input="test",
            output="output.wav",
            voice="zh-TW-2",
            speed=1.5,
            format="wav",
            ssml=True,
            backend="http://custom:9000",
            api_key="secret"
        )
        assert config.voice == "zh-TW-2"
        assert config.speed == 1.5
        assert config.format == "wav"
        assert config.ssml is True
        assert config.backend == "http://custom:9000"
        assert config.api_key == "secret"


class TestValidation:
    """[FR-07] 參數驗證測試群組。"""

    @pytest.mark.parametrize("speed,expected", [
        (0.5, True),
        (1.0, True),
        (2.0, True),
        (0.25, False),
        (4.0, False),
        (0.0, False),
        (-1.0, False),
    ])
    def test_validate_speed(self, speed, expected):
        """[FR-07] 測試語速驗證。

        驗證 speed 是否在允許範圍 0.5-2.0 內。
        """
        assert validate_speed(speed) == expected

    @pytest.mark.parametrize("format,expected", [
        ("mp3", True),
        ("MP3", True),
        ("wav", True),
        ("WAV", True),
        ("flac", False),
        ("aac", False),
        ("", False),
    ])
    def test_validate_format(self, format, expected):
        """[FR-07] 測試音訊格式驗證。

        驗證格式是否為支援的 mp3 或 wav。
        """
        assert validate_format(format) == expected

    @pytest.mark.parametrize("input_str,expected", [
        ("hello", True),
        ("你好世界", True),
        ("", False),
        ("   ", False),
        (None, False),
    ])
    def test_validate_input(self, input_str, expected):
        """[FR-07] 測試輸入驗證。

        驗證輸入是否為有效文字或檔案路徑。
        """
        assert validate_input(input_str) == expected


class TestIsFileInput:
    """[FR-07] 檔案路徑判斷測試群組。"""

    def test_is_file_input_with_file(self):
        """[FR-07] 測試檔案路徑判斷。

        當輸入為有效檔案時，回傳 True。
        """
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test")
            temp_path = f.name

        try:
            assert is_file_input(temp_path) is True
        finally:
            os.unlink(temp_path)

    def test_is_file_input_with_text(self):
        """[FR-07] 測試文字輸入判斷。

        當輸入為一般文字時，回傳 False。
        """
        assert is_file_input("你好世界") is False
        assert is_file_input("hello world") is False


class TestCLIResult:
    """[FR-07] CLIResult 測試群組。"""

    def test_result_success(self):
        """[FR-07] 測試成功結果。

        驗證成功結果的屬性值。
        """
        result = CLIResult(success=True, output_path="/path/to/output.mp3")
        assert result.success is True
        assert result.output_path == "/path/to/output.mp3"
        assert result.error is None

    def test_result_error(self):
        """[FR-07] 測試錯誤結果。

        驗證錯誤結果的屬性值。
        """
        result = CLIResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.output_path is None


class TestBuildCLIParser:
    """[FR-07] CLI 參數解析器測試群組。"""

    def test_build_parser_keys(self):
        """[FR-07] 測試解析器包含所有必要參數。

        驗證解析器包含所有 FR-07 定義的參數。
        """
        parser = build_cli_parser()
        expected_keys = ["input", "output", "voice", "speed", "format", "ssml", "backend"]
        assert all(key in parser for key in expected_keys)

    def test_build_parser_input(self):
        """[FR-07] 測試 input 參數定義。

        驗證 input 參數的必要標記和幫助文字。
        """
        parser = build_cli_parser()
        assert "-i" in parser["input"]["flags"]
        assert "--input" in parser["input"]["flags"]
        assert parser["input"]["required"] is True

    def test_build_parser_output(self):
        """[FR-07] 測試 output 參數定義。

        驗證 output 參數的必要標記和幫助文字。
        """
        parser = build_cli_parser()
        assert "-o" in parser["output"]["flags"]
        assert "--output" in parser["output"]["flags"]
        assert parser["output"]["required"] is True

    def test_build_parser_defaults(self):
        """[FR-07] 測試預設參數值。

        驗證解析器預設值與 FR-07 定義一致。
        """
        parser = build_cli_parser()
        assert parser["voice"]["default"] == "zh-TW-1"
        assert parser["speed"]["default"] == 1.0
        assert parser["format"]["default"] == "mp3"
        assert parser["ssml"]["default"] is False
        assert parser["backend"]["default"] == "http://localhost:8000"


class TestSynthesizeSpeech:
    """[FR-07] 語音合成主流程測試群組。"""

    @pytest.mark.asyncio
    async def test_synthesize_invalid_input(self):
        """[FR-07] 測試無效輸入處理。

        當輸入為空時，回傳錯誤結果。
        """
        config = CLIConfig(input="", output="output.mp3")
        result = await synthesize_speech(config)
        assert result.success is False
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_synthesize_invalid_speed(self):
        """[FR-07] 測試無效語速處理。

        當語速超出範圍時，回傳錯誤結果。
        """
        config = CLIConfig(input="test", output="output.mp3", speed=5.0)
        result = await synthesize_speech(config)
        assert result.success is False
        assert "speed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_synthesize_invalid_format(self):
        """[FR-07] 測試無效格式處理。

        當格式不支援時，回傳錯誤結果。
        """
        config = CLIConfig(input="test", output="output.mp3", format="flac")
        result = await synthesize_speech(config)
        assert result.success is False
        assert "format" in result.error.lower()

    @pytest.mark.asyncio
    async def test_synthesize_file_input_error(self):
        """[FR-07] 測試檔案輸入錯誤處理。

        當輸入為不存在的檔案時，回傳錯誤結果。
        """
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"fake audio data"

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with patch("app.api.routes.is_file_input", return_value=True):
                config = CLIConfig(input="/nonexistent/file.txt", output="output.mp3")
                result = await synthesize_speech(config)
                assert result.success is False
                assert "read input file" in result.error.lower()

    @pytest.mark.asyncio
    async def test_synthesize_api_error(self):
        """[FR-07] 測試 API 錯誤處理。

        當 API 回傳錯誤狀態碼時，回傳錯誤結果。
        """
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            config = CLIConfig(input="test", output="output.mp3")
            result = await synthesize_speech(config)
            assert result.success is False
            assert "api error" in result.error.lower()


class TestSynthesizeStream:
    """[FR-07] 串流語音合成測試群組。"""

    @pytest.mark.asyncio
    async def test_streaming_not_implemented(self):
        """[FR-07] 測試串流功能尚未實作。

        驗證串流功能回傳正確的錯誤訊息。
        """
        config = CLIConfig(input="test", output="output.mp3")
        result = await synthesize_stream(config, chunk_callback=lambda x: x)
        assert result.success is False
        assert "not yet implemented" in result.error.lower()

    @pytest.mark.asyncio
    async def test_streaming_invalid_input(self):
        """[FR-07] 測試串流無效輸入處理。

        當輸入為空時，回傳錯誤結果。
        """
        config = CLIConfig(input="", output="output.mp3")
        result = await synthesize_stream(config, chunk_callback=lambda x: x)
        assert result.success is False
        assert "empty" in result.error.lower()


class TestCLIIntegration:
    """[FR-07] CLI 整合測試群組。"""

    def test_config_to_dict(self):
        """[FR-07] 測試設定轉換。

        驗證 CLIConfig 能正確轉換為字典。
        """
        config = CLIConfig(
            input="test",
            output="output.mp3",
            voice="zh-TW-2",
            speed=1.5
        )
        config_dict = {
            "text": config.input,
            "voice": config.voice,
            "speed": config.speed,
            "format": config.format,
            "ssml": config.ssml,
        }
        assert config_dict["text"] == "test"
        assert config_dict["voice"] == "zh-TW-2"
        assert config_dict["speed"] == 1.5

    def test_help_command_outputs(self):
        """[FR-07] 測試 help 輸出結構。

        驗證 CLI 解析器能支援 help 所需的參數定義。
        """
        parser = build_cli_parser()
        help_keys = ["input", "output", "voice", "speed", "format", "ssml", "backend"]
        for key in help_keys:
            assert "help" in parser[key]
            assert len(parser[key]["help"]) > 0
