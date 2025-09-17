# Ask SF Supes — Hackathon Project

Scrape SF Board of Supervisors meetings, load into Weaviate, and query via a Strands Agent.

## Tech Stack

- Backend: `FastAPI`, `Strands Agents`, `OpenAI` (default) or `Amazon Bedrock`
- Retrieval: `Weaviate` (vectorizer: none) with client-side `OpenAI` embeddings
- Scraping: `Crawl4AI`, `requests`, `pdfplumber`, `beautifulsoup4`
- Frontend: `React` + `Vite` + `Tailwind CSS`
- Observability (optional): `Opik` traces; Friendli serverless via OpenAI-compatible API

## Development

### Local Setup

1. **Backend Setup:**
   ```bash
   python -m venv .venv-sfgov
   source .venv-sfgov/bin/activate  # On Windows: .venv-sfgov\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Frontend Setup:**
   ```bash
   cd web
   npm install
   ```

3. **Environment Variables:**
   Create a `.env` file in the project root:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   WEAVIATE_URL=your_weaviate_cluster_url
   WEAVIATE_API_KEY=your_weaviate_api_key
   # Optional for alternative providers:
   FRIENDLI_TOKEN=your_friendli_token
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   AWS_REGION=us-west-2
   ```

### Running the Application

#### Option 1: Docker (Recommended for Production)
```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build and run manually
docker build -t sf-gov-insight .
docker run -p 8000:8000 --env-file .env sf-gov-insight
```

#### Option 2: Combined Dev Script
```bash
# Runs both backend and frontend together
./dev.sh
```

8. Run the Strands Agent
```
python -m agent.agent --question "What did the board say about housing policy?"
```

9. Friendli + Opik demo (optional)
```
python -m demos.friendli_opik_demo --question "What did the board say about housing policy?" --top-k 3
```
This demo uses OpenAI embeddings, retrieves top chunks from Weaviate, and calls Friendli serverless for chat completions while logging traces to Opik.

## Weaviate Colab Reference
- This repo includes `ai_conference_hack_day_weaviate.py`, a local copy of a Colab wiring up Weaviate Cloud.
- We use client-side embeddings (OpenAI) with `vectorizer: none` on Weaviate.
 - If `FRIENDLI_TOKEN` is set, connections to Weaviate include the `X-Friendli-Token` header, mirroring the Colab script.

## Bedrock Setup for Strands (Summary)
- Enable Claude 4 Sonnet access in `us-west-2` in Bedrock.
- Configure AWS credentials via environment variables or `aws configure`.
- Strands defaults to Bedrock; see `detailed-requirements.md` for step-by-step instructions.

## Web UI

We ship a simple React UI to chat with the agent.

1) Install Node dependencies
```
cd web
npm install
```

2) Start the backend API (in a separate terminal at repo root)
```
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
```

3) Start the frontend dev server (in web/)
```
npm run dev
```

4) Open the app
```
http://localhost:5173
```

The chat calls `POST /api/ask` on `http://localhost:8000`. The response includes an answer and sources; the sidebar shows recent sources with direct links to transcript/minutes/agenda.

### Vite proxy & relative API path
- The frontend calls the backend via a relative path (`/api/ask`).
- In local dev, Vite proxies `/api/*` to the FastAPI server at `http://localhost:8000`.
- See `web/vite.config.ts` (`server.proxy`) for details.
- If `localhost` behaves oddly on your machine, use `http://127.0.0.1:5173` for the frontend.

### Local dev shortcuts
We provide helper scripts to run both backend and frontend together:

- One command (recommended):
  ```
  make dev
  ```
  This uses `./dev.sh` under the hood to:
  - Create/refresh a virtualenv at `.venv-sfgov`
  - `pip install -r requirements.txt`
  - Start `uvicorn` on `http://localhost:8000`
  - Start Vite on `http://127.0.0.1:5173`

- Run only backend:
  ```
  make backend
  ```

- Run only frontend:
  ```
  make frontend
  ```

## CI/CD

### CodeRabbit PR reviews
We use CodeRabbit’s AI PR reviewer on pull requests. The workflow lives at `.github/workflows/ai-pr-reviewer.yml` and runs on:
- PR opened / synchronized / reopened / ready_for_review
- New review comments

To enable it fully, add the following repository secret:
- `OPENAI_API_KEY`: your OpenAI API key

### Basic CI (backend and frontend)
`.github/workflows/ci.yml` runs on push and pull requests:
- Backend (Python): sets up Python, installs `requirements.txt`, runs `pytest`.
- Frontend (Node): installs dependencies and runs `npm run build` in `web/`.

This helps catch lint/build/test regressions early across both stacks.

### Switch providers for the Web UI

The backend defaults to OpenAI. To run the same UI with Amazon Bedrock:

1) Ensure Bedrock is enabled for the desired model (e.g., Claude 4 Sonnet) in `us-west-2` and your AWS creds are set in `.env`.

2) Start the backend with Bedrock provider (from repo root):
```
export STRANDS_PROVIDER=bedrock
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
```

3) Keep the frontend running at `http://localhost:5173`.

Notes:
- We set default region to `us-west-2` in code (`agent/agent.py`, `backend/api.py`). Override with env if needed.
- For OpenAI-compatible servers (Friendli serverless), set `FRIENDLI_TOKEN` and optionally `OPENAI_BASE_URL`.

## API

- `POST /api/ask`
  - Request: `{ "question": string, "top_k": number }`
  - Response: `{ "answer": string, "sources": [{ meetingId, url, date, source_type, chunkIndex }] }`

## Troubleshooting

- Bedrock `AccessDeniedException`: enable model access for the selected model in the AWS console (region `us-west-2`).
- Weaviate 403: use a write-capable `WEAVIATE_API_KEY`.
- CORS errors: the API allows `http://localhost:5173` by default; adjust origins in `backend/api.py` if needed.
- No sources in UI: verify ingestion ran against `data/meetings_refreshed.jsonl` or re-ingest with `--reset`.

## Notes
- CSS extraction and LLM fallback are scaffolded; tune selectors and enable LLM when ready.
- Keep an eye on rate limits; add throttling/caching if needed.
