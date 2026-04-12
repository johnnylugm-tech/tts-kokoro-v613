"""[FR-02] SSML Parser — 解析 SSML 標籤並映射為 Kokoro API 參數。

支援標籤：
- <speak>: 根元素
- <break time="500ms"/>: 插入停頓
- <prosody rate="0.9">: 映射 speed
- <emphasis level="strong">: speed ×1.1
- <voice name="xxx">: 音色切換
- <phoneme alphabet="ipa" ph="...">: 保留原生

Citations:
    SRS.md#L41 (FR-02 需求描述)
    SAD.md#L301 (SSMLParser — FR-02 介面規格)
"""

from __future__ import annotations

import re
import defusedxml
import defusedxml.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class SegmentType(str, Enum):
    """SSML 段落類型。"""
    TEXT = "text"
    BREAK = "break"
    EMPHASIS = "emphasis"
    PHONEME = "phoneme"


@dataclass
class SSMLSegment:
    """[FR-02] 單一 SSML 段落。

    Attributes:
        type: 段落類型 (TEXT/BREAK/EMPHASIS/PHONEME)
        text: 文字內容（BREAK 段落可為空字串）
        break_ms: 停頓毫秒數（BREAK 類型時有值）
        emphasis_level: 強調等級（strong/moderate/reduced/none）
        phoneme_alphabet: 音標系統（ipa）
        phoneme_ph: IPA 音標內容
        voice_name: 音色名稱（来自 <voice name="xxx">）
        prosody: prosody 屬性 dict，keys 為 rate/rate_factor/emphasis_level
    """
    type: SegmentType
    text: str
    break_ms: Optional[int] = None
    emphasis_level: Optional[str] = None
    phoneme_alphabet: Optional[str] = None
    phoneme_ph: Optional[str] = None
    voice_name: Optional[str] = None
    prosody: dict = field(default_factory=dict)


class SSMLParseError(ValueError):
    """[FR-02] SSML 解析失敗時拋出（L1）。"""

    pass


_SUPPORTED_TAGS = {"speak", "break", "prosody", "emphasis", "voice", "phoneme"}


class SSMLParser:
    """[FR-02] 解析 SSML 標記。

    支援 <speak>, <break>, <prosody>, <emphasis>, <voice>, <phoneme>。
    無 <speak> 根標籤時自動包裝為純文字段落。

    Citations:
        SRS.md#L41
        SAD.md#L322
    """

    _BREAK_TIME_RE = re.compile(
        r"^(?P<value>\d+(?:\.\d+)?)(?P<unit>ms|s)$"
    )
    _RATE_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)$")

    def parse(self, text: str) -> list[SSMLSegment]:
        """[FR-02] 解析 SSML 字串為段落列表。

        Args:
            text: SSML 或純文字輸入

        Returns:
            list[SSMLSegment]: 解析後的段落列表

        Raises:
            SSMLParseError: XML 解析失敗時（L1）

        Citations:
            SRS.md#L41 (XML 解析失敗時 fallback 純文字)
            SAD.md#L325
        """
        text = text.strip()
        if not text:
            return []

        try:
            root = ET.fromstring(f"<speak>{text}</speak>")
        except ET.ParseError:
            # [FR-02] Fallback: XML 解析失敗時 fallback 純文字
            return [SSMLSegment(type=SegmentType.TEXT, text=text)]

        return self._parse_element(root, inherited_prosody={})

    def _parse_element(
        self,
        element: ET.Element,
        inherited_prosody: dict,
    ) -> list[SSMLSegment]:
        """[FR-02] 遞迴解析單一 XML 元素。

        Handles mixed content (element.text + child elements + child.tail)
        correctly by capturing text before the first child, each child's
        results, and the tail after each child.

        Args:
            element: XML 元素
            inherited_prosody: 從父元素繼承的 prosody 屬性

        Returns:
            list[SSMLSegment]: 解析後的段落列表

        Citations:
            SAD.md#L328
        """
        tag = element.tag.lower()

        # Unknown tag: skip element but process children
        if tag not in _SUPPORTED_TAGS:
            return self._parse_unknown_tag(element, inherited_prosody)

        # Dispatch to tag-specific handler
        handlers: dict[str, Callable] = {
            "speak": self._handle_speak_tag,
            "break": self._handle_break_tag,
            "prosody": self._handle_prosody_tag,
            "emphasis": self._handle_emphasis_tag,
            "voice": self._handle_voice_tag,
            "phoneme": self._handle_phoneme_tag,
        }
        handler = handlers.get(tag)
        if handler:
            return handler(element, inherited_prosody)

        # Should not reach here — all supported tags are handled above
        return []

    def _parse_unknown_tag(
        self, element: ET.Element, inherited_prosody: dict
    ) -> list[SSMLSegment]:
        """Handle unknown tags by processing children only."""
        results: list[SSMLSegment] = []
        for child in element:
            results.extend(self._parse_element(child, inherited_prosody))
            if child.tail:
                results.append(
                    SSMLSegment(
                        type=SegmentType.TEXT,
                        text=child.tail,
                        prosody=inherited_prosody.copy(),
                    )
                )
        return results

    def _handle_speak_tag(
        self, element: ET.Element, inherited_prosody: dict
    ) -> list[SSMLSegment]:
        """Handle <speak> tag."""
        results: list[SSMLSegment] = []
        if element.text:
            results.append(
                SSMLSegment(type=SegmentType.TEXT, text=element.text, prosody={})
            )
        for child in element:
            results.extend(self._parse_element(child, {}))
            if child.tail:
                results.append(
                    SSMLSegment(type=SegmentType.TEXT, text=child.tail, prosody={})
                )
        return results

    def _handle_break_tag(
        self, element: ET.Element, inherited_prosody: dict
    ) -> list[SSMLSegment]:
        """Handle <break> tag."""
        break_ms = self._normalize_break(element.get("time", ""))
        return [
            SSMLSegment(
                type=SegmentType.BREAK,
                text="",
                break_ms=break_ms,
                prosody=inherited_prosody.copy(),
            )
        ]

    def _handle_prosody_tag(
        self, element: ET.Element, inherited_prosody: dict
    ) -> list[SSMLSegment]:
        """Handle <prosody> tag."""
        prosody = inherited_prosody.copy()
        rate_str = element.get("rate", "")
        if rate_str:
            rate_val = self._normalize_rate(rate_str)
            if rate_val is not None:
                prosody["rate"] = rate_val
        return self._handle_mixed_content_element(element, prosody)

    def _handle_emphasis_tag(
        self, element: ET.Element, inherited_prosody: dict
    ) -> list[SSMLSegment]:
        """Handle <emphasis> tag."""
        level = element.get("level", "moderate")
        emphasis_prosody = inherited_prosody.copy()
        emphasis_prosody["emphasis_level"] = level
        if level == "strong":
            emphasis_prosody["rate_factor"] = 1.1
        elif level == "reduced":
            emphasis_prosody["rate_factor"] = 0.9
        return self._handle_mixed_content_element(element, emphasis_prosody)

    def _handle_voice_tag(
        self, element: ET.Element, inherited_prosody: dict
    ) -> list[SSMLSegment]:
        """Handle <voice> tag."""
        voice_name = element.get("name", "")
        results: list[SSMLSegment] = []
        if element.text:
            results.append(
                SSMLSegment(
                    type=SegmentType.TEXT,
                    text=element.text,
                    voice_name=voice_name if voice_name else None,
                    prosody=inherited_prosody.copy(),
                )
            )
        for child in element:
            child_segs = self._parse_element(child, inherited_prosody)
            for seg in child_segs:
                if voice_name:
                    seg.voice_name = voice_name
            results.extend(child_segs)
            if child.tail:
                results.append(
                    SSMLSegment(
                        type=SegmentType.TEXT,
                        text=child.tail,
                        voice_name=None,  # explicit None — not voice_name propagation
                        prosody=inherited_prosody.copy(),
                    )
                )
        return results

    def _handle_phoneme_tag(
        self, element: ET.Element, inherited_prosody: dict
    ) -> list[SSMLSegment]:
        """Handle <phoneme> tag."""
        alphabet = element.get("alphabet", "ipa")
        ph = element.get("ph", "")
        # [FR-02] <phoneme alphabet="ipa"> → 保留原生
        results: list[SSMLSegment] = []
        if element.text:
            results.append(
                SSMLSegment(
                    type=SegmentType.PHONEME,
                    text=element.text,
                    phoneme_alphabet=alphabet,
                    phoneme_ph=ph,
                    prosody=inherited_prosody.copy(),
                )
            )
        for child in element:
            results.extend(self._parse_element(child, inherited_prosody))
            if child.tail:
                results.append(
                    SSMLSegment(
                        type=SegmentType.TEXT,
                        text=child.tail,
                        prosody=inherited_prosody.copy(),
                    )
                )
        return results

    def _handle_mixed_content_element(
        self,
        element: ET.Element,
        prosody: dict,
    ) -> list[SSMLSegment]:
        """[FR-02] Helper for elements with mixed content (text + children).

        Captures: element.text → child[0].results → child[0].tail →
                  child[1].results → child[1].tail → ...

        Args:
            element: XML element (prosody/emphasis)
            prosody: prosody dict to attach to text segments

        Returns:
            list[SSMLSegment]: ordered segments for this element
        """
        results: list[SSMLSegment] = []
        if element.text:
            results.append(
                SSMLSegment(
                    type=SegmentType.TEXT,
                    text=element.text,
                    prosody=prosody.copy(),
                )
            )
        for child in element:
            results.extend(self._parse_element(child, prosody))
            if child.tail:
                results.append(
                    SSMLSegment(
                        type=SegmentType.TEXT,
                        text=child.tail,
                        prosody=prosody.copy(),
                    )
                )
        return results

    def _normalize_break(self, time_str: str) -> int:
        """[FR-02] 將 time 屬性值正規化為毫秒整數。

        Args:
            time_str: e.g. "500ms", "2s", "1.5s"

        Returns:
            int: 毫秒數，預設 500ms

        Raises:
            SSMLParseError: 格式無法解析時（L1）

        Citations:
            SRS.md#L41 (<break time="500ms"/> → 插入停頓字元)
            SAD.md#L330
        """
        if not time_str:
            return 500  # Default
        m = self._BREAK_TIME_RE.match(time_str.strip().lower())
        if not m:
            raise SSMLParseError(f"Invalid break time format: {time_str!r}")
        value = float(m.group("value"))
        unit = m.group("unit")
        if unit == "ms":
            return int(value)
        if unit == "s":
            return int(value * 1000)
        raise SSMLParseError(f"Unknown time unit: {unit}")

    def _normalize_rate(self, rate_str: str) -> Optional[float]:
        """[FR-02] 將 rate 屬性值正規化為浮點數。

        Args:
            rate_str: e.g. "0.9", "1.2", "fast", "slow"

        Returns:
            float | None: 速度倍率，或 None（無法解析時）

        Citations:
            SRS.md#L41 (<prosody rate="0.9"> → speed=0.9)
        """
        rate_str = rate_str.strip().lower()
        if rate_str == "x-slow":
            return 0.5
        if rate_str == "slow":
            return 0.8
        if rate_str == "medium":
            return 1.0
        if rate_str == "fast":
            return 1.2
        if rate_str == "x-fast":
            return 1.5
        m = self._RATE_RE.match(rate_str)
        if m:
            return float(m.group("value"))
        return None
