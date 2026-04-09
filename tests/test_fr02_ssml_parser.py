"""[FR-02] SSML Parser 單元測試。

Tests:
    - <prosody rate="0.9">文字</prosody> → speed=0.9
    - <voice name="zf_yunxi">文字</voice> → 音色切換為 zf_yunxi
    - <break time="500ms"/> → 插入停頓字元
    - XML 解析失敗時 fallback 純文字

Citations:
    SRS.md#L41
    SAD.md#L301
"""

from __future__ import annotations

import pytest

from app.processing.ssml_parser import (
    SSMLParser,
    SSMLSegment,
    SSMLParseError,
    SegmentType,
)


# ─────────────────────────────────────────────────────────────────────────────
# Happy-path tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBreak:
    """[FR-02] <break time="500ms"/> → 插入停頓字元。"""

    def test_break_milliseconds(self):
        segs = SSMLParser().parse('<break time="500ms"/>')
        assert len(segs) == 1
        assert segs[0].type == SegmentType.BREAK
        assert segs[0].break_ms == 500

    def test_break_seconds(self):
        segs = SSMLParser().parse('<break time="2s"/>')
        assert len(segs) == 1
        assert segs[0].type == SegmentType.BREAK
        assert segs[0].break_ms == 2000

    def test_break_decimal_seconds(self):
        segs = SSMLParser().parse('<break time="1.5s"/>')
        assert len(segs) == 1
        assert segs[0].type == SegmentType.BREAK
        assert segs[0].break_ms == 1500

    def test_break_default(self):
        segs = SSMLParser().parse("<break/>")
        assert len(segs) == 1
        assert segs[0].type == SegmentType.BREAK
        assert segs[0].break_ms == 500  # default

    def test_break_invalid_format_raises(self):
        with pytest.raises(SSMLParseError):
            SSMLParser()._normalize_break("invalid")


class TestProsody:
    """[FR-02] <prosody rate="0.9"> → speed=0.9。"""

    def test_prosody_rate_float(self):
        segs = SSMLParser().parse('<prosody rate="0.9">文字</prosody>')
        assert len(segs) == 1
        assert segs[0].type == SegmentType.TEXT
        assert segs[0].text == "文字"
        assert segs[0].prosody["rate"] == 0.9

    def test_prosody_rate_integer(self):
        segs = SSMLParser().parse('<prosody rate="1">測試</prosody>')
        assert segs[0].prosody["rate"] == 1.0

    def test_prosody_rate_keyword_fast(self):
        segs = SSMLParser().parse('<prosody rate="fast">快</prosody>')
        assert segs[0].prosody["rate"] == 1.2

    def test_prosody_rate_keyword_slow(self):
        segs = SSMLParser().parse('<prosody rate="slow">慢</prosody>')
        assert segs[0].prosody["rate"] == 0.8

    def test_prosody_nested_in_text(self):
        segs = SSMLParser().parse(
            'Hello <prosody rate="0.8">world</prosody> test'
        )
        # Without <speak> wrapper, non-XML text causes parse error → fallback
        # so we wrap in <speak> for explicit test
        segs = SSMLParser().parse(
            '<speak>Hello <prosody rate="0.8">world</prosody> test</speak>'
        )
        assert len(segs) == 3
        assert segs[0].type == SegmentType.TEXT
        assert segs[0].text == "Hello "
        assert segs[1].type == SegmentType.TEXT
        assert segs[1].text == "world"
        assert segs[1].prosody["rate"] == 0.8
        assert segs[2].type == SegmentType.TEXT
        assert segs[2].text == " test"


class TestVoice:
    """[FR-02] <voice name="zf_yunxi"> → 音色切換為 zf_yunxi。"""

    def test_voice_name(self):
        segs = SSMLParser().parse(
            '<voice name="zf_yunxi">文字</voice>'
        )
        assert len(segs) == 1
        assert segs[0].type == SegmentType.TEXT
        assert segs[0].text == "文字"
        assert segs[0].voice_name == "zf_yunxi"

    def test_voice_nested_text(self):
        segs = SSMLParser().parse(
            '<speak>正常音色 '
            '<voice name="zf_yunxi">替換音色</voice> '
            '恢復音色</speak>'
        )
        assert len(segs) == 3
        assert segs[0].voice_name is None
        assert segs[1].voice_name == "zf_yunxi"
        assert segs[2].voice_name is None

    def test_voice_no_name_attribute(self):
        segs = SSMLParser().parse("<voice>文字</voice>")
        assert segs[0].voice_name is None


class TestEmphasis:
    """[FR-02] <emphasis level="strong"> → speed ×1.1。"""

    def test_emphasis_strong(self):
        segs = SSMLParser().parse(
            '<emphasis level="strong">強調文字</emphasis>'
        )
        assert len(segs) == 1
        assert segs[0].type == SegmentType.TEXT
        assert segs[0].text == "強調文字"
        assert segs[0].prosody["emphasis_level"] == "strong"
        assert segs[0].prosody["rate_factor"] == 1.1

    def test_emphasis_reduced(self):
        segs = SSMLParser().parse(
            '<emphasis level="reduced">低調</emphasis>'
        )
        assert segs[0].prosody["emphasis_level"] == "reduced"
        assert segs[0].prosody["rate_factor"] == 0.9

    def test_emphasis_default_level(self):
        segs = SSMLParser().parse("<emphasis>中等強調</emphasis>")
        assert segs[0].prosody["emphasis_level"] == "moderate"


class TestPhoneme:
    """[FR-02] <phoneme alphabet="ipa"> → 保留原生。"""

    def test_phoneme_ipa(self):
        segs = SSMLParser().parse(
            '<phoneme alphabet="ipa" ph="həˈloʊ">hello</phoneme>'
        )
        assert len(segs) == 1
        assert segs[0].type == SegmentType.PHONEME
        assert segs[0].text == "hello"
        assert segs[0].phoneme_alphabet == "ipa"
        assert segs[0].phoneme_ph == "həˈloʊ"

    def test_phoneme_without_ph_attr(self):
        segs = SSMLParser().parse("<phoneme alphabet='ipa'>你好</phoneme>")
        assert segs[0].phoneme_alphabet == "ipa"
        assert segs[0].phoneme_ph == ""


class TestSpeakRoot:
    """[FR-02] <speak> 根元素。"""

    def test_speak_root(self):
        segs = SSMLParser().parse("<speak>純文字內容</speak>")
        assert len(segs) == 1
        assert segs[0].type == SegmentType.TEXT
        assert segs[0].text == "純文字內容"

    def test_speak_with_multiple_children(self):
        segs = SSMLParser().parse(
            '<speak>嗨<break time="1s"/>你<voice name="zf_yunxi">好</voice></speak>'
        )
        assert len(segs) == 4
        assert segs[0].type == SegmentType.TEXT
        assert segs[0].text == "嗨"
        assert segs[1].type == SegmentType.BREAK
        assert segs[1].break_ms == 1000
        assert segs[2].type == SegmentType.TEXT
        assert segs[2].text == "你"
        assert segs[3].type == SegmentType.TEXT
        assert segs[3].text == "好"
        assert segs[3].voice_name == "zf_yunxi"


class TestFallback:
    """[FR-02] XML 解析失敗時 fallback 純文字。"""

    def test_invalid_xml_fallback(self):
        plain = "這是普通文字，沒有任何SSML標籤"
        segs = SSMLParser().parse(plain)
        assert len(segs) == 1
        assert segs[0].type == SegmentType.TEXT
        assert segs[0].text == plain

    def test_malformed_xml_fallback(self):
        segs = SSMLParser().parse("<broken<tag")
        assert len(segs) == 1
        assert segs[0].type == SegmentType.TEXT
        assert "<broken<tag" in segs[0].text


class TestEmptyInput:
    """Edge case: 空輸入。"""

    def test_empty_string(self):
        segs = SSMLParser().parse("")
        assert segs == []

    def test_whitespace_only(self):
        segs = SSMLParser().parse("   ")
        assert segs == []


class TestNormalizeRate:
    """[FR-02] rate 屬性格式正規化。"""

    @pytest.mark.parametrize(
        "input_val,expected",
        [
            ("0.9", 0.9),
            ("1.0", 1.0),
            ("1.2", 1.2),
            ("x-slow", 0.5),
            ("slow", 0.8),
            ("medium", 1.0),
            ("fast", 1.2),
            ("x-fast", 1.5),
        ],
    )
    def test_rate_keywords_and_floats(self, input_val, expected):
        parser = SSMLParser()
        assert parser._normalize_rate(input_val) == expected

    def test_rate_unknown_returns_none(self):
        assert SSMLParser()._normalize_rate("unknown") is None


class TestNormalizeBreak:
    """[FR-02] break time 屬性格式正規化。"""

    @pytest.mark.parametrize(
        "input_val,expected_ms",
        [
            ("500ms", 500),
            ("2000ms", 2000),
            ("2s", 2000),
            ("1.5s", 1500),
            ("0.1s", 100),
        ],
    )
    def test_break_formats(self, input_val, expected_ms):
        assert SSMLParser()._normalize_break(input_val) == expected_ms
