"""Token counting helpers using tiktoken (cl100k_base ≈ Claude's tokenizer, ±5%)."""
from __future__ import annotations

import functools

_ENCODING_NAME = "cl100k_base"


@functools.lru_cache(maxsize=1)
def _enc():
    import tiktoken
    return tiktoken.get_encoding(_ENCODING_NAME)


def count(text: str) -> int:
    """Count tokens in text. Cached encoder; safe to call frequently."""
    if not text:
        return 0
    return len(_enc().encode(text))


def count_file(path) -> int:
    """Count tokens in a file. Returns 0 if file cannot be read."""
    try:
        return count(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return 0


def display(tokens: int) -> str:
    """Human-readable token count rounded to nearest 500, prefixed with ~."""
    rounded = round(tokens / 500) * 500
    if rounded >= 1_000:
        return f"~{rounded // 1000:,}k"
    return f"~{rounded}"
