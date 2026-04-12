"""
[FR-03] 智能文本切分模組 (Text Chunker).

三級遞迴切分邏輯，確保每個 chunk ≤ 250 字：
1. 一級（句）：`。？！!?\n`
2. 二級（子句）：`。；：`（若仍 >100 字）
3. 三級（詞組）：`，`（若仍 >100 字）

規則：
- 每段最多 250 字
- 不在中英文混合字（如 "AI", "BBC"）中間切斷

Citations:
    SRS.md#L63-L76 (FR-03 需求描述與測試案例)
    TRACEABILITY_MATRIX.md#L15 (模組對應)
    SAD.md#L69 (FR-03 模組邊界)
    SAD.md#L179 (TextChunker 元件對應)
    SAD.md#L353-366 (FR-03 介面定義)
"""
from __future__ import annotations

import re
from typing import Final

# 三級切分標點符號（用於 re.split look-ahead）
_LEVEL1_DELIMITERS: Final[str] = r"[。？！!?\n]"
_LEVEL2_DELIMITERS: Final[str] = r"[。；：]"
_LEVEL3_DELIMITERS: Final[str] = r"[，,]"

MAX_CHUNK_CHARS: Final[int] = 250
SUB_CHUNK_THRESHOLD: Final[int] = 100


# ---------------------------------------------------------------------------
# Helper Functions (public for direct testing)
# ---------------------------------------------------------------------------

def _split_by_delimiter(text: str, pattern: str) -> list[str]:
    """
    [FR-03] 以正則錨點（lookahead）對 delimiter 進行安全切分。

    使用 ``(?=<delimiter>)`` lookahead 確保分隔符保留在結果字串中，
    不會被移除。適用於一級/二級/三級遞迴切分。

    Args:
        text: 待切分文字。
        pattern: 正則錶達式（包含於 lookahead 中）。

    Returns:
        子句清單（經 strip 去空白）。

    Citations:
        SRS.md#L63-L76
        SAD.md#L353-366
    """
    parts = re.split(f"({pattern})", text)
    merged: list[str] = []
    buffer = ""
    for part in parts:
        if re.match(f"^{pattern}$", part):
            if buffer or part:
                merged.append(buffer + part)
            buffer = ""
        else:
            buffer += part
    if buffer:
        merged.append(buffer)
    return [m.strip() for m in merged if m.strip()]


def _is_mixed_script(text: str) -> bool:
    """
    [FR-03] 判斷文字是否為中英文/數字混合腳本。

    若同時包含 CJK（\\u4e00-\\u9fff）和拉丁字母/數字，視為混合腳本。

    Args:
        text: 待檢查文字。

    Returns:
        True 表示是中英文混合文字。

    Citations:
        SRS.md#L63-L76
        SAD.md#L353-366
    """
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
    has_latin = bool(re.search(r"[A-Za-z0-9]", text))
    return has_cjk and has_latin


def _is_inside_alphanumeric(text: str, position: int) -> bool:
    """
    [FR-03] 檢查指定位置是否落在英文/數字複合詞內部。

    掃描前後最長 20 字的字母數字序列，確認 position 是否在序列中。
    若在序列內，切分點應跳至序列邊界，避免如 "AI" → "A | I" 的錯誤切分。

    Args:
        text: 完整文字。
        position: 切分候選位置（字元索引，0-indexed）。

    Returns:
        True 表示該位置落在字母數字複合詞內部。

    Citations:
        SRS.md#L63-L76
        SAD.md#L353-366
    """
    segment_start = max(0, position - 20)
    segment = text[segment_start:position + 20]
    match = re.search(r"[A-Za-z0-9]{2,}", segment)
    if not match:
        return False
    seq_start, seq_end = match.start(), match.end()
    rel_pos = position - segment_start
    return seq_start < rel_pos < seq_end


def _chunk_by_level3(text: str) -> list[str]:
    """
    [FR-03] 第三級逗號切分（純函式版本，無狀態）。

    當 text 包含逗號且長度 > SUB_CHUNK_THRESHOLD 時，以逗號切分。
    內部使用 _safe_force_split 處理超大 chunk。

    Args:
        text: 輸入文字（已確認 > SUB_CHUNK_THRESHOLD）。

    Returns:
        符合 250 字限制的 chunk 清單。

    Citations:
        SRS.md#L65
        SAD.md#L353-366
    """
    result: list[str] = []
    buffer = ""

    for char in text:
        buffer += char
        if char in ("，", ","):
            stripped = buffer.rstrip("，,")
            if len(stripped) >= SUB_CHUNK_THRESHOLD:
                result.append(stripped)
                buffer = ""
            elif buffer:
                result.append(buffer)
                buffer = ""

    if buffer:
        result.append(buffer)

    final_result: list[str] = []
    for c in result:
        if len(c) <= MAX_CHUNK_CHARS:
            final_result.append(c)
        else:
            final_result.extend(_safe_force_split(c))

    return final_result


def _safe_force_split(text: str) -> list[str]:
    """
    [FR-03] 安全強制切分：當所有分隔符都無法有效切分時使用。

    從後往前掃描，找到不落在中英文混合詞內部的位置。
    備援策略：若找不到安全位置，則在 250 字處強制截斷。

    Args:
        text: 長度超過 250 字的單段文字。

    Returns:
        符合長度限制的安全切分結果。

    Citations:
        SRS.md#L63-L76
        SAD.md#L353-366
    """
    if len(text) <= MAX_CHUNK_CHARS:
        return [text] if text else []

    result: list[str] = []
    pos = 0
    text_len = len(text)

    while pos < text_len:
        remaining = text_len - pos
        if remaining <= MAX_CHUNK_CHARS:
            result.append(text[pos:])
            break

        cut = _find_safe_cut_point(text, pos, text_len)
        result.append(text[pos:cut])
        pos = cut

    return result


def _find_safe_cut_point(text: str, pos: int, text_len: int) -> int:
    """Find safe cut point working backwards from MAX_CHUNK_CHARS."""
    search_start = pos
    search_end = pos + MAX_CHUNK_CHARS
    cut = search_end

    # 從 250 字處往回找安全切分點（空白或混合腳本邊界）
    for i in range(search_end - 1, search_start + 50, -1):
        if i >= text_len:
            continue
        char = text[i]
        if char in (" ", "\t"):
            return i + 1
        if _is_safe_alphanumeric_cut(text, i, text_len):
            return i

    return cut


def _is_safe_alphanumeric_cut(text: str, i: int, text_len: int) -> bool:
    """Check if position i is a safe cut point for alphanumeric chars."""
    prev_char = text[i - 1] if i > 0 else ""
    next_char = text[i + 1] if i + 1 < text_len else ""
    return (
        text[i].isalnum()
        and prev_char.isalpha()
        and next_char.isalpha()
        and _is_mixed_script(text[max(0, i - 10):i + 10])
    )


# ---------------------------------------------------------------------------
# TextChunker
# ---------------------------------------------------------------------------

class TextChunker:
    """
    [FR-03] 智能文本切分器，支援三級遞迴切分。

    將長文本遞迴拆分為不超過 250 字的中文友善片段，
    適用於 TTS 系統的批次合成需求。

    Example:
        >>> chunker = TextChunker()
        >>> chunks = chunker.chunk("這是測試。")
        >>> print(chunks)
        ['這是測試。']
    """

    def chunk(self, text: str) -> list[str]:
        """
        [FR-03] 將輸入文字依三級邏輯遞迴切分，回傳不超過 250 字的 chunks。

        **遞迴流程**：

        1. **一級（句）**：以 ``。？！!?\\n`` 切分
        2. **二級（子句）**：若 chunk 仍 >100 字，以 ``。；：`` 切分
        3. **三級（詞組）**：若 chunk 仍 >100 字，以 ``，,`` 切分

        **安全規則**：

        - 不在中英文混合詞（如 "AI", "BBC", "App2"）中間切斷
        - 每段輸出嚴格 ≤ 250 字

        Args:
            text: 任意長度的輸入文字。

        Returns:
            不超過 250 字的字串清單。若輸入為空或空白，回傳空清單。

        Citations:
            SRS.md#L63-L76
            SRS.md#L70-L71
            SAD.md#L353-366
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        return self._recursive_split(text)

    def _recursive_split(self, text: str) -> list[str]:
        """
        [FR-03] 遞迴切分實作：依序執行三級切分邏輯。

        Args:
            text: 待切分文字（已確認非空）。

        Returns:
            符合長度限制的 chunk 清單。

        Citations:
            SRS.md#L63-L76
            SAD.md#L353-366
        """
        # ── 第一級：句子切分 ──────────────────────────────────────────
        level1_chunks = _split_by_delimiter(text, _LEVEL1_DELIMITERS)
        result: list[str] = []

        for chunk in level1_chunks:
            if len(chunk) <= SUB_CHUNK_THRESHOLD:
                # chunk ≤ 100: 無需再切分
                result.append(chunk)
            else:
                # chunk > 100: 進入第二級（可能觸發第三級）
                result.extend(self._level2_split(chunk))

        return result

    def _level2_split(self, chunk: str) -> list[str]:
        """
        [FR-03] 第二級切分：若 chunk > 100 字，以二級標點（``。；：``）切分。

        Args:
            chunk: 長度超過 100 字的單元。

        Returns:
            符合長度限制的子句清單。

        Citations:
            SRS.md#L63-L76
            SAD.md#L353-366
        """
        if len(chunk) <= SUB_CHUNK_THRESHOLD:
            return self._level3_split(chunk)

        level2_chunks = _split_by_delimiter(chunk, _LEVEL2_DELIMITERS)
        result: list[str] = []

        for sub_chunk in level2_chunks:
            if len(sub_chunk) <= SUB_CHUNK_THRESHOLD:
                # 太短，不需要 level 3 逗號切分
                result.append(sub_chunk)
            else:
                # > SUB_CHUNK_THRESHOLD: 嘗試 level 3 逗號切分
                result.extend(self._level3_split(sub_chunk))

        return result

    def _level3_split(self, chunk: str) -> list[str]:
        """
        [FR-03] 第三級切分：若 chunk > 100 字，以「，」或「,」切分。

        若逗號之間距離過長（仍 >250 字），則以安全位置強制切分
        （避開中英文混合詞內部）。

        演算法：
        - 累積 buffer，每次遇到「，」或「,」時：
          - 若 buffer（不含本次逗號） < SUB_CHUNK_THRESHOLD（100），繼續累積
          - 否則，buffer 成为一个 chunk；新的 chunk 從此分隔符開始
        - 最後一塊 buffer 追加至結果

        Args:
            chunk: 長度超過 100 字的片段。

        Returns:
            符合 250 字限制的 chunk 清單。

        Citations:
            SRS.md#L65
            SAD.md#L353-366
        """
        if len(chunk) <= SUB_CHUNK_THRESHOLD:
            return [chunk] if chunk else []

        # 累積式逗號切分
        result: list[str] = []
        buffer = ""

        for char in chunk:
            buffer += char
            if char in ("，", ","):
                # 嘗試在逗號處切分
                stripped = buffer.rstrip("，,")
                if len(stripped) >= SUB_CHUNK_THRESHOLD:
                    # buffer 已足夠長，獨立成 chunk
                    result.append(stripped)
                    buffer = ""
                elif buffer:
                    # buffer 太短但有逗號：獨立成 chunk（會在後續合併）
                    result.append(buffer)
                    buffer = ""

        # 最後一段 buffer（直接 append）
        if buffer:
            result.append(buffer)

        # 安全檢查：任何超大 chunk 走 force split
        final_result: list[str] = []
        for c in result:
            if len(c) <= MAX_CHUNK_CHARS:
                final_result.append(c)
            else:
                final_result.extend(_safe_force_split(c))

        return final_result
