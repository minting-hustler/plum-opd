"""Pinecone retriever: embed query → query index → return top-k text chunks."""
from __future__ import annotations

import logging
import os

from pinecone import Pinecone
from services.gemini_service import embed_text

logger = logging.getLogger(__name__)

_pc: Pinecone | None = None
_index = None


def _get_index():
    global _pc, _index
    if _index is not None:
        return _index
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "plum-opd")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY env var not set")
    _pc = Pinecone(api_key=api_key)
    _index = _pc.Index(index_name)
    return _index


def retrieve(query: str, namespace: str, top_k: int = 5) -> list[str]:
    """Return top-k text chunks from Pinecone for the given query."""
    try:
        index = _get_index()
        query_vec = embed_text(query)
        results = index.query(
            vector=query_vec,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
        )
        chunks = []
        for match in results.get("matches", []):
            text = match.get("metadata", {}).get("text", "")
            if text:
                chunks.append(text)
        return chunks
    except Exception as e:
        logger.error(f"Pinecone retrieve failed ({namespace}): {e}")
        return []


def retrieve_with_metadata(query: str, namespace: str, top_k: int = 5) -> list[dict]:
    """Return top-k matches with full metadata."""
    try:
        index = _get_index()
        query_vec = embed_text(query)
        results = index.query(
            vector=query_vec,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
        )
        return results.get("matches", [])
    except Exception as e:
        logger.error(f"Pinecone retrieve_with_metadata failed: {e}")
        return []
