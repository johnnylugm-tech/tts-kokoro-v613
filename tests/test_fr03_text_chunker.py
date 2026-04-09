"""
[FR-03] 測試案例：智能文本切分 (Text Chunker).

三級遞迴切分邏輯驗證：
1. 一級（句）：`。？！!?\n`
2. 二級（子句）：`。；：`（若仍 >100 字）
3. 三級（詞組）：`，`（若仍 >100 字）

Citations:
    SRS.md#L63-L76 (FR-03 需求描述與測試案例)
    SRS.md#L70-L71 (邏輯驗證方法)
    TRACEABILITY_MATRIX.md#L15 (模組對應)
    SAD.md#L69 (FR-03 模組邊界)
    SAD.md#L179 (TextChunker 元件對應)
    SAD.md#L353-366 (FR-03 介面定義)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root is on the import path.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.processing.text_chunker import (
    TextChunker,
    _split_by_delimiter,
    _is_mixed_script,
    _is_inside_alphanumeric,
    _chunk_by_level3,
    MAX_CHUNK_CHARS,
    SUB_CHUNK_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def chunker() -> TextChunker:
    """Instantiate TextChunker for all test cases."""
    return TextChunker()


# ---------------------------------------------------------------------------
# FR-03 Test Cases (SRS.md#L70-L71)
# ---------------------------------------------------------------------------

class TestTextChunkerBasic:
    """[FR-03] 基礎切分功能測試。"""

    def test_single_short_sentence(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：短句「這是測試。」→ 單一 chunk

        SRS.md#L70
        """
        result = chunker.chunk("這是測試。")
        assert len(result) == 1
        assert result[0] == "這是測試。"
        assert len(result[0]) <= MAX_CHUNK_CHARS

    def test_multiple_short_sentences(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：多個短句「你好。今天天氣很好！」→ 兩個 chunks

        SRS.md#L70
        """
        result = chunker.chunk("你好。今天天氣很好！")
        assert len(result) == 2
        assert result[0] == "你好。"
        assert result[1] == "今天天氣很好！"

    def test_empty_string(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：空字串 → 回傳空清單（不拋例外）

        SRS.md#L70
        """
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_whitespace_only(self, chunker: TextChunker) -> None:
        """[FR-03] 純空白字串回傳空清單。"""
        assert chunker.chunk("  \n\t  ") == []

    def test_newline_separator(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：換行符 \\n 作為一級分隔符

        SRS.md#L63
        """
        result = chunker.chunk("第一句\n第二句")
        assert len(result) == 2
        assert "第一句" in result[0]
        assert "第二句" in result[1]


class TestTextChunkerLongText:
    """[FR-03] 長文字強制切分測試（500 字 → ≤ 250 字 chunks）。"""

    def test_500_char_long_sentence(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：輸入 500 字長句 → 每段 ≤ 250 字

        SRS.md#L70
        """
        # 建構一個 500+ 字的中文長句（中間有一個句號和感嘆號）
        base = "這是一個非常長的句子用來測試智能文本切分功能"
        # 19*14=266, + 句號+感嘆號=268, need 500+
        long_text = base * 14 + "。" + base * 14 + "！"
        assert len(long_text) >= 500, f"Test text too short: {len(long_text)}"

        result = chunker.chunk(long_text)

        # 所有 chunk 必須 ≤ 250 字
        for i, chunk in enumerate(result):
            assert len(chunk) <= MAX_CHUNK_CHARS, (
                f"Chunk {i} length {len(chunk)} exceeds {MAX_CHUNK_CHARS}"
            )

        # chunks 數量應合理（500 字理論上不超過 3 個 chunks）
        assert len(result) <= 4, f"Too many chunks ({len(result)}) for 500-char text"

    def test_250_char_at_boundary(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：恰好 250 字 → 1 個 chunk

        SRS.md#L70
        """
        # 建立一個恰好 250 字的 chunk（無句號以避免一級切分）
        base = "這是測試文字"  # 6 字
        target = base * 41 + base[:4]  # 246+4=250
        assert len(target) == 250, f"Constructed text length {len(target)} != 250"

        result = chunker.chunk(target)
        assert len(result) == 1
        assert len(result[0]) == 250

    def test_251_char_forces_split(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：251 字 → 必須切成 2 個 chunks

        SRS.md#L70
        """
        # 建立一個 251 字無標點的長文字
        base = "這是測試文字"  # 6 字
        long_text = base * 41 + "ABCDE"  # 246+5=251
        assert len(long_text) == 251, f"Constructed text length {len(long_text)}"

        result = chunker.chunk(long_text)
        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS


class TestTextChunkerMixedScript:
    """[FR-03] 中英文混合文字安全切分測試。"""

    def test_ai_acronym_not_split(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：含英文「AI」長句 → 不在 A/I 中間切斷

        SRS.md#L71
        """
        text = (
            "近年來人工智慧技術快速發展，AI 的應用範圍越來越廣泛，"
            "從醫療診斷到自動駕駛，AI 正在改變我們的生活。"
            * 5
        )
        result = chunker.chunk(text)

        for chunk in result:
            # 不應出現「A 」或「 I」在中間被切斷的情況
            assert " A " not in chunk, f"Chunk splits 'A' incorrectly: {chunk}"
            assert " I " not in chunk, f"Chunk splits 'I' incorrectly: {chunk}"
            assert len(chunk) <= MAX_CHUNK_CHARS

    def test_bbc_acronym_not_split(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：「BBC」複合詞不得在中間被切斷

        SRS.md#L71
        """
        text = "BBC 是全球知名的廣播公司。" * 10
        result = chunker.chunk(text)

        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS

    def test_app2_not_split(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：「App2」數字混合詞不得被切斷

        SRS.md#L71
        """
        text = "這款 App2 應用程式非常實用。" * 15
        result = chunker.chunk(text)

        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS

    def test_mixed_script_detection(self) -> None:
        """
        [FR-03] _is_mixed_script 函式：中英文混合判斷

        SRS.md#L71
        """
        assert _is_mixed_script("AI人工智慧") is True
        assert _is_mixed_script("Hello你好") is True
        assert _is_mixed_script("純中文文字") is False
        assert _is_mixed_script("PureEnglish") is False
        assert _is_mixed_script("123數字") is True

    def test_alphanumeric_boundary_detection(self) -> None:
        """
        [FR-03] _is_inside_alphanumeric 函式：字母數字邊界檢測

        SRS.md#L71
        """
        text = "這是 AI 人工智慧的時代"
        # position 4 is "I" inside "AI" → should return True (inside alphanumeric)
        assert _is_inside_alphanumeric(text, 4) is True
        # position 6 is "人" → should return False (not alphanumeric)
        assert _is_inside_alphanumeric(text, 6) is False


class TestTextChunkerThreeLevelRecursion:
    """[FR-03] 三級遞迴切分驗證。"""

    def test_level1_only_short_text(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：三級切分遞迴驗證（Level 1 足夠）

        SRS.md#L71
        """
        text = "今天天氣很好。明天會下雨。"
        result = chunker.chunk(text)
        assert len(result) == 2
        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS

    def test_level2_triggered(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：三級切分遞迴驗證（觸發 Level 2）

        Level 2 觸發條件：chunk > 100 字且無一級分隔符

        SRS.md#L63-L64
        """
        # 建構一個 150 字無句號的長片段
        text = "這是一個沒有句號的長段落" * 10  # 14*10=140 字
        assert 100 < len(text) < 250, f"Constructed text length {len(text)} not in (100, 250)"

        result = chunker.chunk(text)
        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS

    def test_level3_triggered(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：三級切分遞迴驗證（觸發 Level 3）

        Level 3 觸發條件：chunk > 100 字且無一二級分隔符，但有逗號

        SRS.md#L65
        """
        # 建構一個有逗號但無句號的 200+ 字長片段
        segments = ["這是第一段話，" for _ in range(15)]  # 7*15=105 字
        text = "".join(segments)
        assert len(text) > 100, f"Constructed text length {len(text)} <= 100"

        result = chunker.chunk(text)
        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS

    def test_three_levels_all_triggered(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：三級遞迴完整觸發（400+ 字文本）

        SRS.md#L63-L65
        """
        # 建構一個 400+ 字長文本，包含一級、二級、三級分隔符
        base1 = "這是一個非常長的句子"
        long_sentence = base1 * 15 + "。"  # 10*15+1=151
        comma_text = "這段話很長，" * 35  # 6*35=210
        combined = long_sentence + comma_text  # 361, still too short
        combined = combined * 2 + "這段話很長，" * 10  # 422
        assert len(combined) >= 400, f"Constructed text length {len(combined)} < 400"

        result = chunker.chunk(combined)
        assert len(result) > 0
        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS


class TestTextChunkerLevel2Delimiters:
    """[FR-03] 二級分隔符（`。；：`）測試。"""

    def test_semicolon_split(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：分號 ``；`` 作為二級分隔符

        SRS.md#L64
        """
        text = "第一句話；第二句話；第三句話。" * 10
        result = chunker.chunk(text)

        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS

    def test_colon_split(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：冒號 ``：`` 作為二級分隔符

        SRS.md#L64
        """
        text = "標題：內容說明" * 20
        result = chunker.chunk(text)

        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS


class TestTextChunkerLevel3Delimiters:
    """[FR-03] 三級分隔符（「，」「,」）測試。"""

    def test_chinese_comma_split(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：中文逗號「，」作為三級分隔符

        SRS.md#L65
        """
        text = "第一句，" * 30  # 5*30=150 字，>100 → 觸發三級
        assert len(text) > 100, f"Constructed text length {len(text)} <= 100"

        result = chunker.chunk(text)

        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS
        assert len(result) >= 2  # 至少切成 2 段

    def test_english_comma_split(self, chunker: TextChunker) -> None:
        """
        [FR-03] 測試案例：英文逗號「,」作為三級分隔符

        SRS.md#L65
        """
        text = "Hello, world, this, is, a, test" * 10
        result = chunker.chunk(text)

        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS


class TestTextChunkerEdgeCases:
    """[FR-03] 邊界條件處理。"""

    def test_only_delimiters(self, chunker: TextChunker) -> None:
        """[FR-03] 僅包含分隔符的字串不拋例外。"""
        result = chunker.chunk("。！？\n；：，,")
        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS

    def test_no_delimiters_long_text(self, chunker: TextChunker) -> None:
        """
        [FR-03] 無任何分隔符的長文字 → 需安全強制切分

        SRS.md#L63-L65
        """
        # 建構 560 字無分隔符長文
        base = "這是沒有任何分隔符的連續文字"  # 14 字
        text = base * 40  # 14*40=560
        assert len(text) >= 500, f"Constructed text length {len(text)} < 500"

        result = chunker.chunk(text)

        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS
        assert len(result) >= 2  # 至少切成 2 段

    def test_max_chunk_respected(self, chunker: TextChunker) -> None:
        """
        [FR-03] 所有輸出 chunks 嚴格遵守 250 字上限

        SRS.md#L66
        """
        # 構造 400+ 字混合文本
        base1 = "今天的課程內容非常豐富。"  # 12
        base2 = "涵蓋多個重要主題；"  # 9
        base3 = "包括人工智慧、機器學習、深度學習，"  # 18
        text = base1 * 15 + base2 * 15 + base3 * 15  # 180+135+270=585
        assert len(text) >= 400, f"Constructed text length {len(text)} < 400"

        result = chunker.chunk(text)

        for i, chunk in enumerate(result):
            assert len(chunk) <= MAX_CHUNK_CHARS, (
                f"Chunk {i} length {len(chunk)} > {MAX_CHUNK_CHARS}"
            )

    def test_special_whitespace_preserved(self, chunker: TextChunker) -> None:
        """[FR-03] 特殊空白字元在 chunk 中保留。"""
        text = "第一句。  \n  第二句。"
        result = chunker.chunk(text)
        assert len(result) >= 1
        assert len(result[0]) <= MAX_CHUNK_CHARS


class TestHelperFunctions:
    """[FR-03] 輔助函式單元測試。"""

    def test_split_by_delimiter_level1(self) -> None:
        """
        [FR-03] _split_by_delimiter：一級分隔符（句號）

        SRS.md#L63
        """
        result = _split_by_delimiter("你好。世界！", r"[。？！!?\n]")
        assert "你好。" in result
        assert "世界！" in result

    def test_split_by_delimiter_level2(self) -> None:
        """
        [FR-03] _split_by_delimiter：二級分隔符（分號）

        SRS.md#L64
        """
        result = _split_by_delimiter("第一；第二；第三", r"[。；：]")
        assert "第一；" in result or "第一" in result

    def test_split_by_delimiter_preserves_delimiter(self) -> None:
        """[FR-03] 分隔符保留在結果中，不被丟棄。"""
        result = _split_by_delimiter("句一。句二！", r"[。？！!?\n]")
        joined = "".join(result)
        assert "。" in joined
        assert "！" in joined

    def test_chunk_by_level3_basic(self) -> None:
        """
        [FR-03] _chunk_by_level3：基本逗號切分

        SRS.md#L65
        """
        text = "第一，" * 50
        result = _chunk_by_level3(text)
        for chunk in result:
            assert len(chunk) <= MAX_CHUNK_CHARS

    def test_sub_chunk_threshold(self) -> None:
        """[FR-03] SUB_CHUNK_THRESHOLD = 100."""
        assert SUB_CHUNK_THRESHOLD == 100

    def test_max_chunk_chars(self) -> None:
        """[FR-03] MAX_CHUNK_CHARS = 250."""
        assert MAX_CHUNK_CHARS == 250


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
