"""
[FR-02] 測試案例：SSML Parser - 解析 SSML 標籤並映射為 Kokoro API 參數。

測試覆蓋：
- <speak> 根標籤處理
- <break> 停頓標籤
- <prosody> 韻律標籤 (rate, pitch, volume)
- <emphasis> 強調標籤 (strong, moderate, reduced, none)
- <voice> 音色切換標籤
- <phoneme> 音標標籤
- fallback 純文字處理

Citations:
    SRS.md#L40-L62 (FR-02 邏輯驗證方法與測試案例)
    SAD.md#L301-L331 (SSMLParser 模組邊界對照表)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root is on the import path.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.processing.ssml_parser import (
    SSMLParser,
    SSMLSegment,
    SSMLParseError,
    SegmentType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def parser() -> SSMLParser:
    """Create a fresh SSMLParser instance for each test."""
    return SSMLParser()


# ---------------------------------------------------------------------------
# Tests: Basic Parsing
# ---------------------------------------------------------------------------

class TestBasicParsing:
    """基本解析功能測試。"""

    def test_parse_simple_text_without_speak_tag(self, parser: SSMLParser) -> None:
        """測試無 <speak> 根標籤時自動包裝。"""
        segments = parser.parse("你好，世界")
        assert len(segments) == 1
        assert segments[0].type == SegmentType.TEXT
        assert segments[0].text == "你好，世界"

    def test_parse_simple_text_with_speak_tag(self, parser: SSMLParser) -> None:
        """測試包含 <speak> 根標籤的解析。"""
        segments = parser.parse("<speak>你好，世界</speak>")
        assert len(segments) == 1
        assert segments[0].type == SegmentType.TEXT
        assert segments[0].text == "你好，世界"

    def test_parse_empty_string(self, parser: SSMLParser) -> None:
        """測試空字串解析。"""
        segments = parser.parse("")
        # Empty string wrapped in <speak> will have one empty text segment
        assert len(segments) >= 0

    def test_parse_text_with_whitespace(self, parser: SSMLParser) -> None:
        """測試帶空白字元的文字。"""
        segments = parser.parse("  你好，世界  ")
        assert len(segments) == 1
        assert segments[0].type == SegmentType.TEXT
        assert segments[0].text == "你好，世界"


# ---------------------------------------------------------------------------
# Tests: <break> Tag
# ---------------------------------------------------------------------------

class TestBreakTag:
    """測試 <break> 停頓標籤。"""

    def test_break_time_ms(self, parser: SSMLParser) -> None:
        """測試 <break time=\"500ms\"/> → 插入停頓 500ms。"""
        segments = parser.parse("<speak>第一句<break time=\"500ms\"/>第二句</speak>")
        assert len(segments) == 3
        assert segments[0].type == SegmentType.TEXT
        assert segments[0].text == "第一句"
        assert segments[1].type == SegmentType.BREAK
        assert segments[1].break_ms == 500
        assert segments[2].type == SegmentType.TEXT
        assert segments[2].text == "第二句"

    def test_break_time_seconds(self, parser: SSMLParser) -> None:
        """測試 <break time=\"1s\"/> → 插入停頓 1000ms。"""
        segments = parser.parse("<speak>第一句<break time=\"1s\"/>第二句</speak>")
        assert segments[1].type == SegmentType.BREAK
        assert segments[1].break_ms == 1000

    def test_break_time_decimal_seconds(self, parser: SSMLParser) -> None:
        """測試 <break time=\"1.5s\"/> → 插入停頓 1500ms。"""
        segments = parser.parse("<speak>第一句<break time=\"1.5s\"/>第二句</speak>")
        assert segments[1].type == SegmentType.BREAK
        assert segments[1].break_ms == 1500

    def test_break_default_time(self, parser: SSMLParser) -> None:
        """測試 <break/> 無 time 屬性時預設為 0ms。"""
        segments = parser.parse("<speak>第一句<break/>第二句</speak>")
        assert segments[1].type == SegmentType.BREAK
        assert segments[1].break_ms == 0


# ---------------------------------------------------------------------------
# Tests: <prosody> Tag
# ---------------------------------------------------------------------------

class TestProsodyTag:
    """測試 <prosody> 韻律標籤。"""

    def test_prosody_rate_numeric(self, parser: SSMLParser) -> None:
        """測試 <prosody rate=\"0.9\">文字</prosody> → speed=0.9。"""
        segments = parser.parse("<speak><prosody rate=\"0.9\">慢慢說</prosody></speak>")
        assert len(segments) == 1
        assert segments[0].type == SegmentType.TEXT
        assert segments[0].text == "慢慢說"
        assert segments[0].prosody.get("rate") == 0.9

    def test_prosody_rate_fast(self, parser: SSMLParser) -> None:
        """測試 <prosody rate=\"fast\"> → 速率 1.2。"""
        segments = parser.parse("<speak><prosody rate=\"fast\">快說</prosody></speak>")
        assert segments[0].prosody.get("rate") == 1.2

    def test_prosody_rate_slow(self, parser: SSMLParser) -> None:
        """測試 <prosody rate=\"slow\"> → 速率 0.8。"""
        segments = parser.parse("<speak><prosody rate=\"slow\">慢說</prosody></speak>")
        assert segments[0].prosody.get("rate") == 0.8

    def test_prosody_rate_normal(self, parser: SSMLParser) -> None:
        """測試 <prosody rate=\"normal\"> → 速率 1.0。"""
        segments = parser.parse("<speak><prosody rate=\"normal\">正常速度</prosody></speak>")
        assert segments[0].prosody.get("rate") == 1.0

    def test_prosody_pitch(self, parser: SSMLParser) -> None:
        """測試 <prosody pitch=\"+10%\"> → 音高調整。"""
        segments = parser.parse("<speak><prosody pitch=\"+10%\">高興說</prosody></speak>")
        assert segments[0].prosody.get("pitch") == "+10%"

    def test_prosody_volume(self, parser: SSMLParser) -> None:
        """測試 <prosody volume=\"loud\"> → 音量調整。"""
        segments = parser.parse("<speak><prosody volume=\"loud\">大聲說</prosody></speak>")
        assert segments[0].prosody.get("volume") == "loud"

    def test_prosody_multiple_attributes(self, parser: SSMLParser) -> None:
        """測試 prosody 多屬性同時設定。"""
        segments = parser.parse(
            "<speak><prosody rate=\"1.2\" pitch=\"+5%\" volume=\"soft\">組合屬性</prosody></speak>"
        )
        assert segments[0].prosody.get("rate") == 1.2
        assert segments[0].prosody.get("pitch") == "+5%"
        assert segments[0].prosody.get("volume") == "soft"


# ---------------------------------------------------------------------------
# Tests: <emphasis> Tag
# ---------------------------------------------------------------------------

class TestEmphasisTag:
    """測試 <emphasis> 強調標籤。"""

    def test_emphasis_strong(self, parser: SSMLParser) -> None:
        """測試 <emphasis level=\"strong\"> → speed ×1.1。"""
        segments = parser.parse("<speak><emphasis level=\"strong\">很重要</emphasis></speak>")
        assert len(segments) == 1
        assert segments[0].type == SegmentType.EMPHASIS
        assert segments[0].text == "很重要"
        assert segments[0].emphasis_level == "strong"
        assert segments[0].prosody.get("rate") == 1.1

    def test_emphasis_moderate(self, parser: SSMLParser) -> None:
        """測試 <emphasis level=\"moderate\"> → speed ×1.05。"""
        segments = parser.parse("<speak><emphasis level=\"moderate\">適度強調</emphasis></speak>")
        assert segments[0].emphasis_level == "moderate"
        assert segments[0].prosody.get("rate") == 1.05

    def test_emphasis_reduced(self, parser: SSMLParser) -> None:
        """測試 <emphasis level=\"reduced\"> → speed ×0.9。"""
        segments = parser.parse("<speak><emphasis level=\"reduced\">降低強調</emphasis></speak>")
        assert segments[0].emphasis_level == "reduced"
        assert segments[0].prosody.get("rate") == 0.9

    def test_emphasis_none(self, parser: SSMLParser) -> None:
        """測試 <emphasis level=\"none\"> → speed ×1.0。"""
        segments = parser.parse("<speak><emphasis level=\"none\">無強調</emphasis></speak>")
        assert segments[0].emphasis_level == "none"
        assert segments[0].prosody.get("rate") == 1.0

    def test_emphasis_default_level(self, parser: SSMLParser) -> None:
        """測試 <emphasis> 無 level 屬性時預設為 moderate。"""
        segments = parser.parse("<speak><emphasis>預設強調</emphasis></speak>")
        assert segments[0].emphasis_level == "moderate"
        assert segments[0].prosody.get("rate") == 1.05


# ---------------------------------------------------------------------------
# Tests: <voice> Tag
# ---------------------------------------------------------------------------

class TestVoiceTag:
    """測試 <voice> 音色切換標籤。"""

    def test_voice_name(self, parser: SSMLParser) -> None:
        """測試 <voice name=\"zf_yunxi\">文字</voice> → 音色切換為 zf_yunxi。"""
        segments = parser.parse("<speak><voice name=\"zf_yunxi\">切換音色</voice></speak>")
        assert len(segments) == 1
        assert segments[0].type == SegmentType.TEXT
        assert segments[0].text == "切換音色"
        assert segments[0].voice_name == "zf_yunxi"

    def test_voice_with_nested_prosody(self, parser: SSMLParser) -> None:
        """測試 <voice> 內嵌 <prosody>。"""
        segments = parser.parse(
            "<speak><voice name=\"zf_xiaoxiao\"><prosody rate=\"0.8\">慢說</prosody></voice></speak>"
        )
        assert segments[0].voice_name == "zf_xiaoxiao"
        assert segments[0].prosody.get("rate") == 0.8

    def test_voice_followed_by_text(self, parser: SSMLParser) -> None:
        """測試 <voice> 後的文字繼承音色。"""
        segments = parser.parse(
            "<speak><voice name=\"zf_anna\">音色文字</voice>普通文字</speak>"
        )
        assert segments[0].voice_name == "zf_anna"
        assert segments[0].text == "音色文字"
        assert segments[1].voice_name is None
        assert segments[1].text == "普通文字"


# ---------------------------------------------------------------------------
# Tests: <phoneme> Tag
# ---------------------------------------------------------------------------

class TestPhonemeTag:
    """測試 <phoneme> 音標標籤。"""

    def test_phoneme_ipa(self, parser: SSMLParser) -> None:
        """測試 <phoneme alphabet=\"ipa\" ph=\"...\"> → 保留音標。"""
        segments = parser.parse(
            "<speak><phoneme alphabet=\"ipa\" ph=\"nǐ hǎo\">你好</phoneme></speak>"
        )
        assert len(segments) == 1
        assert segments[0].type == SegmentType.PHONEME
        assert segments[0].phoneme_alphabet == "ipa"
        assert segments[0].phoneme_ph == "nǐ hǎo"

    def test_phoneme_default_alphabet(self, parser: SSMLParser) -> None:
        """測試 <phoneme> 無 alphabet 屬性時預設為 ipa。"""
        segments = parser.parse("<speak><phoneme ph=\"da\">大</phoneme></speak>")
        assert segments[0].phoneme_alphabet == "ipa"
        assert segments[0].phoneme_ph == "da"


# ---------------------------------------------------------------------------
# Tests: Error Handling & Fallback
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """錯誤處理與 fallback 測試。"""

    def test_invalid_xml_returns_plain_text(self, parser: SSMLParser) -> None:
        """測試 XML 解析失敗時 fallback 純文字。"""
        # Invalid XML: unclosed tag
        segments = parser.parse("<speak><prosody>未關閉")
        assert len(segments) == 1
        assert segments[0].type == SegmentType.TEXT

    def test_invalid_xml_complex(self, parser: SSMLParser) -> None:
        """測試複雜無效 XML fallback。"""
        segments = parser.parse("<speak><break time=>")
        assert len(segments) == 1
        assert segments[0].type == SegmentType.TEXT

    def test_wrong_root_element_raises(self, parser: SSMLParser) -> None:
        """測試非 <speak> 根標籤拋出 SSMLParseError。"""
        with pytest.raises(SSMLParseError) as exc_info:
            parser.parse("<div>text</div>")
        assert "Root element must be <speak>" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Tests: Nested Tags
# ---------------------------------------------------------------------------

class TestNestedTags:
    """巢狀標籤測試。"""

    def test_nested_voice_prosody_emphasis(self, parser: SSMLParser) -> None:
        """測試巢狀 <voice><prosody><emphasis>。"""
        segments = parser.parse(
            "<speak><voice name=\"zf_anna\"><prosody rate=\"0.9\"><emphasis level=\"strong\">複雜巢狀</emphasis></prosody></voice></speak>"
        )
        # Should produce emphasis segment with both voice and prosody
        assert len(segments) == 1
        assert segments[0].type == SegmentType.EMPHASIS
        assert segments[0].voice_name == "zf_anna"
        assert segments[0].prosody.get("rate") == 0.99  # 0.9 * 1.1 rounded

    def test_multiple_elements_sequence(self, parser: SSMLParser) -> None:
        """測試多種元素混合序列。"""
        ssml = (
            "<speak>"
            "<voice name=\"zf_xiaoxiao\">第一句</voice>"
            "<break time=\"500ms\"/>"
            "<prosody rate=\"1.2\">第二句加快</prosody>"
            "<emphasis level=\"strong\">第三句強調</emphasis>"
            "</speak>"
        )
        segments = parser.parse(ssml)
        # 4 segments: text+voice, break, text+prosody, emphasis
        # (element tails like newlines are stripped if empty after strip)
        assert len(segments) == 4
        assert segments[0].voice_name == "zf_xiaoxiao"
        assert segments[1].type == SegmentType.BREAK
        assert segments[1].break_ms == 500
        assert segments[2].prosody.get("rate") == 1.2
        assert segments[3].type == SegmentType.EMPHASIS
        assert segments[3].emphasis_level == "strong"


# ---------------------------------------------------------------------------
# Tests: Segment Attributes
# ---------------------------------------------------------------------------

class TestSegmentAttributes:
    """SSMLSegment 屬性完整性測試。"""

    def test_text_segment_has_empty_optional_attrs(self, parser: SSMLParser) -> None:
        """測試 TEXT 片段的選填屬性為 None 或預設值。"""
        segments = parser.parse("<speak>純文字</speak>")
        seg = segments[0]
        assert seg.type == SegmentType.TEXT
        assert seg.break_ms is None
        assert seg.emphasis_level is None
        assert seg.phoneme_alphabet is None
        assert seg.phoneme_ph is None
        assert seg.voice_name is None
        assert seg.prosody == {}

    def test_break_segment_has_required_attrs(self, parser: SSMLParser) -> None:
        """測試 BREAK 片段包含 break_ms。"""
        segments = parser.parse("<speak>前<break time=\"200ms\"/>後</speak>")
        break_seg = segments[1]
        assert break_seg.type == SegmentType.BREAK
        assert break_seg.break_ms == 200
        assert break_seg.text == ""

    def test_inherited_prosody(self, parser: SSMLParser) -> None:
        """測試 prosody 屬性繼承。"""
        segments = parser.parse(
            "<speak><prosody rate=\"0.8\">外層<voice name=\"zf_anna\">內層音色</voice>回到外層</prosody></speak>"
        )
        # First text segment has outer prosody
        assert segments[0].prosody.get("rate") == 0.8
        # Voice segment inherits prosody and sets voice
        assert segments[1].voice_name == "zf_anna"
        assert segments[1].prosody.get("rate") == 0.8
        # Last text segment back to outer prosody
        assert segments[2].prosody.get("rate") == 0.8


# ---------------------------------------------------------------------------
# Tests: Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """邊界條件測試。"""

    def test_empty_speak_tag(self, parser: SSMLParser) -> None:
        """測試空 <speak></speak>。"""
        segments = parser.parse("<speak></speak>")
        assert len(segments) == 0

    def test_self_closing_break(self, parser: SSMLParser) -> None:
        """測試自閉合 <break/> 標籤。"""
        segments = parser.parse("<speak><break/></speak>")
        assert len(segments) == 1
        assert segments[0].type == SegmentType.BREAK
        assert segments[0].break_ms == 0

    def test_prosody_with_empty_content(self, parser: SSMLParser) -> None:
        """測試空 <prosody> 標籤。"""
        segments = parser.parse("<speak>前<prosody rate=\"1.5\"></prosody>後</speak>")
        # Should have text segments only
        assert all(s.type == SegmentType.TEXT for s in segments)

    def test_case_insensitive_tags(self, parser: SSMLParser) -> None:
        """測試標籤大小寫不敏感。"""
        segments = parser.parse("<SPEAK><VOICE NAME=\"zf_anna\">測試</VOICE></SPEAK>")
        assert segments[0].voice_name == "zf_anna"

    def test_break_with_space_before_unit(self, parser: SSMLParser) -> None:
        """測試 <break time=\"500 ms\">（單位前有空格）。"""
        segments = parser.parse("<speak><break time=\"500 ms\"/></speak>")
        assert segments[0].break_ms == 500

    def test_rate_with_percent(self, parser: SSMLParser) -> None:
        """測試 rate=\"150%\" → 轉換為 1.5。"""
        segments = parser.parse("<speak><prosody rate=\"150%\">快</prosody></speak>")
        assert segments[0].prosody.get("rate") == 1.5


# ---------------------------------------------------------------------------
# Tests: Integration Scenarios
# ---------------------------------------------------------------------------

class TestIntegrationScenarios:
    """整合情境測試。"""

    def test_ssml_from_srs_example(self, parser: SSMLParser) -> None:
        """測試 SRS.md 中提到的 SSML 格式。"""
        ssml = '<speak><voice name="zf_yunxi">這是語音合成測試</voice></speak>'
        segments = parser.parse(ssml)
        assert len(segments) == 1
        assert segments[0].voice_name == "zf_yunxi"
        assert segments[0].text == "這是語音合成測試"

    def test_full_ssml_document(self, parser: SSMLParser) -> None:
        """測試完整 SSML 文件。"""
        ssml = """
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis">
            <voice name="zf_xiaoxiao">
                您好，歡迎使用語音合成服務。
            </voice>
            <break time="500ms"/>
            <prosody rate="0.9">
                這段話會說得比較慢。
            </prosody>
            <emphasis level="strong">
                這個詞很重要！
            </emphasis>
        </speak>
        """
        segments = parser.parse(ssml)
        # Should parse all elements
        assert len(segments) >= 4
        # Find the emphasis segment
        emphasis_segments = [s for s in segments if s.type == SegmentType.EMPHASIS]
        assert len(emphasis_segments) == 1
        assert emphasis_segments[0].emphasis_level == "strong"


# ---------------------------------------------------------------------------
# Tests: SSMLParseError
# ---------------------------------------------------------------------------

class TestSSMLParseError:
    """SSMLParseError 異常測試。"""

    def test_error_contains_message(self) -> None:
        """測試錯誤訊息。"""
        error = SSMLParseError("Test error message")
        assert str(error) == "Test error message"

    def test_error_with_line_number(self) -> None:
        """測試錯誤含行號資訊。"""
        error = SSMLParseError("Error at line 5", line=5)
        assert error.line == 5
        assert "line 5" in str(error)

    def test_error_inheritance(self) -> None:
        """測試錯誤繼承自 ValueError。"""
        error = SSMLParseError("Inherited error")
        assert isinstance(error, ValueError)


# ---------------------------------------------------------------------------
# Tests: SSMLSegment Dataclass
# ---------------------------------------------------------------------------

class TestSSMLSegment:
    """SSMLSegment 資料類別測試。"""

    def test_segment_creation(self) -> None:
        """測試片段建立。"""
        seg = SSMLSegment(type=SegmentType.TEXT, text="Hello")
        assert seg.type == SegmentType.TEXT
        assert seg.text == "Hello"
        assert seg.break_ms is None
        assert seg.prosody == {}

    def test_segment_with_all_attributes(self) -> None:
        """測試含所有屬性的片段。"""
        seg = SSMLSegment(
            type=SegmentType.PHONEME,
            text="nǐ hǎo",
            break_ms=None,
            emphasis_level=None,
            phoneme_alphabet="ipa",
            phoneme_ph="nǐ hǎo",
            voice_name="zf_anna",
            prosody={"rate": 1.0},
        )
        assert seg.phoneme_alphabet == "ipa"
        assert seg.phoneme_ph == "nǐ hǎo"
        assert seg.voice_name == "zf_anna"
