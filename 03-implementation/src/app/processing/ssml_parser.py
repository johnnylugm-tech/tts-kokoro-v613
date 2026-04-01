"""
SSML Parser — FR-02
SSML（Speech Synthesis Markup Language）解析器

支援：<speak>, <break>, <prosody>, <voice>, <phoneme>
"""

from dataclasses import dataclass
from typing import List, Optional
import re


@dataclass
class SSMLElement:
    """SSML 元素結構"""
    tag: str
    attrs: dict
    text: str = ""
    children: List['SSMLElement'] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class KokoroParams:
    """轉換為 Kokoro API 參數"""
    text: str
    voice: str = "zf_xiaoxiao"
    speed: float = 1.0
    pitch: float = 1.0
    break_duration: float = 0.0


class SSMLParser:
    """
    SSML 解析器
    
    將 SSML 標記文字解析為結構化物件，並轉換為 Kokoro API 參數。
    """
    
    # 支援的 SSML 標籤
    SUPPORTED_TAGS = {"speak", "break", "prosody", "voice", "phoneme", "s"}
    
    # Kokoro 支援的音色
    KOKORO_VOICES = {
        "zf_xiaoxiao",  # 中文女聲（預設）
        "zf_yunyang",   # 中文男聲
        "zf_xiaoyi",    # 中文女聲 2
    }
    
    def __init__(self, default_voice: str = "zf_xiaoxiao"):
        self.default_voice = default_voice
    
    def parse(self, ssml: str) -> SSMLElement:
        """
        解析 SSML 文字為結構化物件。
        
        Args:
            ssml: SSML 格式的文字
            
        Returns:
            SSMLElement 結構樹
        """
        # 移除 XML 宣告
        ssml = re.sub(r"<\?xml[^>]+\?>", "", ssml).strip()
        
        # 解析主要 <speak> 標籤
        speak_match = re.search(r"<speak[^>]*>(.*?)</speak>", ssml, re.DOTALL)
        if not speak_match:
            # 沒有 <speak> 標籤，直接當純文字處理
            return SSMLElement(tag="speak", attrs={}, text=ssml)
        
        content = speak_match.group(1)
        return self._parse_children(content)
    
    def _parse_children(self, content: str) -> SSMLElement:
        """遞迴解析子元素。"""
        root = SSMLElement(tag="speak", attrs={})
        remaining = content
        
        while remaining:
            # 找到下一個標籤
            tag_match = re.match(r"<(\w+)([^>]*)>(.*?)</\1>", remaining, re.DOTALL)
            if tag_match:
                tag, attrs_str, tag_content = tag_match.groups()
                
                # 解析屬性
                attrs = self._parse_attrs(attrs_str)
                
                # 遞迴解析內容
                children = []
                if tag in self.SUPPORTED_TAGS - {"break"}:
                    children = [self._parse_children(tag_content)]
                
                root.children.append(SSMLElement(
                    tag=tag,
                    attrs=attrs,
                    text=tag_content if tag not in self.SUPPORTED_TAGS else "",
                    children=children
                ))
                
                remaining = remaining[tag_match.end():]
            else:
                # 純文字
                if remaining.strip():
                    if root.children and root.children[-1].tag == "_text":
                        root.children[-1].text += remaining.strip()
                    else:
                        root.children.append(SSMLElement(
                            tag="_text",
                            attrs={},
                            text=remaining.strip()
                        ))
                break
        
        return root
    
    def _parse_attrs(self, attrs_str: str) -> dict:
        """解析標籤屬性。"""
        attrs = {}
        for match in re.finditer(r'(\w+)="([^"]*)"', attrs_str):
            attrs[match.group(1)] = match.group(2)
        return attrs
    
    def to_kokoro_params(self, ssml: str) -> List[KokoroParams]:
        """
        將 SSML 轉換為 Kokoro API 參數列表。
        
        Args:
            ssml: SSML 格式文字
            
        Returns:
            KokoroParams 列表（每個 <voice> 或段落一段）
        """
        root = self.parse(ssml)
        params = []
        current_params = KokoroParams(text="", voice=self.default_voice)
        
        for child in root.children:
            if child.tag == "_text":
                current_params.text += child.text
            elif child.tag == "voice":
                # 更換音色
                voice = child.attrs.get("name", self.default_voice)
                params.append(current_params)
                current_params = KokoroParams(text="", voice=voice)
            elif child.tag == "prosody":
                # 調整語速/音高
                speed = float(child.attrs.get("rate", "1.0").rstrip("%")) / 100
                pitch = float(child.attrs.get("pitch", "1.0").rstrip("%")) / 100
                current_params.speed = speed
                current_params.pitch = pitch
            elif child.tag == "break":
                # 添加停頓
                duration = child.attrs.get("time", "0s")
                seconds = self._parse_duration(duration)
                current_params.break_duration += seconds
        
        if current_params.text.strip():
            params.append(current_params)
        
        # 如果沒有內容，用預設參數
        if not params:
            params.append(KokoroParams(text=ssml, voice=self.default_voice))
        
        return params
    
    def _parse_duration(self, duration: str) -> float:
        """解析 duration 字串（如 '1s', '500ms'）為秒數。"""
        duration = duration.strip().lower()
        if duration.endswith("ms"):
            return float(duration[:-2]) / 1000
        elif duration.endswith("s"):
            return float(duration[:-1])
        else:
            return float(duration)


def parse_ssml(ssml: str, default_voice: str = "zf_xiaoxiao") -> SSMLElement:
    """快速解析函數。"""
    parser = SSMLParser(default_voice)
    return parser.parse(ssml)
