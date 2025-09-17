from __future__ import annotations

import argparse
import json
import os
from typing import Dict, Iterable, List

from dotenv import load_dotenv

from ingest.chunking import chunk_text


def get_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


 
def get_weaviate_client():
    import weaviate
    from weaviate.classes.init import AdditionalConfig, Auth, Timeout

    cluster_url = (
        get_env("WEAVIATE_URL")
        or get_env("WEAVIATE_CLUSTER_URL")
    )
    api_key = get_env("WEAVIATE_API_KEY")
    friendli_token = get_env("FRIENDLI_TOKEN")
    if not cluster_url or not api_key:
        raise RuntimeError("WEAVIATE_URL/WEAVIATE_CLUSTER_URL and WEAVIATE_API_KEY are required")

    headers = {"X-Friendli-Token": friendli_token} if friendli_token else None
    # First try with increased init timeout
    try:
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=cluster_url,
            auth_credentials=Auth.api_key(api_key),
            headers=headers,
            additional_config=AdditionalConfig(timeout=Timeout(init=45)),
        )
        if not client.is_connected():
            raise RuntimeError("Failed to connect to Weaviate")
        return client
    except Exception:
        # Retry skipping init checks (bypass gRPC health check)
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=cluster_url,
            auth_credentials=Auth.api_key(api_key),
            headers=headers,
            skip_init_checks=True,
        )
        return client
    


def ensure_schema(client) -> None:
    from weaviate.classes.config import Configure, DataType, Property

    # Create if absent
    try:
        client.collections.get("MeetingChunk")
        return
    except Exception:
        pass

    client.collections.create(
        name="MeetingChunk",
        vectorizer_config=Configure.Vectorizer.none(),
        properties=[
            Property(name="meetingId", data_type=DataType.TEXT),
            Property(name="url", data_type=DataType.TEXT),
            Property(name="date", data_type=DataType.DATE),
            Property(name="source_type", data_type=DataType.TEXT),  # agenda | minutes | transcript
            Property(name="itemTitle", data_type=DataType.TEXT),
            Property(name="content", data_type=DataType.TEXT),
            Property(name="chunkIndex", data_type=DataType.INT),
        ],
    )


def reset_schema(client) -> None:
    """Drop MeetingChunk if it exists, then recreate schema."""
    try:
        coll = client.collections.get("MeetingChunk")
        coll.delete()
    except Exception:
        pass
    ensure_schema(client)


def openai_embed_texts(texts: List[str]) -> List[List[float]]:
    from openai import OpenAI

    api_key = get_env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for embeddings")
    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [d.embedding for d in resp.data]


def iter_meeting_chunks(meeting: Dict) -> Iterable[Dict]:
    meeting_id = meeting.get("meetingId")
    # Prefer source-specific URL from metadata for better citations
    meta = meeting.get("metadata") or {}
    default_url = meeting.get("url")
    date = meeting.get("meetingDate")
    for source_type in ("agenda_text", "minutes_text", "transcript_text"):
        content = meeting.get(source_type)
        st = source_type.replace("_text", "")
        if not content:
            continue
        chunks = chunk_text(content)
        # Choose the correct source URL
        if st == "agenda":
            src_url = meta.get("agenda_url") or default_url
        elif st == "minutes":
            src_url = meta.get("minutes_url") or default_url
        elif st == "transcript":
            src_url = meta.get("transcript_url") or default_url
        else:
            src_url = default_url
        for idx, chunk in enumerate(chunks):
            yield {
                "meetingId": meeting_id,
                "url": src_url,
                "date": date,
                "source_type": st,
                "itemTitle": None,
                "content": chunk,
                "chunkIndex": idx,
            }


def ingest(jsonl_path: str) -> None:
    client = get_weaviate_client()
    ensure_schema(client)
    collection = client.collections.get("MeetingChunk")

    count = 0
    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            meeting = json.loads(line)
            items = list(iter_meeting_chunks(meeting))
            if not items:
                continue
            texts = [it["content"] for it in items]
            vectors = openai_embed_texts(texts)
            for it, vec in zip(items, vectors):
                collection.data.insert(it, vector=vec)
                count += 1
    print(f"Ingested {count} chunks into Weaviate")
    try:
        client.close()
    except Exception:
        pass


def test_query(query: str, top_k: int = 5) -> None:
    client = get_weaviate_client()
    collection = client.collections.get("MeetingChunk")

    from openai import OpenAI

    api_key = get_env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for embeddings")
    oai = OpenAI(api_key=api_key)
    qvec = oai.embeddings.create(model="text-embedding-3-small", input=[query]).data[0].embedding

    res = collection.query.near_vector(
        near_vector=qvec,
        limit=top_k,
        return_properties=["meetingId", "url", "date", "source_type", "chunkIndex"],
    )
    for obj in res.objects:
        props = obj.properties
        print(props.get("date"), props.get("source_type"), props.get("url"))
    try:
        client.close()
    except Exception:
        pass


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Ingest meetings into Weaviate")
    parser.add_argument(
        "--jsonl",
        default="data/meetings.jsonl",
        help="Path to JSONL of meetings",
    )
    parser.add_argument(
        "--test-query",
        dest="test_query_str",
        help="Run a retrieval test instead of ingesting",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Drop and recreate the MeetingChunk collection before ingesting"
        ),
    )
    args = parser.parse_args()

    if args.test_query_str:
        test_query(args.test_query_str, args.top_k)
    else:
        if args.reset:
            client = get_weaviate_client()
            try:
                reset_schema(client)
            finally:
                try:
                    client.close()
                except Exception:
                    pass
        ingest(args.jsonl)


if __name__ == "__main__":
    main()
