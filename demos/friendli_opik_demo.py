from __future__ import annotations

import argparse
import os
from textwrap import shorten
from typing import Dict, List

from dotenv import load_dotenv

try:
    import opik  # type: ignore
    from opik.integrations.openai import track_openai  # type: ignore
except Exception:
    opik = None  # type: ignore
    track_openai = None  # type: ignore


def configure_opik() -> None:
    """Configure Opik tracing. No-op if Opik is unavailable."""
    if opik is None:
        return
    use_local = (os.getenv("OPIK_USE_LOCAL", "false").lower() == "true")
    try:
        opik.configure(use_local=use_local)
        if track_openai:
            track_openai()
    except Exception as e:
        print("OPIK: Tracing disabled (", e, ")")


def get_weaviate_client():
    import weaviate
    from weaviate.classes.init import Auth

    url = os.getenv("WEAVIATE_URL") or os.getenv("WEAVIATE_CLUSTER_URL")
    key = os.getenv("WEAVIATE_API_KEY")
    if not url or not key:
        raise RuntimeError(
            "WEAVIATE_URL (or WEAVIATE_CLUSTER_URL) and WEAVIATE_API_KEY are required"
        )
    headers = (
        {"X-Friendli-Token": os.getenv("FRIENDLI_TOKEN")}
        if os.getenv("FRIENDLI_TOKEN")
        else None
    )
    client = weaviate.connect_to_weaviate_cloud(
        cluster_url=url,
        auth_credentials=Auth.api_key(key),
        headers=headers,
    )
    if not client.is_connected():
        raise RuntimeError("Failed to connect to Weaviate")
    return client


def embed_query(text: str) -> List[float]:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for embeddings")
    client = OpenAI(api_key=api_key)
    return client.embeddings.create(model="text-embedding-3-small", input=[text]).data[0].embedding


def retrieve_context(question: str, top_k: int = 3) -> List[Dict]:
    client = get_weaviate_client()
    try:
        coll = client.collections.get("MeetingChunk")
        vec = embed_query(question)
        res = coll.query.near_vector(
            near_vector=vec,
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
        return out
    finally:
        try:
            client.close()
        except Exception:
            pass


def compose_prompt(question: str, contexts: List[Dict]) -> str:
    blocks = []
    for c in contexts:
        header = f"- [{c.get('date')}] ({c.get('source_type')}) {c.get('url')}"
        body = shorten(c.get("content") or "", width=1000, placeholder="…")
        blocks.append(f"{header}\n{body}")
    context_text = "\n\n".join(blocks)
    instruction = (
        "Answer strictly from the provided context. Cite meeting date and URL. "
        "If insufficient context, say so."
    )
    return f"{instruction}\n\nQuestion: {question}\n\nContext:\n{context_text}"


def friendli_chat_complete(messages: List[Dict[str, str]]) -> str:
    from openai import OpenAI

    token = os.getenv("FRIENDLI_TOKEN")
    if not token:
        raise RuntimeError("FRIENDLI_TOKEN is required for Friendli serverless completions")
    client = OpenAI(base_url="https://api.friendli.ai/serverless/v1", api_key=token)
    resp = client.chat.completions.create(
        model="meta-llama-3.3-70b-instruct",
        messages=messages,
    )
    return resp.choices[0].message.content


def main() -> None:
    load_dotenv()
    configure_opik()

    parser = argparse.ArgumentParser(description="Friendli + Opik demo over Weaviate")
    parser.add_argument("--question", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    contexts = retrieve_context(args.question, top_k=args.top_k)
    prompt = compose_prompt(args.question, contexts)
    messages = [{"role": "user", "content": prompt}]

    # Trace the LLM call if Opik is available
    if opik is not None:
        @opik.track  # type: ignore
        def _call_friendli_traced(msgs):
            return friendli_chat_complete(msgs)
        answer = _call_friendli_traced(messages)
    else:
        answer = friendli_chat_complete(messages)

    print("\n=== Answer ===\n")
    print(answer)
    print("\n=== Sources ===\n")
    for c in contexts:
        print(
            f"- [{c.get('date')}] ({c.get('source_type')}) "
            f"{c.get('url')}#chunk-{c.get('chunkIndex')}"
        )


if __name__ == "__main__":
    main()
