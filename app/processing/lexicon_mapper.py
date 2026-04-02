"""
Taiwan Lexicon Mapper — FR-01 台灣中文詞彙映射

對應 methodology-v2 規範：
- SKILL.md - Core Modules
- SKILL.md - Error Handling (L1-L6)
- SRS.md FR-01

邏輯約束：
- 詞典在首次 apply() 才載入（Lazy Init）
- 單次正則穿越，長詞優先匹配
- L1 錯誤處理：输入验证失败立即返回错误
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional


class LexiconMapperError(Exception):
    """L1 錯誤：詞彙映射相關錯誤（輸入/檔案/JSON格式）"""
    pass


class LexiconMapper:
    """
    台灣中文詞彙映射器

    在文本傳入 TTS 引擎前，進行台灣特有詞彙與發音的 LEXICON 映射。
    支援科技詞、交通詞、食物詞、發音詞、職業詞、稱謂等類別。

    邏輯約束（對應 FR-01）：
    - 詞典在首次 apply() 才載入（Lazy Init）
    - 單次正則穿越，長詞優先匹配
    - L1 錯誤處理：輸入驗證失敗立即返回錯誤

    Example:
        >>> mapper = LexiconMapper()
        >>> mapper.apply("我要坐地鐵去看視頻")
        '我要坐捷運去看影片'
    """

    # L1: 預設詞典路徑
    DEFAULT_LEXICON_PATH = Path(__file__).parent.parent / "data" / "lexicon_tw.json"

    def __init__(self, lexicon_path: Optional[str | Path] = None) -> None:
        """
        初始化 LexiconMapper

        Args:
            lexicon_path: 可選，自訂詞典路徑。預設使用 app/data/lexicon_tw.json

        Raises:
            LexiconMapperError: L1 - 路徑無效（非檔案）
        """
        self._lexicon_path: Optional[Path] = Path(lexicon_path) if lexicon_path else self.DEFAULT_LEXICON_PATH
        self._lexicon: list[dict[str, str]] = []
        self._patterns: Optional[re.Pattern] = None  # 快取正則
        self._loaded: bool = False

        # L1: 路徑存在性預檢（僅檢查類型，不觸發檔案讀取）
        # 實際讀取延遲到 apply() — 符合 Lazy Init 規範
        if self._lexicon_path is not None and not self._lexicon_path.is_file():
            raise LexiconMapperError(f"L1-001: 詞典檔案不存在或非檔案: {self._lexicon_path}")

    # -------------------------------------------------------------------------
    # Lazy Init
    # -------------------------------------------------------------------------

    def _load_lexicon(self) -> None:
        """Lazy Init：詞典在首次 apply() 才載入"""
        if self._loaded:
            return

        if self._lexicon_path is None:
            raise LexiconMapperError("L1-002: 詞典路徑未設定")

        try:
            with open(self._lexicon_path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError as e:
            raise LexiconMapperError(f"L1-003: 詞典檔案讀取失敗: {e}") from e
        except json.JSONDecodeError as e:
            raise LexiconMapperError(f"L1-004: 詞典 JSON 格式錯誤: {e}") from e

        lexicon_tw = data.get("lexicon_tw")
        if not isinstance(lexicon_tw, list):
            raise LexiconMapperError("L1-005: 詞典 JSON 根節點必須為 list")

        self._lexicon = lexicon_tw
        self._build_pattern()
        self._loaded = True

    def _build_pattern(self) -> None:
        """建構單次正則：長詞優先匹配（依 from 字串長度降序排列）

        策略：
        1. 按 from 長度降序排列 → re alternation 會依序嘗試，長詞先匹配
        2. 單字符詞彙（len=1）：plain escaped pattern，替換所有出現
           （無法準確判斷邊界，故全部替換 — 代價是「和」在「你和」中也被替換）
        3. 多字符詞彙（len≥2）：plain escaped pattern，callback 精確比對
        4. callback 內再做精確匹配確保替換正確
        """
        # 按 from 字串長度降序排列，確保長詞優先匹配
        sorted_lexicon = sorted(self._lexicon, key=lambda x: len(x.get("from", "")), reverse=True)

        froms = [re.escape(item["from"]) for item in sorted_lexicon if item.get("from")]
        if not froms:
            self._patterns = None
            return

        combined = "|".join(froms)
        self._patterns = re.compile(combined)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def apply(self, text: str) -> str:
        """
        對輸入文本應用詞彙映射

        Args:
            text: 輸入文本

        Returns:
            映射後的文本

        Raises:
            LexiconMapperError: L1 - 輸入驗證失敗或詞典載入失敗

        Example:
            >>> mapper = LexiconMapper()
            >>> mapper.apply("我要坐地鐵去看視頻")
            '我要坐捷運去看影片'
        """
        # L1: 輸入驗證
        if not isinstance(text, str):
            raise LexiconMapperError("L1-006: 輸入必須為 str 類型")
        if text == "":
            return text  # 空字串直接返回，不算錯誤

        # Lazy Init
        if not self._loaded:
            self._load_lexicon()

        # 無詞典時直接返回原文
        if not self._patterns or not self._lexicon:
            return text

        # 建立 from→to 查找表（按長度排序供 callback 比對）
        sorted_lexicon = sorted(self._lexicon, key=lambda x: len(x.get("from", "")), reverse=True)
        from_to_pairs = [(item["from"], item["to"]) for item in sorted_lexicon]

        def replace_match(match: re.Match) -> str:
            """單次正則穿越的 callback：長詞優先匹配"""
            matched_text = match.group(0)
            # 去除 boundary 判斷用的脫逸，只取原本的 from 字串比對
            for from_str, to_str in from_to_pairs:
                # matched_text 應該等於 from_str（因正則已擋掉非獨立詞）
                if matched_text == from_str:
                    return to_str
            return matched_text  # 不應發生

        return self._patterns.sub(replace_match, text)

    @property
    def lexicon_size(self) -> int:
        """回傳詞典詞彙數量（未載入時回傳 0，不觸發 lazy load）"""
        if not self._loaded:
            return 0
        return len(self._lexicon)

    def reload(self, lexicon_path: Optional[str | Path] = None) -> None:
        """
        重新載入詞典（支援動態更新詞典）

        Args:
            lexicon_path: 可選，新的詞典路徑
        """
        self._lexicon = []
        self._patterns = None
        self._loaded = False

        if lexicon_path is not None:
            self._lexicon_path = Path(lexicon_path)
            if not self._lexicon_path.is_file():
                raise LexiconMapperError(f"L1-007: 詞典檔案不存在: {self._lexicon_path}")

        self._load_lexicon()

    def reset(self) -> None:
        """重置 Lazy Init 狀態（釋放記憶體）"""
        self._lexicon = []
        self._patterns = None
        self._loaded = False
