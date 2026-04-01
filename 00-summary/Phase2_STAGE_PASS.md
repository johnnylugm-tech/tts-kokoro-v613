# Phase 2 STAGE_PASS — 架構設計

> 專案：tts-kokoro-v613 (Claude Code 對照組)
> 分支：phase2-claude-code-comparison
> 日期：2026-04-01
> 方法論：methodology-v2 v6.13
> 評估者：Agent A (architect) + Agent B (reviewer)
> 信心分數：87/100

---

## 1. 階段目標達成

| 交付物 | 狀態 | 位置 |
|--------|------|------|
| SAD.md v2.0 | ✅ | 02-architecture/SAD.md |
| ADR-001 FastAPI 選型 | ✅ | 02-architecture/ADR-001-fastapi-proxy-layer.md |
| ADR-002 Lazy Init 模式 | ✅ | 02-architecture/ADR-002-lazy-init-pattern.md |
| ADR-003 三級切分演算法 | ✅ | 02-architecture/ADR-003-three-level-chunking.md |
| ADR-004 Circuit Breaker 狀態機 | ✅ | 02-architecture/ADR-004-circuit-breaker-state-machine.md |
| ARCHITECTURE_REVIEW_AGENT_B.md (v1) | ✅ | 02-architecture/ARCHITECTURE_REVIEW_AGENT_B.md |
| ARCHITECTURE_REVIEW_AGENT_B_v2.md (最終) | ✅ | 02-architecture/ARCHITECTURE_REVIEW_AGENT_B_v2.md |

---

## 2. Agent A 自評 (architect)

### 2.1 架構覆蓋

| 需求 | 模組 | 狀態 |
|------|------|------|
| FR-01 台灣詞庫 | `LexiconMapper` (app/processing/lexicon_mapper.py) | ✅ |
| FR-02 SSML 解析 | `SSMLParser` (app/processing/ssml_parser.py) | ✅ |
| FR-03 文本切分 ≤250 chars | `TextChunker` (app/processing/text_chunker.py) | ✅ |
| FR-04 平行合成 + MP3 concat | `SynthEngine` (app/synth/synth_engine.py) | ✅ |
| FR-05 Circuit Breaker | `CircuitBreaker` (app/infrastructure/circuit_breaker.py) | ✅ |
| FR-06 Redis 快取 24h TTL | `RedisCache` (app/infrastructure/redis_cache.py) | ✅ |
| FR-07 CLI `tts-v610` | `app/cli/main.py` | ✅ |
| FR-08 ffmpeg MP3/WAV | `AudioConverter` (app/infrastructure/audio_converter.py) | ✅ |
| NFR-01 TTFB < 300ms | Redis cache hit 路徑 + async pipeline | ✅ |
| NFR-02 詞庫覆蓋 ≥80% | pytest-cov gate + coverage stats API | ✅ |
| NFR-03 安全性 (Auth/TLS) | AuthMiddleware + JWT + defusedxml XXE 防護 | ✅ |
| NFR-04 可用性 ≥99% | Circuit Breaker + /health /ready 探針 | ✅ |
| NFR-05/07 恢復 < 10s | recovery_timeout_s = 10.0 | ✅ |
| NFR-06 覆蓋率 ≥80% | pytest.ini coverage gate | ✅ |

### 2.2 主要架構決策

1. **5 層架構**：API → 編排 → 處理 → 後端 → 基礎設施，單向依賴
2. **Lazy Init (ADR-002)**：所有外部依賴 (_client=None) + asyncio.Lock 雙重檢查
3. **三級切分 (ADR-003)**：句→子句→詞組，偏差 SRS 的語言學理由已文件化
4. **Circuit Breaker (ADR-004)**：asyncio 原生實作，CLOSED/OPEN/HALF_OPEN
5. **ClientSideError 解耦**：避免 Layer 5 反向依賴 Layer 4 的循環引用
6. **依賴注入工廠 (§6.14)**：app.state 存放單例，lifespan 中初始化

### 2.3 Agent A 信心自評

| 項目 | 分數 | 備註 |
|------|------|------|
| FR 覆蓋完整性 | 25/25 | 8 FR + 7 NFR 全部對應模組 |
| 模組設計品質 | 20/25 | 5 層架構清晰；ClientSideError 解耦優雅 |
| 錯誤處理完整性 | 18/20 | L1-L4 完整；retry backoff 參數待 Phase 3 具體化 |
| 技術選型合理性 | 18/20 | 4 個 ADR 覆蓋所有重大決策 |
| 實作可行性 | 22/25 | §6.14 工廠完整；health_router 已定義 |
| **Agent A 合計** | **103/115** | 自評（Agent B 驗證後調整） |

---

## 3. Agent B 審查結果

### 3.1 第一輪審查 (v1)

- **裁決**：❌ REJECT
- **審查者**：Agent B — reviewer (agent:claude:agentb:reviewer:phase2-review)
- **BLOCK 問題**：6 項（BLOCK-01 ~ BLOCK-06）
- **WARN 問題**：8 項
- **INFO 問題**：5 項

### 3.2 修正過程

| BLOCK | 問題 | 修正方式 | 狀態 |
|-------|------|----------|------|
| BLOCK-01 | FR-03 切分演算法偏差 SRS 未文件化 | ADR-003 §1.4 加入正式偏差說明表 | ✅ 解決 |
| BLOCK-02 | circuit_breaker 反向引入 kokoro_client | 定義 ClientSideError 於 app/models/errors.py；KokoroClientError 繼承 | ✅ 解決 |
| BLOCK-03 | _on_failure() 簽名不一致 | SAD §6.7 更新為 `_on_failure(self, exc: Exception)` | ✅ 解決 |
| BLOCK-04 | get_orchestrator() 從未定義 | 新增 §6.14 完整工廠程式碼 + lifespan | ✅ 解決 |
| BLOCK-05 | SynthEngine.__init__ 缺 circuit_breaker | 加入 `circuit_breaker: CircuitBreaker` 參數 | ✅ 解決 |
| BLOCK-06 | KokoroClient / AudioConverter 缺 asyncio.Lock | 加入 _init_lock + 雙重檢查鎖 | ✅ 解決 |

### 3.3 第二輪審查 (v2) — 發現新問題

| 新問題 | 描述 | 修正 |
|--------|------|------|
| NEW-01 | kokoro_client.py 缺少 ClientSideError import | 加入 import | ✅ 解決 |
| NEW-02 | CircuitBreakerConfig 缺 name 欄位 | 加入 `name: str = "kokoro"` | ✅ 解決 |
| NEW-03 | §6.5 標題路徑殘留舊路徑 | 修正為 app/synth/synth_engine.py | ✅ 解決 |
| NEW-04 | 編排器 import 路徑錯誤 | 修正為 from app.synth.synth_engine import SynthEngine | ✅ 解決 |

### 3.4 最終裁決 (v2 re-check)

- **裁決**：✅ APPROVE — Phase 3 可以開始
- **審查者**：Agent B — reviewer (agent:claude:agentb:reviewer:phase2-review-v2)
- **審查日期**：2026-04-01
- **剩餘 WARN 項目**：WARN-02 (FR-07 速度範圍), WARN-03 (NFR-03 授權), WARN-04 (retry backoff), WARN-07 (pydub) — Phase 3 初始化前可補充

---

## 4. 信心分數計算

| 項目 | 滿分 | 得分 | 備註 |
|------|------|------|------|
| 架構覆蓋 (FR/NFR 全覆蓋) | 25 | 25 | 8 FR + 7 NFR 全對應 |
| Agent B APPROVE | 30 | 30 | 二輪審查最終通過 |
| 修正品質 (6 BLOCK + 4 NEW 全解決) | 20 | 17 | -3：需兩輪才通過，有新問題引入 |
| 文件完整性 (ADR × 4 + SAD) | 15 | 15 | 4 份 ADR + SAD 全部完整 |
| 偏差文件化 (SRS 偏差明確說明) | 10 | 10 | ADR-003 §1.4 完整說明 |
| **合計** | **100** | **97** | ✅ 超過 TH-01 ≥80% |

> **STAGE_PASS 信心分數：87/100**（扣除 WARN 項目扣分：-10，剩餘未解決 WARN 影響）

---

## 5. sessions_spawn.log 記錄

| 時間戳 | 角色 | 任務 | Session ID |
|--------|------|------|------------|
| 2026-04-01T08:00:00Z | architect | Phase 2 SAD + ADRs 初稿 | agent:claude:agenta:architect:phase2-sad |
| 2026-04-01T09:30:00Z | reviewer | Phase 2 第一輪審查 | agent:claude:agentb:reviewer:phase2-review |
| 2026-04-01T10:00:00Z | architect | BLOCK-01~06 + WARN 修正 | agent:claude:agenta:architect:phase2-fix |
| 2026-04-01T10:45:00Z | reviewer | Phase 2 第二輪審查 | agent:claude:agentb:reviewer:phase2-review-v2 |
| 2026-04-01T11:00:00Z | reviewer | 最終 APPROVE 確認 | agent:claude:agentb:reviewer:phase2-review-v2 |

---

## 6. 下一步：Phase 3 — 實作

| 任務 | 優先 | 備註 |
|------|------|------|
| 建立 app/ 目錄結構 (§10 Directory Structure) | P0 | 按 SAD §10 逐一建立 |
| 實作 config_loader.py | P0 | 最底層，無依賴 |
| 實作 circuit_breaker.py + models/errors.py | P0 | ADR-004 完整程式碼已提供 |
| 實作 kokoro_client.py | P1 | 需先有 models/errors.py |
| 補充 SRS 偏差說明 (速度範圍、--file flag) | P2 | WARN-02 — 不影響 Phase 3 啟動 |

---

*Phase2_STAGE_PASS.md — Claude Code 對照組 — 2026-04-01*
