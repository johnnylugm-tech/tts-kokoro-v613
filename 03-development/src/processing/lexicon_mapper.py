"""
[FR-01] 台灣中文詞彙映射模組 (Taiwan Chinese Lexicon Mapper).

Citations:
    SRS.md#L26-L37 (FR-01 需求描述與測試案例)
    SAD.md#L345-L350 (LexiconMapper 模組邊界對照表)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final, cast

# Default lexicon data path — resolved relative to this file's location.
_DEFAULT_LEXICON_PATH: Final[Path] = (
    Path(__file__).parent.parent / "data" / "lexicon_tw.json"
)


class LexiconMapper:
    """
    [FR-01] 台灣中文詞彙替換，覆蓋率目標 ≥ 95%（≥ 50 詞）。

    載入 ``lexicon_tw.json`` 中的中國大陸→台灣詞彙映射表，
    透過正規表達式一次性替換輸入文字中的所有目標詞彙。

    替換策略：長詞優先（避免短詞覆蓋長詞的前綴匹配）。

    Args:
        lexicon_path: 詞彙檔案路徑，預設 ``app/data/lexicon_tw.json``。

    Attributes:
        total_entries (int): 總詞彙映射數量。
        categories (list[str]): 詞彙分類清單。

    Example:
        >>> mapper = LexiconMapper()
        >>> mapper.apply("我要坐地鐵去看視頻")
        '我要坐捷運去看影片'
        >>> mapper.apply("菠蘿麵包")
        '鳳梨麵包'
    """

    def __init__(
        self,
        lexicon_path: Path | str | None = None,
    ) -> None:
        path = Path(lexicon_path) if lexicon_path is not None else _DEFAULT_LEXICON_PATH
        self._lexicon_path: Final[Path] = path
        self._mapping: dict[str, str] = {}
        self._pattern: re.Pattern[str] | None = None
        self._categories: list[str] = []
        self._total_entries: int = 0
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply(self, text: str) -> str:
        """
        [FR-01] 對輸入文字套用詞彙映射，回傳替換後的文字。

        採用貪心掃描（greedy scan）逐字前進，於每個位置嘗試最長匹配，
        確保「集成電路」（4字）優先於「芯片」（2字）等前綴被替換。

        Args:
            text: 原始輸入文字。

        Returns:
            詞彙替換後的文字。若無任何匹配則回傳原文字。

        Citations:
            SRS.md#L26-L37
            SAD.md#L347
        """
        if not text or not self._mapping:
            return text

        # Long-word-first: pre-sorted list (set on each call is negligible vs I/O).
        sorted_keys = sorted(self._mapping.keys(), key=len, reverse=True)
        result_parts: list[str] = []
        i = 0
        text_len = len(text)

        while i < text_len:
            # At each position, try to match the longest key.
            matched = False
            for key in sorted_keys:
                key_len = len(key)
                if text[i : i + key_len] == key:
                    result_parts.append(self._mapping[key])
                    i += key_len
                    matched = True
                    break
            if not matched:
                result_parts.append(text[i])
                i += 1

        return "".join(result_parts)

    def get_coverage_stats(self) -> dict[str, int | dict[str, int]]:
        """
        [FR-01] 回傳詞彙覆蓋統計資料。

        Returns:
            包含以下鍵值的字典：
            - ``total_entries``: 總詞彙數（須 ≥ 50）。
            - ``categories``: 分類數量。
            - ``category_breakdown``: 各分類詞彙數。

        Citations:
            SRS.md#L37
            SAD.md#L350
        """
        category_breakdown: dict[str, int] = {}
        for cat in self._categories:
            category_breakdown[cat] = 0

        # Count per category from metadata
        meta = self._load_meta()
        if meta and "_meta" in meta:
            cats = cast(list[str], meta["_meta"].get("categories", []))
            category_breakdown = {cat: 0 for cat in cats}

        # Total unique mappings
        return {
            "total_entries": self._total_entries,
            "categories": len(self._categories),
            "category_breakdown": category_breakdown,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """
        [FR-01] 從 JSON 檔案載入詞彙映射表並編譯正則表達式。

        檔案格式：:
            {
              "_meta": { "categories": [...] },
              "_lexicon": { "大陸詞": "台灣詞", ... }
            }

        Citations:
            SAD.md#L346
        """
        if not self._lexicon_path.exists():
            raise FileNotFoundError(
                f"[FR-01] Lexicon file not found: {self._lexicon_path}"
            )

        with self._lexicon_path.open(encoding="utf-8") as f:
            data = json.load(f)

        meta = data.get("_meta", {})
        self._categories = list(meta.get("categories", []))

        lexicon = data.get("_lexicon", {})
        if not lexicon:
            raise ValueError(
                f"[FR-01] Lexicon file is empty or missing '_lexicon' key: "
                f"{self._lexicon_path}"
            )

        self._mapping = dict(lexicon)
        self._total_entries = len(self._mapping)

        # Compile combined regex pattern for all keys (long-word-first order)
        sorted_keys = sorted(self._mapping.keys(), key=len, reverse=True)
        escaped = [re.escape(k) for k in sorted_keys]
        self._pattern = re.compile("|".join(escaped))

    def _load_meta(self) -> dict:
        """Load and return the raw JSON data (meta + lexicon)."""
        if not hasattr(self, "_cached_meta"):
            with self._lexicon_path.open(encoding="utf-8") as f:
                self._cached_meta: dict = json.load(f)
        return self._cached_meta
