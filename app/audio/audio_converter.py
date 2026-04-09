"""
[FR-08] ffmpeg 音訊格式轉換模組。

支援 MP3 ↔ WAV 雙向轉換，採用 Lazy Init + 雙重檢查鎖定模式。

Citations:
    SRS.md#L154-L162 (FR-08 需求描述與測試案例)
    SAD.md#L557-L572 (AudioConverter 類別介面與錯誤定義)
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from typing import Final

# Supported conversion formats.
SUPPORTED_FORMATS: Final[set[str]] = {"mp3", "wav"}


class AudioConverterError(RuntimeError):
    """[FR-08] L2 錯誤：音訊轉換失敗。"""


class AudioConverterNotFoundError(AudioConverterError):
    """[FR-08] L2 錯誤：系統中找不到 ffmpeg。"""


class AudioConverter:
    """
    [FR-08] ffmpeg 音訊格式轉換器（Lazy Init）。

    支援 MP3 ↔ WAV 雙向轉換。使用雙重檢查鎖定確保執行緒安全。

    Citations:
        SRS.md#L154-L162
        SAD.md#L557-L572
    """

    def __init__(self) -> None:
        self._ffmpeg_path: str | None = None
        self._init_lock: asyncio.Lock = asyncio.Lock()

    async def _get_ffmpeg(self) -> str:
        """
        [FR-08] 取得 ffmpeg 路徑（雙重檢查鎖定）。

        首次呼叫時以 Lock 保護避免競爭條件；之後直接回傳快取路徑。
        若系統中找不到 ffmpeg，拋出 AudioConverterNotFoundError。

        Raises:
            AudioConverterNotFoundError: ffmpeg 不在 PATH 中。

        Citations:
            SRS.md#L154-L162
            SAD.md#L561-L565
        """
        if self._ffmpeg_path is None:
            async with self._init_lock:
                if self._ffmpeg_path is None:
                    path = shutil.which("ffmpeg")
                    if path is None:
                        raise AudioConverterNotFoundError(
                            "ffmpeg not found in PATH."
                        )
                    self._ffmpeg_path = path
        return self._ffmpeg_path

    async def convert(
        self,
        audio_data: bytes,
        target_format: str,
        source_format: str = "mp3",
    ) -> bytes:
        """
        [FR-08] 將音訊資料從來源格式轉換為目標格式。

        內部以 subprocess 呼叫 ffmpeg，寫入暫存檔後讀回轉換結果。
        支援格式：MP3 ↔ WAV（由 SUPPORTED_FORMATS 定義）。

        Args:
            audio_data: 原始音訊位元組。
            target_format: 目標格式（"mp3" 或 "wav"）。
            source_format: 來源格式（預設 "mp3"）。

        Returns:
            轉換後的音訊位元組。

        Raises:
            AudioConverterError: 轉換過程失敗（L2）。
            AudioConverterNotFoundError: ffmpeg 不存在（L2）。
            ValueError: 來源或目標格式不支援。

        Citations:
            SRS.md#L154-L162
            SAD.md#L566-L570
        """
        if source_format not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported source format: {source_format!r}. "
                f"Supported: {SUPPORTED_FORMATS!r}."
            )
        if target_format not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported target format: {target_format!r}. "
                f"Supported: {SUPPORTED_FORMATS!r}."
            )

        ffmpeg_path = await self._get_ffmpeg()

        src_ext = source_format.lstrip(".")
        tgt_ext = target_format.lstrip(".")

        # ffmpeg input/output flags per format pair
        format_flags: dict[tuple[str, str], list[str]] = {
            ("mp3", "wav"): ["-f", "mp3", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2"],
            ("wav", "mp3"): ["-f", "wav", "-acodec", "libmp3lame", "-b:a", "192k"],
        }
        flags = format_flags.get((src_ext, tgt_ext), [])

        with tempfile.NamedTemporaryFile(suffix=f".{src_ext}", delete=False) as src_in:
            src_in.write(audio_data)
            src_path = src_in.name

        try:
            with tempfile.NamedTemporaryFile(suffix=f".{tgt_ext}", delete=False) as dst_out:
                dst_path = dst_out.name

            proc = await asyncio.create_subprocess_exec(
                ffmpeg_path,
                "-y",
                "-loglevel", "error",
                "-i", src_path,
                *flags,
                dst_path,
            )
            await proc.wait()

            if proc.returncode != 0:
                raise AudioConverterError(
                    f"ffmpeg exited with code {proc.returncode}."
                )

            with open(dst_path, "rb") as f:
                result = f.read()

            return result

        finally:
            # Clean up temp files even on error.
            try:
                os.unlink(src_path)
                os.unlink(dst_path)
            except OSError:
                pass
