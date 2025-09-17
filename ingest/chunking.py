from __future__ import annotations

from typing import List


def chunk_text(text: str, chunk_size: int = 2000, chunk_overlap: int = 200) -> List[str]:
    """Simple character-based chunking with overlap.

    For hackathon purposes, character-based is sufficient. Swap for token-based later if needed.
    """
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + chunk_size)
        chunks.append(text[start:end])
        if end == n:
            break
        start = end - chunk_overlap
        if start < 0:
            start = 0
    return chunks
