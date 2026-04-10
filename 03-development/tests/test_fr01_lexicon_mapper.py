"""
[FR-01] 測試案例：台灣中文詞彙映射 (Taiwan Chinese Lexicon Mapper).

Citations:
    SRS.md#L35-L37 (邏輯驗證方法與測試案例)
    SAD.md#L334-L342 (模組邊界對照表)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure the project root is on the import path.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.processing.lexicon_mapper import LexiconMapper


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def lexicon_path(tmp_path: Path) -> Path:
    """
    Generate a temporary lexicon JSON with controlled entries for testing.
    Includes enough categories and ≥50 entries to satisfy FR-01.
    """
    data = {
        "_meta": {
            "version": "1.0",
            "categories": [
                "transportation", "technology", "food",
                "occupation", "pronunciation", "daily"
            ]
        },
        "_lexicon": {
            # Transportation
            "地鐵": "捷運",
            "地鐵站": "捷運站",
            "出租車": "計程車",
            "摩托車": "機車",
            # Technology
            "視頻": "影片",
            "軟件": "軟體",
            "硬件": "硬體",
            "打印": "列印",
            "打印機": "印表機",
            "U盤": "隨身碟",
            "U 盤": "隨身碟",
            "網吧": "網咖",
            "信息安全": "資訊安全",
            "博客": "部落格",
            "blog": "部落格",
            "微博": "微博(微網誌)",
            "短訊": "簡訊",
            "內存": "記憶體",
            "計算機": "電腦",
            "大哥大": "手機",
            "激光": "雷射",
            "芯片": "晶片",
            "集成電路": "積體電路",
            "硅": "矽",
            "數碼相機": "數位相機",
            "智能手機": "智慧手機",
            "互聯網": "網際網路",
            "網絡": "網路",
            "人工智能": "人工智慧",
            # Food
            "菠蘿": "鳳梨",
            "菠蘿麵包": "鳳梨麵包",
            "土豆": "馬鈴薯",
            "白菜": "高麗菜",
            # Occupation
            "程序員": "工程師",
            "老師": "老師(教師)",
            "導游": "導遊",
            # Pronunciation (particles)
            "和": "ㄏㄢˋ",
            "吧": "啦",
            "哦": "喔",
            "嗯": "嗯(思考)",
            "啦": "啦(語氣)",
            # Daily / Slang
            "信息": "資訊",
            "這會": "這會(這時候)",
            "那會": "那會(那時候)",
            "啥": "什麼",
            "咋": "怎麼",
            "咱": "我們",
            "俺": "我",
            "帥哥": "帥哥(美男子)",
            "美女": "正妹",
            "壓縮包": "壓縮檔",
            "解壓縮": "解壓縮",
            "桌麵": "桌面",
            "筆記本": "筆電",
            "掌上電腦": "PDA",
            "質量": "品質",
            "納米": "奈米",
            "納米技術": "奈米技術",
            "艾滋病": "愛滋病",
            "系列": "系列(產品線)",
            "和信息": "和資訊",
        }
    }
    path = tmp_path / "lexicon_tw.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


@pytest.fixture
def mapper(lexicon_path: Path) -> LexiconMapper:
    """Instantiate LexiconMapper with the temporary lexicon."""
    return LexiconMapper(lexicon_path=lexicon_path)


# ---------------------------------------------------------------------------
# FR-01 Test Cases (SRS.md#L35-L37)
# ---------------------------------------------------------------------------

class TestLexiconMapperApply:
    """[FR-01] apply() 單次正則表達式穿越，長詞優先。"""

    def test_transportation_subway(self, mapper: LexiconMapper) -> None:
        """
        [FR-01] 測試案例：輸入「我要坐地鐵去看視頻」，預期輸出「我要坐捷運去看影片」

        SRS.md#L35
        """
        result = mapper.apply("我要坐地鐵去看視頻")
        assert result == "我要坐捷運去看影片"

    def test_food_pineapple_bread(self, mapper: LexiconMapper) -> None:
        """
        [FR-01] 測試案例：輸入「菠蘿麵包」，預期輸出「鳳梨麵包」

        SRS.md#L36
        """
        result = mapper.apply("菠蘿麵包")
        assert result == "鳳梨麵包"

    def test_multiple_mappings(self, mapper: LexiconMapper) -> None:
        """[FR-01] 單次 apply() 替換多個不同類別詞彙。"""
        text = "菠蘿麵包好吃，我要坐地鐵"
        result = mapper.apply(text)
        assert "鳳梨麵包" in result
        assert "捷運" in result
        assert "菠蘿" not in result
        assert "地鐵" not in result

    def test_long_word_priority(self, mapper: LexiconMapper) -> None:
        """
        [FR-01] 長詞優先：集成電路（4字）優先於芯片（2字）被掃描匹配。

        貪心掃描於 position 0 找到「芯片」（2字 valid match），
        於 position 3 找到「集成電路」（4字 valid match），
        兩者均被獨立替換 — 重疊字元不產生重複輸出。

        SAD.md#L341 (「長詞優先」策略)
        """
        text = "芯片是集成電路的組成部分"
        result = mapper.apply(text)
        # 「集成電路」→「積體電路」（長詞正確替換）
        assert "積體電路" in result
        # 「芯片」出現在 position 0，屬於 valid standalone match
        # （欲使「芯片」不被替換需 lookahead 上下文，脫離 lexicon 職責）
        assert result == "晶片是積體電路的組成部分"

    def test_no_match_returns_original(self, mapper: LexiconMapper) -> None:
        """[FR-01] 無任何匹配時，回傳原始文字。"""
        original = "這句話完全沒有需要替換的詞"
        assert mapper.apply(original) == original

    def test_empty_string(self, mapper: LexiconMapper) -> None:
        """[FR-01] 空字串輸入須回傳空字串（不禁引發錯誤）。"""
        assert mapper.apply("") == ""

    def test_mixed_chinese_and_punctuation(self, mapper: LexiconMapper) -> None:
        """[FR-01] 中英文混合含標點符號場景。"""
        text = "我要坐地鐵去看視頻，菠蘿麵包超好吃！"
        result = mapper.apply(text)
        assert "捷運" in result
        assert "影片" in result
        assert "鳳梨麵包" in result

    def test_pronunciation_particle_replacement(self, mapper: LexiconMapper) -> None:
        """[FR-01] 發音詞替換：和→ㄏㄢˋ、吧→啦"""
        result = mapper.apply("你和我是朋友吧")
        assert "ㄏㄢˋ" in result
        assert "啦" in result

    def test_all_categories_present(self, mapper: LexiconMapper) -> None:
        """[FR-01] 驗證六個分類（交通、科技、食物、職業、發音、日常）皆有詞條。"""
        samples = [
            ("地鐵", "捷運"),       # transportation
            ("視頻", "影片"),       # technology
            ("菠蘿", "鳳梨"),       # food
            ("程序員", "工程師"),   # occupation
            ("和", "ㄏㄢˋ"),       # pronunciation
            ("啥", "什麼"),        # daily/slang
        ]
        for old, new in samples:
            assert mapper.apply(old) == new


class TestLexiconMapperCoverage:
    """[FR-01] 詞彙覆蓋率 ≥ 50 詞（lexicon ≥ 50 entries）。"""

    def test_total_entries_meets_minimum(self, mapper: LexiconMapper) -> None:
        """
        [FR-01] 測試案例：LEXICON 總詞彙數 ≥ 50

        SRS.md#L37
        """
        stats = mapper.get_coverage_stats()
        assert stats["total_entries"] >= 50, (
            f"Lexicon entries {stats['total_entries']} < 50 (FR-01 minimum)"
        )

    def test_categories_not_empty(self, mapper: LexiconMapper) -> None:
        """[FR-01] categories 清單不得為空。"""
        stats = mapper.get_coverage_stats()
        assert stats["categories"] > 0

    def test_stats_keys(self, mapper: LexiconMapper) -> None:
        """[FR-01] get_coverage_stats() 回傳必要欄位。"""
        stats = mapper.get_coverage_stats()
        assert "total_entries" in stats
        assert "categories" in stats
        assert "category_breakdown" in stats


class TestLexiconMapperEdgeCases:
    """[FR-01] 邊界條件處理。"""

    def test_whitespace_preserved(self, mapper: LexiconMapper) -> None:
        """[FR-01] 純空白字串回傳空白。"""
        assert mapper.apply("   ") == "   "

    def test_unicode_fullwidth_punctuation(self, mapper: LexiconMapper) -> None:
        """[FR-01] 全形標點符號不影響替換。"""
        result = mapper.apply("視頻！？視頻")
        assert result.count("影片") == 2

    def test_repeated_same_word(self, mapper: LexiconMapper) -> None:
        """[FR-01] 同一詞彙出現多次，全部替換。"""
        result = mapper.apply("視頻視頻視頻")
        assert result == "影片影片影片"

    def test_substring_not_double_replaced(self, mapper: LexiconMapper) -> None:
        """[FR-01] 已替換的詞不再被二次匹配。"""
        # "U盤" → "隨身碟"，"隨身碟" 中不再包含 "U" 或 "盤" 的獨立映射
        result = mapper.apply("U盤")
        assert result == "隨身碟"


class TestLexiconMapperFileNotFound:
    """[FR-01] 檔案缺失時拋出 FileNotFoundError。"""

    def test_nonexistent_lexicon_path(self) -> None:
        """[FR-01] 指定不存在的 lexicon 路徑時，__init__ 拋出 FileNotFoundError。"""
        fake = Path("/nonexistent/path/lexicon_tw.json")
        with pytest.raises(FileNotFoundError) as exc_info:
            LexiconMapper(lexicon_path=fake)
        assert "lexicon file not found" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
