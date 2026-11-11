"""Optional listwise rerank with the same Ollama chat model. Off unless RERANK=true."""

from __future__ import annotations

import json
import re

from webknot_bd.config import logger, settings


def parse_index_order(text: str, count: int) -> list[int] | None:
    """Pull a permutation of chunk indexes out of a model response."""
    match = re.search(r"\[[\d,\s]+\]", text)
    if not match:
        return None
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, list):
        return None
    indexes: list[int] = []
    for item in raw:
        if not isinstance(item, int) or item < 0 or item >= count or item in indexes:
            return None
        indexes.append(item)
    if len(indexes) != count:
        return None
    return indexes


def maybe_rerank(query: str, chunks: list[dict]) -> list[dict]:
    if not settings.rerank or len(chunks) < 2:
        return chunks
    try:
        from langchain_ollama import ChatOllama

        numbered = "\n\n".join(
            f"[{index}] {chunk.get('text', '')[:500]}" for index, chunk in enumerate(chunks)
        )
        prompt = (
            "Reorder these retrieved passages by usefulness for the query. "
            "Reply with only a JSON list of the indexes, most useful first. "
            f"The list must contain each index from 0 to {len(chunks) - 1} once.\n\n"
            f"Query: {query}\n\n{numbered}"
        )
        model = ChatOllama(
            model=settings.ollama_model,
            temperature=0,
            base_url=settings.ollama_base_url,
        )
        message = model.invoke(prompt)
        content = message.content if isinstance(message.content, str) else str(message.content)
        order = parse_index_order(content, len(chunks))
        if order is None:
            logger.warning("Rerank response was not a valid index list; keeping retrieval order")
            return chunks
        return [chunks[index] for index in order]
    except Exception:
        logger.warning("Rerank failed; keeping retrieval order", exc_info=True)
        return chunks
