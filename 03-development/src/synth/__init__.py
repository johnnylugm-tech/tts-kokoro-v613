"""[FR-04] 合成引擎模組。

子模組：
- synth_engine：並行合成引擎（asyncio.gather + httpx.AsyncClient）
"""

from src.synth.synth_engine import (
    SynthesisRequest,
    SynthesisResult,
    SynthEngine,
    SynthesisPartialError,
    SynthesisUnavailableError,
)

__all__ = [
    "SynthesisRequest",
    "SynthesisResult",
    "SynthEngine",
    "SynthesisPartialError",
    "SynthesisUnavailableError",
]
