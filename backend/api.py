from __future__ import annotations

import os
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment
load_dotenv()
# Avoid interactive Opik prompts in API context
os.environ.setdefault("OPIK_USE_LOCAL", "true")
# Ensure AWS region defaults for Bedrock-backed Strands usage if enabled later
os.environ.setdefault("AWS_REGION", "us-west-2")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")

app = FastAPI(title="SF GovInsight API", version="0.1.0")

# CORS for local dev (Vite defaults)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


class Source(BaseModel):
    meetingId: Optional[str] = None
    url: Optional[str] = None
    date: Optional[str] = None
    source_type: Optional[str] = None
    chunkIndex: Optional[int] = None


class AskResponse(BaseModel):
    answer: str
    sources: List[Source]


# Utilities borrowed from agent/agent.py
from textwrap import shorten


def build_prompt_with_context(question: str, contexts: list[dict], max_chars: int = 6000) -> str:
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
    return prompt[:max_chars]


def get_strands_openai_model():
    """Construct a Strands OpenAIModel based on env (OpenAI or Friendli serverless)."""
    try:
        from strands.models.openai import OpenAIModel  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Strands OpenAI provider not available. Ensure 'strands-agents[openai]' is installed."
        ) from e

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    # Friendli serverless compatibility
    if not base_url and os.getenv("FRIENDLI_TOKEN"):
        base_url = "https://api.friendli.ai/serverless/v1"
        api_key = os.getenv("FRIENDLI_TOKEN")

    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY (or FRIENDLI_TOKEN for serverless)")

    model_id = os.getenv("STRANDS_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    # If routing to Friendli serverless and user didn't override model, avoid OpenAI-only defaults
    if base_url and "friendli.ai" in base_url and (
        model_id.startswith("gpt-") or model_id in ("gpt-4o-mini", "gpt-4o", "gpt-4.1")
    ):
        model_id = os.getenv("STRANDS_MODEL") or os.getenv("OPENAI_MODEL") or "meta-llama-3.3-70b-instruct"

    return OpenAIModel(
        client_args={
            "api_key": api_key,
            **({"base_url": base_url} if base_url else {}),
        },
        model_id=model_id,
        params={
            "max_tokens": 700,
            "temperature": 0.2,
        },
    )


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty")

    # Retrieve context from Weaviate
    try:
        from agent.weaviate_tool import search_weaviate
        contexts = search_weaviate(question, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {e}")

    if not contexts:
        return AskResponse(answer="No relevant context found.", sources=[])

    prompt = build_prompt_with_context(question, contexts)

    # Run Strands Agent using selected provider
    try:
        from strands import Agent
        provider = os.getenv("STRANDS_PROVIDER", "openai").lower()
        if provider == "openai":
            model = get_strands_openai_model()
            agent = Agent(model=model)
        else:
            # bedrock or other providers configured via env; Agent() will resolve
            agent = Agent()
        answer = agent(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent failed: {e}")

    sources: List[Source] = []
    for c in contexts:
        sources.append(
            Source(
                meetingId=c.get("meetingId"),
                url=c.get("url"),
                date=c.get("date"),
                source_type=c.get("source_type"),
                chunkIndex=c.get("chunkIndex"),
            )
        )

    return AskResponse(answer=str(answer), sources=sources)
