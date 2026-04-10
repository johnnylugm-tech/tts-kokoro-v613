"""
[FR-08] 測試案例：ffmpeg 音訊格式轉換（MP3 ↔ WAV）。

Citations:
    SRS.md#L154-L162 (FR-08 需求描述與測試案例)
    SAD.md#L557-L572 (AudioConverter 類別與錯誤定義)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.audio.audio_converter import (
    AudioConverter,
    AudioConverterError,
    AudioConverterNotFoundError,
    SUPPORTED_FORMATS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def converter() -> AudioConverter:
    """Create a fresh AudioConverter instance for each test."""
    return AudioConverter()


@pytest.fixture
def valid_mp3_data() -> bytes:
    """Minimal valid MP3 frame (ID3v2 + minimal frame — not decodable, just bytes)."""
    # ID3v2 header
    id3 = b"ID3" + b"\x04\x00\x00\x00\x00\x00\x00"
    # A minimal MP3 frame header (0xFF 0xFB = MPEG1 Layer3, 128kbps, 44.1kHz, stereo)
    frame = b"\xff\xfb\x90\x00" + b"\x00" * 200
    return id3 + frame


@pytest.fixture
def valid_wav_data() -> bytes:
    """Minimal valid WAV header + silent PCM data (44.1kHz, 16-bit, stereo)."""
    import struct as st

    sample_rate = 44100
    num_channels = 2
    bits_per_sample = 16
    num_samples = 100
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = num_samples * block_align

    header = st.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,           # Subchunk1Size
        1,            # AudioFormat (PCM)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    pcm = b"\x00" * data_size
    return header + pcm


# ---------------------------------------------------------------------------
# SUPPORTED_FORMATS
# ---------------------------------------------------------------------------

class TestSupportedFormats:
    def test_supported_formats_contains_mp3_and_wav(self) -> None:
        assert "mp3" in SUPPORTED_FORMATS
        assert "wav" in SUPPORTED_FORMATS

    def test_supported_formats_is_frozenset_or_set(self) -> None:
        assert isinstance(SUPPORTED_FORMATS, (set, frozenset))


# ---------------------------------------------------------------------------
# Error Classes
# ---------------------------------------------------------------------------

class TestErrorClasses:
    def test_not_found_error_is_subclass_of_converter_error(self) -> None:
        assert issubclass(AudioConverterNotFoundError, AudioConverterError)

    def test_not_found_error_is_runtime_error(self) -> None:
        assert issubclass(AudioConverterNotFoundError, RuntimeError)

    def test_converter_error_is_runtime_error(self) -> None:
        assert issubclass(AudioConverterError, RuntimeError)

    def test_not_found_error_message(self) -> None:
        err = AudioConverterNotFoundError("ffmpeg not found in PATH.")
        assert "ffmpeg" in str(err)


# ---------------------------------------------------------------------------
# Lazy Init — _get_ffmpeg
# ---------------------------------------------------------------------------

class TestGetFfmpeg:
    @pytest.mark.asyncio
    async def test_get_ffmpeg_returns_path_string(self, converter: AudioConverter) -> None:
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = await converter._get_ffmpeg()
            assert isinstance(result, str)
            assert "ffmpeg" in result

    @pytest.mark.asyncio
    async def test_get_ffmpeg_caches_after_first_call(self, converter: AudioConverter) -> None:
        with patch("shutil.which", return_value="/usr/bin/ffmpeg") as mock_which:
            await converter._get_ffmpeg()
            await converter._get_ffmpeg()
            await converter._get_ffmpeg()
            # Lock acquired once, check only one call
            assert mock_which.call_count == 1

    @pytest.mark.asyncio
    async def test_get_ffmpeg_raises_when_not_found(self, converter: AudioConverter) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(AudioConverterNotFoundError) as exc_info:
                await converter._get_ffmpeg()
            assert "ffmpeg" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# convert — Validation
# ---------------------------------------------------------------------------

class TestConvertValidation:
    @pytest.mark.asyncio
    async def test_raises_on_unsupported_source_format(
        self, converter: AudioConverter, valid_mp3_data: bytes
    ) -> None:
        with pytest.raises(ValueError) as exc_info:
            await converter.convert(valid_mp3_data, target_format="wav", source_format="flac")
        assert "Unsupported source format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_on_unsupported_target_format(
        self, converter: AudioConverter, valid_mp3_data: bytes
    ) -> None:
        with pytest.raises(ValueError) as exc_info:
            await converter.convert(valid_mp3_data, target_format="flac", source_format="mp3")
        assert "Unsupported target format" in str(exc_info.value)


# ---------------------------------------------------------------------------
# convert — Happy Path (MP3 → WAV)
# ---------------------------------------------------------------------------

class TestConvertMp3ToWav:
    @pytest.mark.asyncio
    async def test_mp3_to_wav_returns_bytes(
        self, converter: AudioConverter, valid_mp3_data: bytes
    ) -> None:
        expected_output = b"RIFFfake_wav_content"
        with patch.object(converter, "_get_ffmpeg", new=AsyncMock(return_value="/usr/bin/ffmpeg")):
            with patch("asyncio.create_subprocess_exec") as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.returncode = 0
                mock_proc.wait = AsyncMock()
                mock_subprocess.return_value = mock_proc

                with patch("app.audio.audio_converter.tempfile.NamedTemporaryFile") as mock_tmp:
                    mock_src = MagicMock()
                    mock_src.__enter__ = MagicMock(return_value=mock_src)
                    mock_src.__exit__ = MagicMock(return_value=False)
                    mock_src.name = "/tmp/src.mp3"

                    mock_dst = MagicMock()
                    mock_dst.__enter__ = MagicMock(return_value=mock_dst)
                    mock_dst.__exit__ = MagicMock(return_value=False)
                    mock_dst.name = "/tmp/dst.wav"

                    mock_tmp.side_effect = [mock_src, mock_dst]

                    with patch("app.audio.audio_converter.open", mock_open(read_data=expected_output)) as _mo:
                        with patch("app.audio.audio_converter.os.unlink"):
                            result = await converter.convert(
                                valid_mp3_data, target_format="wav", source_format="mp3"
                            )
                            assert isinstance(result, bytes)
                            assert result == expected_output


# ---------------------------------------------------------------------------
# convert — Happy Path (WAV → MP3)
# ---------------------------------------------------------------------------

class TestConvertWavToMp3:
    @pytest.mark.asyncio
    async def test_wav_to_mp3_returns_bytes(
        self, converter: AudioConverter, valid_wav_data: bytes
    ) -> None:
        expected_output = b"ID3fake_mp3_content"
        with patch.object(converter, "_get_ffmpeg", new=AsyncMock(return_value="/usr/bin/ffmpeg")):
            with patch("asyncio.create_subprocess_exec") as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.returncode = 0
                mock_proc.wait = AsyncMock()
                mock_subprocess.return_value = mock_proc

                with patch("app.audio.audio_converter.tempfile.NamedTemporaryFile") as mock_tmp:
                    mock_src = MagicMock()
                    mock_src.__enter__ = MagicMock(return_value=mock_src)
                    mock_src.__exit__ = MagicMock(return_value=False)
                    mock_src.name = "/tmp/src.wav"

                    mock_dst = MagicMock()
                    mock_dst.__enter__ = MagicMock(return_value=mock_dst)
                    mock_dst.__exit__ = MagicMock(return_value=False)
                    mock_dst.name = "/tmp/dst.mp3"

                    mock_tmp.side_effect = [mock_src, mock_dst]

                    with patch("app.audio.audio_converter.open", mock_open(read_data=expected_output)) as _mo:
                        with patch("app.audio.audio_converter.os.unlink"):
                            result = await converter.convert(
                                valid_wav_data, target_format="mp3", source_format="wav"
                            )
                            assert isinstance(result, bytes)
                            assert result == expected_output


# ---------------------------------------------------------------------------
# convert — Error Handling
# ---------------------------------------------------------------------------

class TestConvertErrorHandling:
    @pytest.mark.asyncio
    async def test_raises_converter_error_on_nonzero_returncode(
        self, converter: AudioConverter, valid_mp3_data: bytes
    ) -> None:
        with patch.object(converter, "_get_ffmpeg", new=AsyncMock(return_value="/usr/bin/ffmpeg")):
            with patch("asyncio.create_subprocess_exec") as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.returncode = 1
                mock_proc.wait = AsyncMock()
                mock_subprocess.return_value = mock_proc

                with patch("app.audio.audio_converter.tempfile.NamedTemporaryFile") as mock_tmp:
                    mock_src = MagicMock()
                    mock_src.__enter__ = MagicMock(return_value=mock_src)
                    mock_src.__exit__ = MagicMock(return_value=False)
                    mock_src.name = "/tmp/src.mp3"

                    mock_dst = MagicMock()
                    mock_dst.__enter__ = MagicMock(return_value=mock_dst)
                    mock_dst.__exit__ = MagicMock(return_value=False)
                    mock_dst.name = "/tmp/dst.wav"

                    mock_tmp.side_effect = [mock_src, mock_dst]

                    with patch("app.audio.audio_converter.os.unlink"):
                        with pytest.raises(AudioConverterError) as exc_info:
                            await converter.convert(valid_mp3_data, target_format="wav")
                        assert "1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_not_found_when_ffmpeg_missing(
        self, converter: AudioConverter, valid_mp3_data: bytes
    ) -> None:
        with patch.object(converter, "_get_ffmpeg", new=AsyncMock(
            side_effect=AudioConverterNotFoundError("ffmpeg not found in PATH.")
        )):
            with pytest.raises(AudioConverterNotFoundError):
                await converter.convert(valid_mp3_data, target_format="wav")
