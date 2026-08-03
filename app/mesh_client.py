"""Mesh API client.

Mesh is an OpenAI-compatible gateway, so we drive it with the official openai
SDK and just point the client at Mesh's base URL. Every LLM and embedding call
in this codebase must go through the helpers in this module.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable, List, Optional

from openai import OpenAI

from app.config import get_settings


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    """Return a cached OpenAI SDK client pointed at Mesh."""
    settings = get_settings()
    if not settings.MESH_API_KEY:
        # We don't raise here so the app can still boot without a key (e.g. running
        # migrations or the CI checks). Individual calls will fail loudly if invoked.
        pass
    return OpenAI(
        api_key=settings.MESH_API_KEY or "missing",
        base_url=settings.MESH_BASE_URL,
    )


def chat_complete(
    messages: List[dict],
    *,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 800,
    response_format: Optional[dict] = None,
) -> str:
    """Simple chat completion. Returns the assistant message content as a string.

    Pass ``response_format={"type": "json_object"}`` to force JSON output.
    """
    settings = get_settings()
    client = get_client()
    kwargs = dict(
        model=model or settings.MESH_CHAT_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if response_format is not None:
        kwargs["response_format"] = response_format
    resp = client.chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip()


def embed(texts: Iterable[str], *, model: Optional[str] = None) -> List[List[float]]:
    """Embed one or more texts. Returns a list of vectors in input order."""
    settings = get_settings()
    client = get_client()
    text_list = [t for t in texts]
    if not text_list:
        return []
    resp = client.embeddings.create(
        model=model or settings.MESH_EMBED_MODEL,
        input=text_list,
    )
    return [d.embedding for d in resp.data]


def embed_one(text: str, *, model: Optional[str] = None) -> List[float]:
    """Convenience wrapper for embedding a single string."""
    return embed([text], model=model)[0]
