# TEST_PLAN.md - tts-kokoro-v613

> Phase 4 測試計畫

## 測試檔案

| FR | 測試檔案 | 數量 |
|----|---------|------|
| FR-01 | test_fr01_lexicon_mapper.py | 17 tests |
| FR-02 | test_fr02_ssml_parser.py | 38 tests |
| FR-03 | test_fr03_text_chunker.py | 31 tests |
| FR-04 | test_fr04_synth_engine.py | 23 tests |
| FR-05 | test_fr05_circuit_breaker.py | 26 tests |
| FR-06 | test_fr06_redis_cache.py | 25 tests |
| FR-07 | test_fr07_routes.py | 38 tests |
| FR-08 | test_fr08_audio_converter.py | 23 tests |
| FR-09 | test_fr09_kokoro_client.py | 17 tests |

## 測試覆蓋率

- 總測試數：238
- 平均覆蓋率：92%

<!-- TEST:START -->
```json
{
  "version": "1.0",
  "created_at": "2026-04-12",
  "phase": 4,
  "project": "tts-kokoro-v613",
  "test_cases": [
    {"id": "TC-01", "type": "unit", "description": "lexicon_mapper 基本功能", "fr_coverage": ["FR-01"]},
    {"id": "TC-02", "type": "unit", "description": "ssml_parser 解析", "fr_coverage": ["FR-02"]},
    {"id": "TC-03", "type": "unit", "description": "text_chunker 切分", "fr_coverage": ["FR-03"]},
    {"id": "TC-04", "type": "unit", "description": "synth_engine 合成", "fr_coverage": ["FR-04"]},
    {"id": "TC-05", "type": "unit", "description": "circuit_breaker 保護", "fr_coverage": ["FR-05"]},
    {"id": "TC-06", "type": "unit", "description": "redis_cache 快取", "fr_coverage": ["FR-06"]},
    {"id": "TC-07", "type": "unit", "description": "routes CLI", "fr_coverage": ["FR-07"]},
    {"id": "TC-08", "type": "unit", "description": "audio_converter 轉換", "fr_coverage": ["FR-08"]},
    {"id": "TC-09", "type": "unit", "description": "kokoro_client 代理", "fr_coverage": ["FR-09"]}
  ],
  "test_strategy": {
    "unit_coverage_target": 80,
    "branch_coverage_target": 70,
    "integration_coverage_target": 60
  },
  "total_tests": 238,
  "average_coverage": 92
}
```
<!-- TEST:END -->
