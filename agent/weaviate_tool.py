from __future__ import annotations

import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

try:
    import opik  # type: ignore
    from opik.integrations.openai import track_openai  # type: ignore
    _OPIK_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    opik = None
    track_openai = None
    _OPIK_AVAILABLE = False

def _maybe_configure_opik():
    if not _OPIK_AVAILABLE:
        return
    # Configure Opik once per process
    try:
        use_local = (os.getenv("OPIK_USE_LOCAL", "false").lower() == "true")
        opik.configure(use_local=use_local)
        if track_openai:
            # Patch OpenAI client to auto-log traces
            track_openai()
    except Exception:
        pass

def _track(func):
    if _OPIK_AVAILABLE:
        try:
            return opik.track(func)  # type: ignore
        except Exception:
            return func
    return func


def _get_weaviate_client():
    import weaviate
    from weaviate.classes.init import Auth

    url = os.getenv("WEAVIATE_URL") or os.getenv("WEAVIATE_CLUSTER_URL")
    key = os.getenv("WEAVIATE_API_KEY")
    if not url or not key:
        raise RuntimeError("WEAVIATE_URL (or WEAVIATE_CLUSTER_URL) and WEAVIATE_API_KEY are required")
    headers = {"X-Friendli-Token": os.getenv("FRIENDLI_TOKEN")} if os.getenv("FRIENDLI_TOKEN") else None
    client = weaviate.connect_to_weaviate_cloud(
        cluster_url=url,
        auth_credentials=Auth.api_key(key),
        headers=headers,
    )
    if not client.is_connected():
        raise RuntimeError("Failed to connect to Weaviate")
    return client


def _embed_query(query: str) -> List[float]:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for retrieval embeddings")
    client = OpenAI(api_key=api_key)
    return client.embeddings.create(model="text-embedding-3-small", input=[query]).data[0].embedding


@_track
def search_weaviate(
    query: str,
    top_k: int = 5,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    source_type: Optional[str] = None,
) -> List[Dict]:
    """Semantic search in the MeetingChunk collection and return top chunks with metadata."""
    load_dotenv()
    _maybe_configure_opik()
    client = _get_weaviate_client()
    coll = client.collections.get("MeetingChunk")

    qvec = _embed_query(query)
    res = coll.query.near_vector(
        near_vector=qvec,
        limit=top_k,
        return_properties=["meetingId", "url", "date", "source_type", "content", "chunkIndex"],
    )

    out: List[Dict] = []
    for obj in res.objects:
        props = obj.properties
        out.append({
            "meetingId": props.get("meetingId"),
            "url": props.get("url"),
            "date": props.get("date"),
            "source_type": props.get("source_type"),
            "content": props.get("content"),
            "chunkIndex": props.get("chunkIndex"),
        })
    try:
        client.close()
    except Exception:
        pass
    return out
