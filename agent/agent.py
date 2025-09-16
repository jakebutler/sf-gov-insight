from __future__ import annotations

import argparse
from textwrap import shorten
import os

from dotenv import load_dotenv
# Ensure AWS region is set for Bedrock-backed Strands usage by default
os.environ.setdefault("AWS_REGION", "us-west-2")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")


def build_prompt_with_context(question: str, contexts: list[dict], max_chars: int = 6000) -> str:
    """Compose a prompt with retrieved context chunks.

    We keep the prompt simple for hackathon speed. Strands can be configured with tools later.
    """
    context_blocks = []
    for c in contexts:
        header = f"- [{c.get('date')}] ({c.get('source_type')}) {c.get('url')}"
        body = shorten(c.get("content") or "", width=1000, placeholder="…")
        context_blocks.append(f"{header}\n{body}")
    merged = "\n\n".join(context_blocks)
    instruction = (
        "You are a helpful assistant answering only from the provided context. "
        "Cite meeting date and URL for each claim. If insufficient context, say so."
    )
    prompt = f"{instruction}\n\nQuestion: {question}\n\nContext:\n{merged}"
    # Trim prompt if needed
    return prompt[:max_chars]


def _configure_strands(provider: str | None, model: str | None) -> None:
    if provider:
        os.environ.setdefault("STRANDS_PROVIDER", provider)
        os.environ.setdefault("STRANDS_MODEL_PROVIDER", provider)
    if model:
        os.environ.setdefault("STRANDS_MODEL", model)


def run_agent(question: str, top_k: int = 5, provider: str | None = None, model: str | None = None) -> None:
    load_dotenv()

    # Retrieve context from Weaviate first
    from agent.weaviate_tool import search_weaviate
    contexts = search_weaviate(question, top_k=top_k)
    composed = build_prompt_with_context(question, contexts)

    # Strands Agent
    from strands import Agent
    agent_instance = None
    if (provider or os.getenv("STRANDS_PROVIDER") or os.getenv("STRANDS_MODEL_PROVIDER")) == "openai":
        # Build an explicit OpenAIModel as per Strands docs
        try:
            from strands.models.openai import OpenAIModel  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Strands OpenAI provider not available. Ensure 'strands-agents[openai]' is installed."
            ) from e

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for Strands OpenAI provider")
        base_url = os.getenv("OPENAI_BASE_URL")
        # Friendli serverless compatibility (optional)
        if not base_url and os.getenv("FRIENDLI_TOKEN"):
            base_url = "https://api.friendli.ai/serverless/v1"
            api_key = os.getenv("FRIENDLI_TOKEN")

        model_id = model or os.getenv("STRANDS_MODEL") or "gpt-4o-mini"
        strands_model = OpenAIModel(
            client_args={
                "api_key": api_key,
                **({"base_url": base_url} if base_url else {}),
            },
            model_id=model_id,
            params={
                "max_tokens": 600,
                "temperature": 0.2,
            },
        )
        agent_instance = Agent(model=strands_model)
    else:
        # Default (Bedrock or configured elsewhere via env)
        _configure_strands(provider, model)
        agent_instance = Agent()

    answer = agent_instance(composed)

    print("\n=== Answer ===\n")
    print(answer)
    print("\n=== Sources ===\n")
    for c in contexts:
        print(f"- [{c.get('date')}] ({c.get('source_type')}) {c.get('url')}#chunk-{c.get('chunkIndex')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strands Agent for SF Supes RAG")
    parser.add_argument("--question", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--provider", help="Strands model provider override, e.g., 'openai' or 'bedrock'")
    parser.add_argument("--model", help="Strands model name override, e.g., 'gpt-4o-mini'")
    args = parser.parse_args()
    run_agent(args.question, args.top_k, provider=args.provider, model=args.model)
