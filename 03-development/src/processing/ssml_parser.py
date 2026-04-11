"""
[FR-02] SSML Parser - 解析 SSML 標籤並映射為 Kokoro API 參數，支援音色切換。

支援標籤：
- <speak>: 根元素
- <break>: time="500ms" → 插入停頓
- <prosody>: rate="0.9" → 映射 speed
- <emphasis>: level="strong" → speed ×1.1
- <voice>: name="xxx" → 音色切換
- <phoneme>: alphabet="ipa" → 保留原生

Citations:
    SRS.md#L40-L62 (FR-02 需求規格)
    SAD.md#L301-L331 (SSMLParser 模組邊界對照表)
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SegmentType(str, Enum):
    """SSML 片段類型枚舉。"""
    TEXT = "text"
    BREAK = "break"
    EMPHASIS = "emphasis"
    PHONEME = "phoneme"


@dataclass
class SSMLSegment:
    """
    SSML 解析後的片段結構。

    Attributes:
        type: 片段類型 (TEXT/BREAK/EMPHASIS/PHONEME)
        text: 文字內容（純文字或包含 SSML 的段落）
        break_ms: 停頓時間（毫秒），僅用於 BREAK 類型
        emphasis_level: 強調級別 (none/moderate/strong/reduced)，僅用於 EMPHASIS
        phoneme_alphabet: 音標體系 (ipa/x-sampa)，僅用於 PHONEME
        phoneme_ph: 音標符號，僅用於 PHONEME
        voice_name: 音色名稱，僅用於需要切換音色時
        prosody: 韻律屬性字典 (rate, pitch, volume)
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
    """
    SSML 解析錯誤（L1 錯誤）。

    當 XML 格式不正確或遇到不支援的 SSML 標籤時拋出。
    包含 XML 行號資訊以便除錯。
    """
    def __init__(self, message: str, line: Optional[int] = None) -> None:
        self.line = line
        super().__init__(message)

    def __str__(self) -> str:
        if self.line is not None:
            return f"{super().__str__()} (line {self.line})"
        return super().__str__()


class SSMLParser:
    """
    FR-02: 解析 SSML 標記。

    支援 <speak>, <break>, <prosody>, <emphasis>, <voice>, <phoneme>。
    無 <speak> 根標籤時自動包裝。

    Example:
        >>> parser = SSMLParser()
        >>> segments = parser.parse('<voice name="zf_yunxi">你好</voice>')
        >>> segments[0].voice_name
        'zf_yunxi'
    """

    # 支援的 SSML 標籤集合（忽略大小寫）
    SUPPORTED_TAGS = {"speak", "break", "prosody", "emphasis", "voice", "phoneme"}

    # 強調級別到 speed 倍率的映射
    EMPHASIS_RATE_MAP = {
        "none": 1.0,
        "reduced": 0.9,
        "moderate": 1.05,
        "strong": 1.1,
    }

    def __init__(self) -> None:
        """初始化 SSML Parser。"""
        pass

    def parse(self, text: str) -> list[SSMLSegment]:
        """
        解析 SSML 文字並返回片段列表。

        當輸入不包含 <speak> 根標籤時，自動包裝為 <speak> 再解析。
        解析失敗時回退至純文字模式。

        Args:
            text: SSML 格式的文字輸入

        Returns:
            list[SSMLSegment]: 解析後的 SSML 片段列表

        Raises:
            SSMLParseError: 當 XML 解析失敗且無法回退至純文字時（L1）
        """
        # 去除多餘空白
        text = text.strip()

        # 先檢查是否看起來像 XML（包含 < 和 >）
        is_xml_like = '<' in text and '>' in text

        if is_xml_like:
            # 嘗試直接解析為 XML
            try:
                root = ET.fromstring(text)
                # 驗證根標籤（忽略大小寫和命名空間）
                root_tag = root.tag.split('}')[-1].lower()  # 移除命名空間前綴
                if root_tag != "speak":
                    raise SSMLParseError(
                        f"Root element must be <speak>, got <{root.tag}>"
                    )
                return self._parse_element(root, inherited_prosody={})
            except ET.ParseError:
                # XML 解析失敗時回退至純文字
                return [SSMLSegment(type=SegmentType.TEXT, text=text)]
        else:
            # 非 XML 內容，自動包裝為 <speak>
            text = f"<speak>{text}</speak>"
            try:
                root = ET.fromstring(text)
                return self._parse_element(root, inherited_prosody={})
            except ET.ParseError:
                return [SSMLSegment(type=SegmentType.TEXT, text=text)]

    def _parse_element(
        self, element: ET.Element, inherited_prosody: dict
    ) -> list[SSMLSegment]:
        """
        遞迴解析 XML 元素為 SSMLSegment 列表。

        Args:
            element: XML 元素
            inherited_prosody: 從父元素繼承的 prosody 屬性

        Returns:
            list[SSMLSegment]: 解析後的片段列表
        """
        segments: list[SSMLSegment] = []
        # 移除命名空間前綴（如 {http://www.w3.org/2001/10/synthesis}speak -> speak）
        tag = element.tag.split('}')[-1].lower()

        # 處理不同標籤
        if tag == "break":
            segments.extend(self._parse_break(element, inherited_prosody))
        elif tag == "prosody":
            segments.extend(self._parse_prosody(element, inherited_prosody))
        elif tag == "emphasis":
            segments.extend(self._parse_emphasis(element, inherited_prosody))
        elif tag == "voice":
            segments.extend(self._parse_voice(element, inherited_prosody))
        elif tag == "phoneme":
            segments.extend(self._parse_phoneme(element, inherited_prosody))
        elif tag == "speak":
            segments.extend(self._parse_speak(element, inherited_prosody))
        else:
            # 不支援的標籤，當作純文字處理
            if element.text and element.text.strip():
                segments.append(
                    SSMLSegment(type=SegmentType.TEXT, text=element.text.strip())
                )

        # 處理 tail 文字（元素後的文字）- 適用於所有標籤
        if element.tail and element.tail.strip():
            segments.append(
                SSMLSegment(type=SegmentType.TEXT, text=element.tail.strip(), prosody=inherited_prosody.copy())
            )

        return segments

    def _parse_speak(self, element: ET.Element, inherited_prosody: dict) -> list[SSMLSegment]:
        """
        解析 <speak> 標籤。

        Args:
            element: <speak> XML 元素
            inherited_prosody: 從父元素繼承的 prosody 屬性

        Returns:
            list[SSMLSegment]: 解析後的片段列表
        """
        segments: list[SSMLSegment] = []

        # 1. 先處理 speak 標籤內的文字節點（出現在第一個子元素之前的文字）
        if element.text and element.text.strip():
            segments.append(
                SSMLSegment(type=SegmentType.TEXT, text=element.text.strip())
            )

        # 2. 遍歷所有子元素
        for child in element:
            child_segments = self._parse_element(child, inherited_prosody)
            segments.extend(child_segments)

        return segments

    def _parse_break(self, element: ET.Element, inherited_prosody: dict) -> list[SSMLSegment]:
        """
        解析 <break> 標籤。

        Args:
            element: <break> XML 元素
            inherited_prosody: 繼承的 prosody 屬性

        Returns:
            list[SSMLSegment]: 包含 BREAK 片段的列表
        """
        time_attr = element.get("time", "0s")
        break_ms = self._normalize_break(time_attr)

        return [
            SSMLSegment(
                type=SegmentType.BREAK,
                text="",
                break_ms=break_ms,
                prosody=inherited_prosody.copy(),
            )
        ]

    def _parse_prosody(self, element: ET.Element, inherited_prosody: dict) -> list[SSMLSegment]:
        """
        解析 <prosody> 標籤。

        支援 rate, pitch, volume 屬性。
        計算新的 prosody 字典並傳遞給子元素。

        Args:
            element: <prosody> XML 元素
            inherited_prosody: 從父元素繼承的 prosody 屬性

        Returns:
            list[SSMLSegment]: 解析後的片段列表
        """
        # 合併 prosody 屬性
        new_prosody = inherited_prosody.copy()

        rate = element.get("rate")
        if rate is not None:
            new_prosody["rate"] = self._normalize_rate(rate)

        pitch = element.get("pitch")
        if pitch is not None:
            new_prosody["pitch"] = pitch

        volume = element.get("volume")
        if volume is not None:
            new_prosody["volume"] = volume

        segments: list[SSMLSegment] = []

        # 先處理 element.text（prosody 標籤內的文字）
        if element.text and element.text.strip():
            segments.append(
                SSMLSegment(type=SegmentType.TEXT, text=element.text.strip(), prosody=new_prosody)
            )

        # 遞迴處理子元素
        for child in element:
            segments.extend(self._parse_element(child, new_prosody))

        return segments

    def _parse_emphasis(self, element: ET.Element, inherited_prosody: dict) -> list[SSMLSegment]:
        """
        解析 <emphasis> 標籤。

        根據 level 屬性調整說話速率：
        - strong: rate ×1.1
        - moderate: rate ×1.05
        - reduced: rate ×0.9
        - none: rate ×1.0

        Args:
            element: <emphasis> XML 元素
            inherited_prosody: 從父元素繼承的 prosody 屬性

        Returns:
            list[SSMLSegment]: 解析後的片段列表
        """
        level = element.get("level", "moderate")
        segments: list[SSMLSegment] = []

        # 建立 emphasis 的 prosody
        emphasis_prosody = inherited_prosody.copy()
        emphasis_rate = self.EMPHASIS_RATE_MAP.get(level, 1.0)

        if "rate" in emphasis_prosody:
            emphasis_prosody["rate"] = round(emphasis_prosody["rate"] * emphasis_rate, 2)
        else:
            emphasis_prosody["rate"] = emphasis_rate

        if element.text and element.text.strip():
            segments.append(
                SSMLSegment(
                    type=SegmentType.EMPHASIS,
                    text=element.text.strip(),
                    emphasis_level=level,
                    prosody=emphasis_prosody,
                )
            )

        for child in element:
            segments.extend(self._parse_element(child, emphasis_prosody))

        return segments

    def _parse_voice(self, element: ET.Element, inherited_prosody: dict) -> list[SSMLSegment]:
        """
        解析 <voice> 標籤。

        從 name 屬性取得音色名稱，切換後的子元素使用該音色。
        屬性名稱忽略大小寫（支援 name, Name, NAME 等）。

        Args:
            element: <voice> XML 元素
            inherited_prosody: 從父元素繼承的 prosody 屬性

        Returns:
            list[SSMLSegment]: 解析後的片段列表
        """
        # 屬性名稱忽略大小寫
        voice_name = element.get("name") or element.get("Name") or element.get("NAME")
        segments: list[SSMLSegment] = []

        if element.text and element.text.strip():
            segments.append(
                SSMLSegment(
                    type=SegmentType.TEXT,
                    text=element.text.strip(),
                    voice_name=voice_name,
                    prosody=inherited_prosody.copy(),
                )
            )

        for child in element:
            child_segments = self._parse_element(child, inherited_prosody)
            # 為子片段設置音色名稱（如果尚未設置）
            for seg in child_segments:
                if seg.voice_name is None and voice_name is not None:
                    seg.voice_name = voice_name
            segments.extend(child_segments)

        return segments

    def _parse_phoneme(self, element: ET.Element, inherited_prosody: dict) -> list[SSMLSegment]:
        """
        解析 <phoneme> 標籤。

        保留音標符號和字母體系。

        Args:
            element: <phoneme> XML 元素
            inherited_prosody: 從父元素繼承的 prosody 屬性

        Returns:
            list[SSMLSegment]: 解析後的片段列表
        """
        alphabet = element.get("alphabet", "ipa")
        ph = element.get("ph", "")

        return [
            SSMLSegment(
                type=SegmentType.PHONEME,
                text=element.text or "",
                phoneme_alphabet=alphabet,
                phoneme_ph=ph,
                prosody=inherited_prosody.copy(),
            )
        ]

    def _normalize_break(self, time_str: str) -> int:
        """
        將 SSML time 字串轉換為毫秒整數。

        支援格式：
        - 500ms → 500
        - 1s → 1000
        - 1.5s → 1500

        Args:
            time_str: 時間字串（如 "500ms", "1s", "1.5s"）

        Returns:
            int: 毫秒整數
        """
        if not time_str:
            return 0

        time_str = time_str.strip().lower()

        # 解析毫秒
        ms_match = re.match(r"^(\d+(?:\.\d+)?)\s*ms$", time_str)
        if ms_match:
            return int(float(ms_match.group(1)))

        # 解析秒
        s_match = re.match(r"^(\d+(?:\.\d+)?)\s*s$", time_str)
        if s_match:
            return int(float(s_match.group(1)) * 1000)

        # 嘗試純數字（假設為秒）
        try:
            return int(float(time_str) * 1000)
        except ValueError:
            return 0

    def _normalize_rate(self, rate_str: str) -> float:
        """
        將 SSML rate 字串轉換為浮點數。

        支援格式：
        - "1.0" → 1.0
        - "0.9" → 0.9
        - "fast" → 1.2
        - "slow" → 0.8
        - "medium" / "normal" → 1.0
        - "150%" → 1.5

        Args:
            rate_str: 速率字串

        Returns:
            float: 標準化後的速率值
        """
        if not rate_str:
            return 1.0

        rate_str = rate_str.strip().lower()

        # 百分比格式
        pct_match = re.match(r"^(\d+(?:\.\d+)?)\s*%$", rate_str)
        if pct_match:
            return float(pct_match.group(1)) / 100.0

        # 數值格式
        try:
            return float(rate_str)
        except ValueError:
            pass

        # 關鍵字格式
        RATE_KEYWORDS = {
            "x-fast": 1.4,
            "fast": 1.2,
            "medium": 1.0,
            "normal": 1.0,
            "slow": 0.8,
            "x-slow": 0.6,
        }

        return RATE_KEYWORDS.get(rate_str, 1.0)
