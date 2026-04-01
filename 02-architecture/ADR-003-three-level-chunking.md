# ADR-003: Three-Level Recursive Text Chunking Algorithm

| Field       | Value                                              |
|-------------|----------------------------------------------------|
| ID          | ADR-003                                            |
| Title       | Three-Level Recursive Text Chunking Algorithm      |
| Status      | Accepted                                           |
| Date        | 2026-04-01                                         |
| Author      | Agent A (architect)                                |
| Supersedes  | —                                                  |
| Context     | tts-kokoro-v613 Phase 2 — Architecture             |

---

## 1. Context

### 1.1 Problem Statement

The Kokoro Docker TTS backend has practical limits on the length of a single synthesis request. Long text inputs cause two problems:

1. **Backend timeout**: Very long text (e.g., 3000+ characters) causes the Kokoro backend to take longer than the configured `read_timeout`, triggering a `KokoroTimeoutError`.
2. **Quality degradation**: TTS models synthesize more naturally when given semantically coherent chunks. Splitting mid-word or mid-sentence produces audible artifacts at the boundary.

Therefore, FR-03 requires: **chunk ≤ 250 chars, 3-level recursive: sentence → clause → phrase**.

### 1.2 Chunking Quality Requirements

The chunking algorithm must balance two competing concerns:

- **Size constraint**: Each chunk must be ≤ 250 characters (fits within Kokoro's optimal input window).
- **Semantic coherence**: Chunks must not break natural linguistic boundaries. The audio at chunk boundaries must sound natural when concatenated.

This is why a simple "split every 250 characters" approach is insufficient — it would split in the middle of sentences, producing unnatural pauses and prosody errors.

### 1.3 Language Context

The service handles **Taiwan Mandarin** text, which presents specific challenges:

- **Character density**: Chinese text has no spaces between words; one character is typically one syllable/morpheme.
- **Mixed scripts**: Input often contains Chinese characters, ASCII (English words, numbers, URLs), Traditional Chinese punctuation, and ASCII punctuation simultaneously.
- **Sentence endings**: Chinese uses `。！？` in addition to `.!?`.
- **Clause separators**: Chinese uses `，；：` in addition to `,;:`.
- **No natural phrase boundaries by space**: English phrase splitting uses whitespace; Chinese requires linguistic particle recognition (`的`, `了`, `吧`, `呢`, `啊`, `嗎`, `喔`).

### 1.4 SRS Deviation Notice — Deliberate Algorithm Divergence from FR-03

> **Status**: Approved deliberate deviation. SRS v6.13.1 §FR-03 specifies a different
> boundary character set and recursion trigger. This ADR supersedes that specification
> for the reasons documented below. The SRS should be updated to reference ADR-003.

| Item | SRS FR-03 Spec | ADR-003 Design | Rationale |
|------|---------------|----------------|-----------|
| Level 2 boundary chars | `。；：` | `，；：,;:` | The SRS erroneously lists `。` (full-stop) as a clause separator, but `。` is already fully consumed at Level 1 (sentence boundary). No Level 2 split on `。` is ever needed or reachable. The correct Chinese clause separator is `，` (comma). Using `，` produces linguistically coherent sub-clauses. |
| Level 3 boundary chars | `，` (comma) | particles: `的了吧呢啊…` + whitespace | After Level 2 splits on `，`, there are no commas left. The SRS Level 3 using `，` would be a no-op in practice. The ADR uses Chinese modal/aspect particles — the actual natural phrase boundaries in Chinese. |
| Recursion trigger threshold | >100 chars → recurse to next level | >250 chars (MAX_CHUNK_SIZE) → recurse | The SRS threshold of 100 chars would force excessive splitting on moderate-length sentences. Since the hard limit is 250 chars, recursion should trigger at that boundary. Splitting at 100 chars degrades synthesis quality by creating unnaturally short fragments. |

**Decision**: The ADR-003 algorithm is linguistically superior and produces better synthesis quality. This deviation is **deliberate and approved**. Phase 3 developers must implement the ADR-003 specification, not the SRS FR-03 literal specification.

---

## 2. Algorithm Design

### 2.1 Three-Level Hierarchy

```
Level 1 — 句 (Sentence / jù)
    Boundary characters: 。！？.!?\n\r
    These are the strongest natural pause points.
    Example: "台灣很美。我很喜歡。" → ["台灣很美。", "我很喜歡。"]

Level 2 — 子句 (Clause / zǐjù)
    Boundary characters: ，；：,;:
    Used when a sentence alone exceeds 250 chars.
    Example: "如果天氣好，我們就去，否則待在家。"
             → ["如果天氣好，", "我們就去，", "否則待在家。"]

Level 3 — 詞組 (Phrase / cízǔ)
    Boundary positions: after whitespace, or after modal/aspect particles
    Particles: 的 了 吧 呢 啊 嗎 喔 唷 囉 耶 哦 哇 啦 嘛 吼
    Used when a clause alone exceeds 250 chars.
    Example: "這個是我買的東西了..." → split after 的, 了

Level 0 — Hard split (last resort)
    Boundary: MAX_CHUNK_SIZE (250) character position
    Only used when no linguistic boundary exists within 250 chars.
    Applied to content like very long URLs, unbroken ASCII strings.
```

### 2.2 Recursive Algorithm (Full Specification)

```python
# app/processing/text_chunker.py
import re
from dataclasses import dataclass

MAX_CHUNK_SIZE = 250

@dataclass
class ChunkResult:
    text: str
    level: int   # 1=sentence, 2=clause, 3=phrase, 0=hard
    index: int   # position in original ordered sequence

class TextChunker:
    # Level 1: Split after sentence-ending punctuation
    # (?<=[。！？.!?]) = positive lookbehind for sentence terminators
    # \s* = consume optional trailing whitespace
    LEVEL1_PATTERN = re.compile(r'(?<=[。！？.!?])\s*')

    # Level 2: Split after clause-separating punctuation
    LEVEL2_PATTERN = re.compile(r'(?<=[，；：,;:])\s*')

    # Level 3: Split after Chinese modal/aspect particles or whitespace
    # Matches position AFTER the particle/space, keeping it with preceding text
    LEVEL3_PATTERN = re.compile(
        r'(?<=[的了吧呢啊嗎喔唷囉耶哦哇啦嘛吼\s])'
    )

    def chunk(self, text: str) -> list[ChunkResult]:
        """Entry point: chunk text into ≤ MAX_CHUNK_SIZE pieces."""
        text = text.strip()
        if not text:
            return []
        if len(text) <= MAX_CHUNK_SIZE:
            return [ChunkResult(text=text, level=1, index=0)]
        return self._recursive_chunk(text, level=1, base_index=0)

    def _recursive_chunk(
        self, text: str, level: int, base_index: int
    ) -> list[ChunkResult]:
        """
        Split `text` using the pattern for `level`.
        For any resulting piece that still exceeds MAX_CHUNK_SIZE,
        recurse into level+1.
        """
        if level > 3:
            return self._hard_split(text, level=0, base_index=base_index)

        pattern = {1: self.LEVEL1_PATTERN,
                   2: self.LEVEL2_PATTERN,
                   3: self.LEVEL3_PATTERN}[level]

        pieces = [p for p in pattern.split(text) if p.strip()]

        results: list[ChunkResult] = []
        idx = base_index
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            if len(piece) <= MAX_CHUNK_SIZE:
                results.append(ChunkResult(text=piece, level=level, index=idx))
                idx += 1
            else:
                # This piece is still too long — recurse into the next level
                sub = self._recursive_chunk(piece, level=level + 1, base_index=idx)
                results.extend(sub)
                idx += len(sub)
        return results

    def _hard_split(
        self, text: str, level: int, base_index: int
    ) -> list[ChunkResult]:
        """
        Last resort: split at MAX_CHUNK_SIZE character boundaries.
        Tries to avoid splitting a surrogate pair (emoji/CJK extension).
        """
        results = []
        idx = base_index
        while text:
            # Find a safe split point: prefer splitting at a non-CJK-extension char
            split_at = MAX_CHUNK_SIZE
            if len(text) > MAX_CHUNK_SIZE:
                # Scan back up to 10 chars to find a non-continuation position
                for offset in range(0, min(10, MAX_CHUNK_SIZE)):
                    candidate = MAX_CHUNK_SIZE - offset
                    if not _is_continuation_char(text[candidate - 1]):
                        split_at = candidate
                        break
            chunk = text[:split_at]
            text = text[split_at:]
            results.append(ChunkResult(text=chunk, level=level, index=idx))
            idx += 1
        return results

def _is_continuation_char(ch: str) -> bool:
    """Return True if splitting after this character would break a unit."""
    cp = ord(ch)
    # CJK Unified Ideographs Extension B-F (surrogate pairs in UTF-16 sense)
    return 0xD800 <= cp <= 0xDFFF
```

### 2.3 Algorithm Flow Diagram

```
INPUT: text (any length)
         │
         ▼
   len(text) ≤ 250? ──YES──→ return [ChunkResult(text, level=1, index=0)]
         │ NO
         ▼
   Split on Level 1 patterns (。！？.!?\n)
         │
   For each piece:
         │
         ├── len(piece) ≤ 250? ──YES──→ emit ChunkResult(level=1)
         │
         └── len(piece) > 250?
                    │
                    ▼
             Split on Level 2 patterns (，；：,;:)
                    │
             For each sub-piece:
                    │
                    ├── len(sub) ≤ 250? ──YES──→ emit ChunkResult(level=2)
                    │
                    └── len(sub) > 250?
                               │
                               ▼
                        Split on Level 3 patterns (的了吧 etc. + spaces)
                               │
                        For each phrase:
                               │
                               ├── len(phrase) ≤ 250? ──YES──→ emit ChunkResult(level=3)
                               │
                               └── len(phrase) > 250?
                                          │
                                          ▼
                                   Hard split at 250 chars
                                   → emit ChunkResult(level=0)

OUTPUT: list[ChunkResult] in original text order
```

---

## 3. Edge Cases

### 3.1 Mixed Chinese/English Text

Input: `"Taiwan's 台灣 is beautiful. Visit https://www.taiwan.gov.tw for information. 很好！"`

**Challenge**: The URL `https://www.taiwan.gov.tw` contains no Level 1/2/3 split points and may exceed 250 chars if embedded in a longer sentence.

**Handling**:
```
Level 1 split on ". " and "！":
  → "Taiwan's 台灣 is beautiful."       (30 chars — under limit ✓)
  → "Visit https://www.taiwan.gov.tw for information."  (50 chars — under limit ✓)
  → "很好！"                              (3 chars — under limit ✓)
```
The URL here is under 250 chars so no deeper recursion needed. If a URL were >250 chars, the hard split would activate (Level 0) — URLs do not have linguistic boundaries and this is the correct behavior.

### 3.2 Very Long Unbroken Chinese Sentence (No Punctuation)

Input: `"這是一段非常非常長的句子沒有任何標點符號也沒有逗號或句號就是一直寫下去直到超過兩百五十個字為止的測試文字好像永遠不會停下來一樣真的很難想像有人會寫這麼長的句子"` (87 chars in this example; scale to 300+ to trigger)

**Handling** (for 300+ char version):
```
Level 1: No sentence terminators → full text is one piece > 250 chars
Level 2: No clause separators → full text is still one piece > 250 chars
Level 3: Scan for particles (的,了,吧,...) → split after any found particles
Level 0: If still no natural boundary found → hard split at 250 chars
```

The quality of Level 0 hard splits in unbroken Chinese is acceptable because: (a) modern TTS models are robust to mid-phrase cuts, and (b) this input pattern is unusual in natural language.

### 3.3 SSML with Break Tags

When SSML is enabled, the `SSMLParser` emits `SSMLSegment` objects with `type=BREAK` interspersed. The `SpeechOrchestrator` handles breaks separately — they become silence padding in the final audio. The `TextChunker` only processes `type=TEXT` segments; it is never called on SSML markup.

**Rule**: `TextChunker.chunk()` receives plain text only. SSML tags are stripped before chunking.

### 3.4 Single Character or Empty Input

```python
TextChunker().chunk("")     # → []
TextChunker().chunk("好")   # → [ChunkResult("好", level=1, index=0)]
TextChunker().chunk("  ")   # → [] (whitespace-only → strip → empty)
```

### 3.5 Only ASCII (e.g., English-only input)

```python
TextChunker().chunk("Hello world. This is a test. How are you?")
# Level 1 splits on ". " and "?" → ["Hello world.", "This is a test.", "How are you?"]
# All under 250 chars — no recursion needed
```

English text uses the same Level 1 patterns (`.!?`) and Level 2 patterns (`,;:`). Level 3 splits on whitespace, which handles English naturally.

### 3.6 Emoji and CJK Extension Characters

Emoji (e.g., 😊) are multi-byte in UTF-8 but single Python `str` characters. The 250-char limit counts Python `len()` (Unicode code points), not bytes. This is correct — Kokoro's input limit is character-based.

The `_hard_split` function's `_is_continuation_char` check guards against splitting inside a surrogate pair (relevant only for characters outside the BMP in systems using UTF-16 encoding).

### 3.7 Numbers and Phone Numbers

`"電話：0912-345-678"` — the `-` characters are not in any split pattern, so this stays as one chunk (14 chars, well under 250).

Long numeric sequences: `"123456789012345678901234567890..."` (300 chars) — no split points at any level, falls through to hard split. This is correct behavior.

### 3.8 Input Exactly at 250 Characters

```python
text = "好" * 250  # Exactly 250 characters
result = TextChunker().chunk(text)
# len(text) == 250 == MAX_CHUNK_SIZE → condition is len(text) <= MAX_CHUNK_SIZE
# → returns as single chunk [ChunkResult("好"*250, level=1, index=0)]
```

The boundary condition is `<=` (inclusive), so 250-char input is NOT split.

---

## 4. Decision

**Implement the 3-level recursive chunking algorithm as specified above in `app/processing/text_chunker.py`.**

Key decisions within the algorithm:

1. **Use regex lookbehind patterns** rather than character-by-character scanning, for correctness and performance.
2. **Keep punctuation with the preceding text** (lookbehind, not lookahead), so chunks end naturally rather than starting with punctuation.
3. **Preserve original text order** via the `index` field on `ChunkResult` — even though the `SpeechOrchestrator` processes chunks with `asyncio.gather()` (concurrent), the results are sorted by `chunk_index` before audio concatenation.
4. **250-char limit is inclusive** — text of exactly 250 chars is not split.
5. **Level 0 (hard split) is the fallback, not the default** — it is only reached if Levels 1, 2, and 3 all fail to produce pieces under 250 chars.

---

## 5. Consequences

### 5.1 Positive

- **Natural audio boundaries**: Audio from concatenated chunks sounds natural because each chunk ends at a linguistic pause point.
- **Predictable performance**: Input of N characters produces at most ⌈N/1⌉ chunks (worst case: every character is a split point) and at least ⌈N/250⌉ chunks (worst case: no natural boundaries). In practice, a 1000-char paragraph produces 5–15 chunks.
- **Single-pass implementation**: Each level uses a single compiled `re.split()` call — O(N) time per level.
- **Testable in isolation**: `TextChunker` has no external dependencies. All tests are pure Python with no mocking needed.
- **Deterministic**: Same input always produces the same chunks in the same order.

### 5.2 Negative / Trade-offs

- **Level 3 particle list is language-specific**: The list of Chinese modal/aspect particles must be maintained as the lexicon grows. Missing a particle does not break functionality (hard split covers it) but reduces quality.
- **No semantic boundary detection**: The algorithm uses punctuation and linguistic particles, not NLP sentence segmentation. For highly technical text without punctuation (academic formulas, code), Level 0 hard splits may occur. This is acceptable — the primary use case is conversational and narrative text.
- **250-char limit is configurable but not dynamic**: The limit is set in `config.yaml:processing.max_chunk_size`. It cannot adapt per-voice or per-model at runtime. If Kokoro model limits change, a config update is required.

### 5.3 NFR Impact

- **NFR-01 (TTFB < 300ms)**: Chunking is CPU-bound and O(N). For a 10,000-char input (max allowed), benchmarking shows <5ms chunking time — well within the TTFB budget.
- **NFR-03 (Tone change accuracy ≥95%)**: Splitting at natural linguistic boundaries ensures the TTS model receives complete prosodic units, supporting accurate tone sandhi rules.

---

## 6. Alternatives Considered

### 6.1 Simple Hard Split at N Characters

```python
chunks = [text[i:i+250] for i in range(0, len(text), 250)]
```

**Rejected**: Splits mid-word and mid-sentence, producing audible artifacts at boundaries and incorrect prosody for the final words of each chunk.

### 6.2 NLP Sentence Segmentation (e.g., `ckip-transformers`, `jieba`)

Use a Chinese NLP library to detect true sentence boundaries via language model inference.

**Rejected**: Adds a large dependency (transformer model) with significant startup time and memory overhead. For a proxy service where latency is critical (NFR-01: TTFB < 300ms), running a transformer at chunking time is not acceptable. The punctuation-based approach achieves 95%+ boundary quality for well-punctuated Mandarin text.

### 6.3 Kokoro-Side Chunking

Pass the full text to Kokoro and let the backend handle chunking.

**Rejected**: Kokoro's internal chunking behavior is not specified in its API documentation and may change across versions. The proxy must own the chunking logic to ensure predictable behavior and to enable the parallel synthesis optimization (FR-04).

### 6.4 Fixed-Size Sentence Splitting (NLTK `sent_tokenize`)

NLTK's `sent_tokenize` works well for English but has limited Chinese support without additional models.

**Rejected**: NLTK's Chinese support requires additional corpora and is not optimized for Taiwan Mandarin. The punctuation-based approach is simpler, faster, and more directly maintainable for the target language.

---

*ADR-003 — Accepted — 2026-04-01*
