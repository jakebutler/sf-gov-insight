# Detailed Requirements — “Ask SF Supes” Hackathon

Scrape San Francisco Board of Supervisors meeting pages (agenda, minutes, transcript), normalize to a standard JSON schema, embed into a RAG database (Weaviate), and build an agent interface (Strands Agents) for Q&A with sources.

This document expands on `high-level-requirements.md` and `crawler-requirements.md` into a buildable project plan with milestones, acceptance criteria, environment variables, and a concise runbook. See `IMPLEMENTATION_PLAN.md` for staged execution tracking and current status.

---

## 0) Goals, Scope, Success Criteria

- Core loop: scrape → normalize JSONL → chunk + embed → retrieve → answer with citations.
- Produce at least 5–10 meeting records with usable text blobs (agenda/minutes/transcript) and a working retrieval agent.
- Keep the code modular and runnable locally in under 10 minutes.

Out of scope for MVP
- Full coverage of all historical meetings.
- Complex analytics or summarization beyond short, source-backed answers.

Success criteria
- JSONL at `data/meetings.jsonl` with ≥5 valid meeting records.
- Weaviate populated with chunks; a test query returns relevant chunks.
- Agent answers a natural-language question with citations (meeting date + URL).

---

## 1) Inputs and Outputs

### 1.1 Inputs
- Primary input: `data/urls.csv` (exported from Google Sheets)
  - Expected columns: `url` (required), `date` (optional ISO8601), `meeting_name` (optional), `notes` (optional).
  - Alternative (optional): Google Sheets API via `gspread` (skip during 4-hour MVP to avoid OAuth complexity).

### 1.2 Outputs
- Normalized JSONL at `data/meetings.jsonl`, one record per meeting page:

```json
{
  "meetingId": "<generated: e.g. supes-2025-09-10-uuid>",
  "meetingName": "SF Board of Supervisors - Regular Meeting",
  "meetingDate": "2025-09-10T10:00:00-07:00",
  "meetingLocation": "City Hall - Room 250",
  "url": "https://...",
  "metadata": {
    "fileNumber": "xxx",
    "version": "v1",
    "agendaNumber": "12",
    "type": "Regular",
    "status": "Approved"
  },
  "meetingItems": [
    {
      "itemIndex": 1,
      "name": "Public Comment",
      "title": "Open Forum",
      "type": "Public",
      "status": "N/A",
      "details": "short text from table row or derived summary",
      "attachments": [
        { "label": "agenda pdf", "url": "https://....pdf", "file_type": "pdf" }
      ]
    }
  ],
  "agenda_text": "<full agenda text if present>",
  "minutes_text": "<full minutes text if present>",
  "transcript_text": "<full transcript text if present>",
  "derived": {
    "word_count": 1234,
    "extracted_speakers": ["Supervisor X", "Supervisor Y"],
    "pdfs_parsed": ["https://...pdf"]
  },
  "provenance": {
    "crawled_at": "2025-09-15T17:12:00Z",
    "crawler_version": "c4a-0.7.x",
    "raw_html_path": "raw/example-page-1.html"
  }
}
```

Acceptance criteria for a valid meeting record
- Has `meetingId`, `url`, `provenance.crawled_at`, and at least one of the three text blobs (`agenda_text`, `minutes_text`, `transcript_text`).

---

## 2) Architecture & Directory Layout

```
/ (repo root)
  /data
    urls.csv                 # exported from spreadsheet
    meetings.jsonl           # final output from scraper
    raw/                     # optional raw HTML/PDF cache
  /scraper
    __init__.py
    scrape.py                # CLI entrypoint
    extractors.py            # CSS extractors
    llm_schemas.py           # Pydantic models for LLM extraction
    llm_extractor.py         # LLMExtractionStrategy integration
    utils.py                 # read_urls_from_csv, append_jsonl, etc.
  /ingest
    ingest.py                # chunk + embed + push to Weaviate
    chunking.py              # text chunk functions
  /agent
    agent.py                 # Strands agent with Weaviate retrieval tool
    weaviate_tool.py         # retrieval implementation
  /frontend (optional)
    index.html               # minimal chat UI (stretch)
  requirements.txt          # Python deps for scraper + ingest + agent
  README.md
  detailed-requirements.md  # this document
```

Notes
- The scraper uses Crawl4AI. Extraction is CSS-first with LLM fallback.
- The ingest step uses Weaviate client + an embeddings provider (OpenAI or Cohere). We will embed client-side and set vectorizer to `none` in Weaviate.
- The agent is built with Strands Agents and uses a custom retrieval tool to query Weaviate.

---

## 3) Detailed Implementation Plan

### 3.1 Scraper (Crawl4AI)

Dependencies (minimum)
- `crawl4ai>=0.7.0`, `aiohttp`, `pydantic`, `python-dateutil`, `tqdm`, `pandas`, `beautifulsoup4`, `lxml`, `requests`
- Optional: `pdfplumber` (for agenda/minutes PDFs), `gspread` + `oauth2client` (Google Sheets)

Core flow
- Read `data/urls.csv` via `scraper.utils.read_urls_from_csv()`.
- For each URL, attempt CSS-based extraction using `JsonCssExtractionStrategy` with tuned selectors. If empty or unreliable, fallback to `LLMExtractionStrategy` with `MeetingSchema` Pydantic model.
- Extract and normalize the three text blobs (agenda/minutes/transcript) as available. If linked PDFs are present, optionally download and parse to text.
- Append standardized records to `data/meetings.jsonl` using `utils.append_jsonl()`.

Key modules & functions
- `scraper/utils.py`
  - `read_urls_from_csv(path="data/urls.csv")`
  - `append_jsonl(path, obj)`
  - `safe_mkdir(path)`
- `scraper/extractors.py`
  - `MEETING_TABLE_SCHEMA` for CSS table extraction
  - `extract_table_css(url)` returns dict with `meetingItems` and metadata
- `scraper/llm_schemas.py`
  - `MeetingItem`, `MeetingSchema` Pydantic models
- `scraper/llm_extractor.py`
  - `extract_with_llm(url, provider, api_token)` returning JSON for `MeetingSchema`
- `scraper/scrape.py`
  - CLI modes: single URL vs batch (`--batch data/urls.csv`)
  - Hybrid extraction logic: CSS-first, LLM fallback, merge results
  - Writes to JSONL and prints stats summary

Concurrency
- Use `AsyncWebCrawler.arun_many()` with `stream=True` to process multiple URLs concurrently. Respect rate limits & politeness.

Error handling & robustness
- Retries with exponential backoff on network errors.
- Cache/bypass modes via `CacheMode` during development.
- When a blob is missing, still write a record with `null` fields and provenance.
- Structured logging (JSON) and a `data/crawl_stats.json` summary with success/failure counts.

Acceptance for Scraper
- Run single URL: `python -m scraper.scrape "<url>"` prints markdown preview and writes 1 record.
- Run batch: `python -m scraper.scrape --batch data/urls.csv` writes ≥5 records.


### 3.2 RAG Database (Weaviate)

Deployment options
- Local via Docker or Weaviate Cloud. For speed, we can use Weaviate Cloud (requires `WEAVIATE_URL` + `WEAVIATE_API_KEY`) or local if Docker is pre-installed.

Using the provided Colab-based script
- This repo includes `ai_conference_hack_day_weaviate.py`, a local copy of the Colab notebook wiring up a Weaviate Cloud client and a simple near-text query. Use this as a reference for client setup. For our ingestion, we will:
  - Switch to our own class (`MeetingChunk`) and schema.
  - Use client-side embeddings (OpenAI) and set `vectorizer: none`.
  - Prefer `WEAVIATE_URL` (alias: `WEAVIATE_CLUSTER_URL`) and `WEAVIATE_API_KEY` from `.env`.
  - If `FRIENDLI_TOKEN` is present, include it as `X-Friendli-Token` header in Weaviate connections (mirrors the Colab script).

Embeddings provider
- Default: OpenAI `text-embedding-3-small` (fast, low-cost). Set `OPENAI_API_KEY`.
- Alternative: Cohere or AWS Bedrock (if available). Keep a provider abstraction.

Schema (store client-provided vectors; vectorizer = none)

```json
{
  "class": "MeetingChunk",
  "vectorizer": "none",
  "properties": [
    { "name": "meetingId",   "dataType": ["text"] },
    { "name": "url",         "dataType": ["text"] },
    { "name": "date",        "dataType": ["date"] },
    { "name": "source_type", "dataType": ["text"] },  // agenda | minutes | transcript
    { "name": "itemTitle",   "dataType": ["text"] },
    { "name": "content",     "dataType": ["text"] },
    { "name": "chunkIndex",  "dataType": ["int"] }
  ]
}
```

Chunking
- Split each text blob into ~800-token chunks with 200-token overlap.
- Keep per-chunk metadata: `meetingId`, `url`, `date`, `source_type`, `chunkIndex`.

Ingestion flow (`/ingest/ingest.py`)
- Read `data/meetings.jsonl`.
- For each meeting, for each non-null text blob (agenda/minutes/transcript):
  - Chunk → embed (`OpenAIEmbeddings.embed_documents`) → create Weaviate objects with vectors.
- Verify with a simple test query.

Retrieval
- Query Weaviate with user query embedding and `topK` (e.g., 5). Return content + metadata to the agent layer.

Acceptance for Weaviate
- Create schema successfully.
- After ingestion, a test query returns relevant chunks with correct `url` and `date`.


### 3.3 Agent (Strands Agents)

Reference
- Strands SDK docs: https://strandsagents.com/latest/documentation/docs/
- Install: `pip install strands-agents`
- Default model provider is AWS Bedrock (Claude 4 Sonnet, `us-west-2`). Requires AWS credentials and model access.

Provider choices
- Option A (default): AWS Bedrock (Claude 4 Sonnet). Requires `AWS_...` env vars and Bedrock model access enabled.
- Option B: Configure a different provider per Strands quickstart (e.g., OpenAI). Choose whichever is fastest to set up given available keys.

Bedrock setup for Strands (step-by-step)
1) Enable model access
   - In the AWS Console → Amazon Bedrock → Model access → Manage model access.
   - Enable access to “Claude 4 Sonnet” in region `us-west-2` (Oregon). Approval may take a few minutes.
2) Create credentials (IAM user or role)
   - For a hackathon, attach either `AmazonBedrockFullAccess` or the minimal permissions: `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`, and `bedrock:ListFoundationModels`.
3) Configure local credentials
   - Option A (env vars):
     - `AWS_ACCESS_KEY_ID=...`
     - `AWS_SECRET_ACCESS_KEY=...`
     - `AWS_DEFAULT_REGION=us-west-2`
   - Option B (AWS CLI):
     - Run `aws configure` and choose region `us-west-2`.
4) Verify Bedrock connectivity (sanity check)
   - Use a quick Python snippet with `boto3`:
     ```python
     import boto3
     bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")
     # Should not raise; optionally list models with the control-plane client
     ctrl = boto3.client("bedrock", region_name="us-west-2")
     print([m["modelId"] for m in ctrl.list_foundation_models()["modelSummaries"][:5]])
     ```
5) Run the Strands Agent
   - Strands defaults to Bedrock. With AWS creds configured and model access approved, a minimal agent should work out of the box:
     ```bash
     pip install strands-agents
     python - <<'PY'
     from strands import Agent
     agent = Agent()
     print(agent("Say hello from Bedrock via Strands"))
     PY
     ```
6) Switching providers (optional)
   - If Bedrock access is not yet enabled, follow the Strands quickstart to point to another provider. Keep embeddings on OpenAI for Weaviate as planned.

Design
- Build a Strands `Agent` with a custom "Weaviate retrieval" tool:
  - Input: `query` string, optional `date_from`, `date_to`, `source_type`, `top_k`.
  - Action: embed query → vector search in Weaviate → return top chunks with citations.
  - Output to the LLM: a context bundle comprising chunk texts + metadata (url/date/meetingId).
- System prompt should instruct the agent to:
  - Answer concisely from provided context only.
  - Include citations (meeting date + URL) inline or as a references list.
  - If insufficient context, say so and suggest follow-up filters.

Acceptance for Agent
- Running `python -u agent/agent.py` should allow asking: “What did the board say about housing policy?” and return an answer with at least one citation.


### 3.4 Frontend (stretch)
- Minimal HTML/React chat UI showing Q&A and clickable citations.
- Optional deployment to Vercel/Netlify.

---

## 4) Environment & Secrets

Python
- Create venv and install `requirements.txt`.

Environment variables (.env)
- `OPENAI_API_KEY` (embeddings and/or LLM extraction fallback)
- `WEAVIATE_URL`, `WEAVIATE_API_KEY` (alias: `WEAVIATE_CLUSTER_URL`)
- `STRANDS_MODEL_PROVIDER` (optional if deviating from default)
- If using Bedrock (Strands default): `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION=us-west-2` and ensure Claude 4 Sonnet access is enabled.
- Friendli + Opik demo (optional): `FRIENDLI_TOKEN`, `OPIK_PROJECT_NAME`, `OPIK_USE_LOCAL` (default `false`)

`requirements.txt` (union of scraper + ingest + agent)
- crawl4ai>=0.7.0
- aiohttp
- pydantic
- python-dateutil
- tqdm
- pandas
- beautifulsoup4
- lxml
- requests
- pdfplumber          # optional
- weaviate-client
- openai              # if using OpenAI embeddings / LLM
- strands-agents
- python-dotenv       # optional for local env loading

---

## 5) Milestones & Timebox (4 hours)

- Milestone 1 (≈45–60 min): Scraper MVP
  - Validate Crawl4AI on 1 URL, CSS extraction working.
  - Write ≥5 records into `data/meetings.jsonl`.

- Milestone 2 (≈45–60 min): Ingestion + Retrieval
  - Create Weaviate schema and ingest chunks with embeddings.
  - Verify a test query returns relevant chunks.

- Milestone 3 (≈60 min): Agent
  - Implement Strands agent with Weaviate retrieval tool.
  - Answer a question with citations.

- Stretch (≤60 min):
  - LLM extraction fallback integrated.
  - PDF parsing for agenda/minutes.
  - Simple UI and/or word cloud.

---

## 6) Testing & Validation

- Unit tests (optional given time):
  - `tests/test_utils.py`: CSV read/write.
  - `tests/test_extractors.py`: CSS extractor on sample HTML; mock LLM extraction output.
  - `tests/test_chunking.py`: chunk sizes and overlaps.
- Manual tests:
  - Spot-check 2–3 meeting pages for extraction accuracy.
  - Verify JSONL records match schema and have provenance.
  - Ingest and run a query; confirm citations.

Acceptance checklist
- [ ] `data/meetings.jsonl` has ≥5 valid records with at least one text blob each.
- [ ] Weaviate contains chunks; vector search returns relevant chunks.
- [ ] Agent answers “What did the board say about housing policy?” with citations.

---

## 7) Runbook

Setup
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Scraper
```
# Single URL
python -m scraper.scrape "https://example.com/meeting1"

# Batch from CSV
python -m scraper.scrape --batch data/urls.csv
```

Weaviate (if local; otherwise set `WEAVIATE_URL`/`WEAVIATE_API_KEY`)
- Ensure Weaviate is running (Docker or Cloud).
- Create schema in `ingest/ingest.py` if not exists.
- Ingest:
```
python -m ingest.ingest
```

Agent (Strands)
```
# Ensure credentials for model provider (Bedrock or OpenAI)
python -u agent/agent.py
```

Friendli + Opik demo (optional)
```
python -m demos.friendli_opik_demo --question "What did the board say about housing policy?" --top-k 3
```
This uses OpenAI embeddings, queries Weaviate with optional `X-Friendli-Token` header, calls Friendli Serverless for chat completions, and logs traces to Opik when configured.

---

## 8) Risks & Mitigations

- Page heterogeneity → CSS fails
  - Mitigation: LLM extraction fallback with deterministic settings (`temperature=0`).
- PDFs only for agenda/minutes
  - Mitigation: parse with `pdfplumber`; store text + provenance.
- Rate limits / dynamic content
  - Mitigation: throttling, `wait_for_network_idle`, caching where possible.
- Credentials friction (Bedrock access)
  - Mitigation: switch provider to OpenAI if Bedrock not enabled.

---

## 9) Open Questions & Assumptions

- Which provider do we prefer for embeddings/LLM at the event (OpenAI vs Cohere vs Bedrock)?
- Are transcript URLs available consistently, or only PDFs?
- Any filtering fields we should prioritize (e.g., file number, item type) for the first demo?

---

## 11) Process & Engineering Standards (applied)

- Planning & staging
  - Work is split into 3–5 stages in `IMPLEMENTATION_PLAN.md` with Goal, Success Criteria, Tests, and Status per stage. Update as you progress; remove the file when complete.
- Implementation flow
  - Understand → Test (write first when feasible) → Implement minimally → Refactor → Commit with clear message referencing the plan.
  - Prefer boring, obvious solutions. Single responsibility per function; avoid premature abstractions.
- When stuck (after 3 attempts)
  - Stop and document what failed; research 2–3 similar implementations; question assumptions; try a different angle.
- Code quality
  - Every commit compiles, tests pass, lints/formatters are clean. No disabling tests. Clear commit messages (explain why, not just what).
- Error handling
  - Fail fast with descriptive messages; include debugging context; handle errors at the right level; never silently swallow exceptions.
- Decision framework (tie-breakers)
  - Testability → Readability → Consistency → Simplicity → Reversibility.
- Tooling
  - Use existing build/test/lint tools; do not add new ones without strong justification.

This section summarizes and applies the workspace global rules at `.codeium/windsurf/memories/global_rules.md`.

---

## 12) Definition of Done (for this project)

- Tests written and passing (unit or integration as appropriate for scope/time).
- Code follows project conventions and directory layout.
- No linter/formatter warnings.
- Commit messages are clear and reference `IMPLEMENTATION_PLAN.md` stages.
- Matches the implementation plan’s goals and success criteria.
- No TODOs without linked issue numbers or explicit backlog entries.

---

## 13) Test Guidelines (applied)

- Test behavior, not implementation details.
- Aim for one assertion per test where practical; otherwise, keep tests focused.
- Clear, descriptive test names.
- Use existing helpers; keep tests deterministic (fix random seeds, avoid network in unit tests).
- For this hackathon:
  - Minimal unit tests for utilities (CSV read, chunking) and mocks for LLM extraction.
  - Manual validation for scraper output, ingestion, retrieval, and agent answers with citations.

---

## 10) References

- Local docs: `crawler-requirements.md`, `high-level-requirements.md`
- Local Weaviate Colab export: `ai_conference_hack_day_weaviate.py`
- Strands Agents: https://strandsagents.com/latest/documentation/docs/
- Weaviate Python client: https://weaviate.io/developers/weaviate/client-libraries/python

