# Implementation Plan — Ask SF Supes

This plan follows the global development guidelines. Update statuses as you progress. Remove this file when all stages are complete.

## Stage 0: Repo setup & docs update
**Goal**: Initialize repo structure, environment, requirements, and documentation. Apply global rules.
**Success Criteria**:
- Project skeleton present with scraper/ingest/agent modules.
- `.env` and `.gitignore` in place; secrets excluded from git.
- `detailed-requirements.md` updated with Bedrock setup and process standards.
**Tests**:
- Import sanity: `python -m scraper.scrape -h`, `python -m ingest.ingest -h`, `python -m agent.agent -h` run without ImportError.
**Status**: Complete

## Stage 1: Scraper MVP
**Goal**: Crawl 5–10 meeting URLs and write normalized records to `data/meetings.jsonl`.
**Success Criteria**:
- At least 5 records with `meetingId`, `url`, and at least one of `agenda_text`/`minutes_text`/`transcript_text`.
- `provenance.crawled_at` set for every record.
**Tests**:
- Unit: `read_urls_from_csv` with a temp CSV.
- Manual: Run single URL and batch CLI; verify JSONL lines are valid JSON and contain required fields.
**Status**: Not Started

## Stage 2: Ingestion & Retrieval (Weaviate)
**Goal**: Chunk + embed records and upsert into Weaviate; validate retrieval.
**Success Criteria**:
- Weaviate schema created with `vectorizer: none`.
- Ingest ≥50 chunks.
- Test query returns relevant chunks with `url` and `date`.
**Tests**:
- Manual: `python -m ingest.ingest --jsonl data/meetings.jsonl` then `--test-query "<question>"` prints top results with citations.
**Status**: Not Started

## Stage 3: Agent (Strands)
**Goal**: Answer user questions using retrieved context with citations.
**Success Criteria**:
- `python -m agent.agent --question "What did the board say about housing policy?"` returns an answer with at least one citation.
**Tests**:
- Manual: Ask a domain question and verify references include meeting date + URL.
**Status**: Not Started

## Stage 4: Robust extraction & PDFs (Stretch)
**Goal**: Add CSS-first + LLM fallback extraction and PDF parsing.
**Success Criteria**:
- Pages with heterogeneous layouts yield structured `meetingItems` via fallback.
- Agenda/minutes PDFs parsed on at least one record; `derived.pdfs_parsed` shows source link.
**Tests**:
- Unit: Mock LLM extraction; CSS extractor against sample HTML.
- Manual: Run scraper on a known PDF page and verify text extraction.
**Status**: Not Started

## Stage 5: Frontend & Demo Polish (Stretch)
**Goal**: Minimal chat UI and optional visualization (word cloud).
**Success Criteria**:
- Chat interface invokes agent and shows answers + clickable citations.
- Word cloud generated from `agenda_text` for one meeting.
**Tests**:
- Manual: Launch frontend, ask a question, click citations, display word cloud image.
**Status**: Not Started
