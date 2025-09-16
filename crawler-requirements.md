crawler-requirements.md

Purpose: a precise, step-by-step requirements + implementation guide (with code examples and AI-assistant prompts) to build a Crawl4AI-based scraper that reads your spreadsheet of SF Board of Supervisors URLs, extracts structured meeting data and text blobs (agenda / minutes / transcript), and writes standardized JSONL output ready for ingestion into a RAG pipeline (Weaviate). Uses the Crawl4AI Python API (AsyncWebCrawler). References: Crawl4AI Quickstart & Simple Crawling.  ￼

⸻

Table of contents
	1.	Goals & success criteria
	2.	Input data (spreadsheet)
	3.	Target data model (JSON schema + examples)
	4.	High-level architecture & files
	5.	Step-by-step implementation plan (with code)
	•	env & deps
	•	two ingestion modes: CSV-export (recommended) and Google Sheets API (optional)
	•	crawl loop: single-URL and multi-URL (concurrent)
	•	extraction strategies: CSS-based, LLM-assisted, and hybrid
	•	output & validation
	6.	Edge cases, error handling & operational notes
	7.	Prompts for the Windsurf AI coding assistant (detailed tasks)
	8.	Quick runbook (how to run locally)
	9.	Test checklist & demo script

⸻

1 — Goals & success criteria
	•	Read the list of target meeting URLs (you already have them in a Google Sheet).  ￼
	•	For each URL: crawl the page, extract structured metadata (meeting items table), and capture three text blobs (agenda, minutes, transcript) where present.
	•	Produce one newline-delimited JSON file (data/meetings.jsonl) where each record adheres to the project JSON schema (see below).
	•	Output must include provenance metadata: url, crawled_at, and optionally source_html (or local cached file) per page.
	•	Be robust enough to handle dynamic pages, PDFs, and pages missing one or more text blobs.
	•	Keep the code modular so Windsurf AI can generate strong unit tests and iterate fast.

⸻

2 — Input data (spreadsheet)

You provided a Google Sheet with the URLs and extra metadata. Two practical ingestion paths:

A. Export CSV (recommended for hackathon): Export the relevant sheet as urls.csv and place in /data/urls.csv. This avoids OAuth complexity during a 4-hour sprint.

B. Google Sheets API: Use gspread + service-account JSON. Included below as an optional helper.

Spreadsheet link (for reference): the sheet you supplied.  ￼

⸻

3 — Target data model

Below is the standard JSON structure each scraped meeting should produce. Keep fields stable — this is what you will index into Weaviate later.

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
    "status": "Approved",
    "...": "any other table columns"
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
        {
          "label": "agenda pdf",
          "url": "https://....pdf",
          "file_type": "pdf"
        }
      ]
    }
  ],

  "agenda_text": "<raw or cleaned agenda text (string)>",
  "minutes_text": "<raw minutes text>",
  "transcript_text": "<raw transcript text>",

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

Notes & choices
	•	agenda_text, minutes_text, transcript_text are each single text blobs. This is simple and useful for RAG. If you want more finesse later, you can also store chunks (split by time or speaker) — but keep core simple for 4-hour sprint.
	•	meetingItems stores the tabular details from your spreadsheet or the page table. These are useful for filtering queries later (e.g., filter by agenda item / file #).
	•	derived is for light NLP extraction (speaker list, counts). Useful for visualizations.

⸻

4 — High-level architecture & files

/supes-scraper
  /data
    urls.csv                 # exported from your spreadsheet
    meetings.jsonl           # final output
    raw/                     # optional: local cached HTML/PDFs
  /scraper
    scrape.py                # main crawl driver
    extractors.py            # extraction utilities, css schemas
    llm_schemas.py           # pydantic models for LLM-based extraction
    utils.py                 # helpers: logging, file i/o, chunking, parse_date
  requirements.txt
  README.md


⸻

5 — Step-by-step implementation plan (with code)

A — Environment & dependencies

Create requirements.txt with (minimum):

crawl4ai>=0.7.0
aiohttp
pydantic
python-dateutil
tqdm
pandas
beautifulsoup4
lxml
requests
pdfplumber    # optional, for PDFs
gspread       # optional if you use Google Sheets API
oauth2client  # optional

Install:

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

B — Utility: read URLs (CSV recommended)

/scraper/utils.py (snippet)

import csv
from pathlib import Path

def read_urls_from_csv(path="data/urls.csv"):
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
    return rows

If you prefer Google Sheets (optional), put sheets_reader.py but skip OAuth for speed in hackathon.

C — Minimal single-URL crawl (Crawl4AI quickstart)

/scraper/scrape.py — minimal example that prints markdown:

import asyncio
from crawl4ai import AsyncWebCrawler

async def crawl_single(url):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url)
        print("MARKDOWN:", result.markdown.raw_markdown[:1000])
        return result

if __name__ == "__main__":
    import sys
    url = sys.argv[1]
    asyncio.run(crawl_single(url))

Reference: Quick Start.  ￼

D — CSS-based table extraction (fast, deterministic)

Use JsonCssExtractionStrategy. Example extractor for the meeting items table:

/scraper/extractors.py

import asyncio, json
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai import JsonCssExtractionStrategy

MEETING_TABLE_SCHEMA = {
  "name": "meetingItems",
  "baseSelector": "table.meeting-items tr",   # adjust to real selector
  "fields": [
    {"name": "fileNumber", "selector": "td.file-number", "type": "text"},
    {"name": "ver", "selector": "td.ver", "type": "text"},
    {"name": "agendaNumber", "selector": "td.agenda-number", "type": "text"},
    {"name": "name", "selector": "td.name", "type": "text"},
    {"name": "type", "selector": "td.type", "type": "text"},
    {"name": "status", "selector": "td.status", "type": "text"},
    {"name": "title", "selector": "td.title", "type": "text"}
  ]
}

async def extract_table(url):
    async with AsyncWebCrawler() as crawler:
        config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS,
                                  extraction_strategy=JsonCssExtractionStrategy(MEETING_TABLE_SCHEMA))
        res = await crawler.arun(url=url, config=config)
        extracted = json.loads(res.extracted_content)
        return extracted

Important: you will need to inspect a few real pages to find correct CSS selectors. If the pages vary, the LLM-assisted approach below is recommended.

E — LLM-assisted extraction (recommended for messy pages)

When pages are inconsistent, use LLMExtractionStrategy to map page content into a Pydantic model. This is extremely helpful for meeting pages where the structure changes between meetings. Crawl4AI docs show using LLMExtractionStrategy with Pydantic schema.  ￼

Example Pydantic model and LLM extraction (in llm_schemas.py):

from pydantic import BaseModel, Field
from typing import List, Optional

class MeetingItem(BaseModel):
    itemIndex: Optional[int]
    fileNumber: Optional[str]
    ver: Optional[str]
    agendaNumber: Optional[str]
    name: Optional[str]
    type: Optional[str]
    status: Optional[str]
    title: Optional[str]
    details: Optional[str]

class MeetingSchema(BaseModel):
    meetingName: Optional[str]
    meetingDate: Optional[str]
    meetingLocation: Optional[str]
    meetingItems: List[MeetingItem] = []
    agenda_text: Optional[str]
    minutes_text: Optional[str]
    transcript_text: Optional[str]

LLM extraction driver (snippet):

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig, LLMExtractionStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from llm_schemas import MeetingSchema

async def extract_with_llm(url, provider="openai/gpt-4o", api_token=None):
    browser_conf = BrowserConfig(headless=True)
    md_gen = DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.4))
    run_conf = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=md_gen,
        extraction_strategy=LLMExtractionStrategy(
            llm_config=LLMConfig(provider=provider, api_token=api_token),
            schema=MeetingSchema.model_json_schema(),
            extraction_type="schema",
            instruction="""Extract meeting metadata including meeting name, meeting date and location.
            For agenda/minutes/transcript fields, return the full text blocks if present. 
            For meetingItems return an array of items with fileNumber, title, type, status if found.""",
            extra_args={"temperature": 0, "max_tokens": 1500}
        )
    )
    async with AsyncWebCrawler(config=browser_conf) as crawler:
        res = await crawler.arun(url=url, config=run_conf)
        return res.extracted_content  # JSON string

Tip: For extraction you will have to pass your OpenAI API key (or use an open-source model such as Ollama if available). When using OpenAI, put temperature=0 to maximize deterministic extraction.

F — Combined (hybrid) strategy
	1.	Try JsonCssExtractionStrategy first for speed and zero-cost extraction.
	2.	If CSS extraction yields no rows (or the page looks inconsistent), fallback to LLMExtractionStrategy for robust parsing.

G — Multi-URL concurrency

Use arun_many() to stream results in parallel. Example:

urls = [r["url"] for r in read_urls_from_csv("data/urls.csv")]

run_conf = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, stream=True)
async with AsyncWebCrawler() as crawler:
    async for result in await crawler.arun_many(urls, config=run_conf):
        if result.success:
            # process result
        else:
            # log error

H — Output JSONL writer

/scraper/utils.py append function:

import json

def append_jsonl(path, obj):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")

I — PDF handling and attachments
	•	If the page links to PDFs (agenda/minutes), download them and extract text with pdfplumber or pypdf. Store attachments metadata and optionally parsed text into derived.pdfs_parsed.
	•	Crawl4AI docs include file downloading hooks—see advanced docs if you want automated downloading.  ￼

⸻

6 — Edge cases, error handling & operational notes
	•	Rate-limits & politeness: Crawl4AI uses a headless browser; for bulk crawling respect server resources and add a short delay between requests when crawling many pages. Use CacheMode to avoid re-downloads during dev.  ￼
	•	Dynamic pages: Set BrowserConfig(headless=True, wait_for_network_idle=True) or use the Playwright options if needed.
	•	Character encoding: Normalize to UTF-8 and replace control characters.
	•	Partial pages: If transcript_text missing, still write a record with null value and provenance.crawled_at.
	•	Retries: Implement exponential backoff for network errors.
	•	Logging: Use structured logs (JSON) and a summary stats file (data/crawl_stats.json) with counts of successes/failures.

⸻

7 — Prompts for the Windsurf AI coding assistant

Below are explicit prompts you can paste into Windsurf so the coding assistant will write the code files for you. Use them as tasks.

Task A — Project skeleton

Task: Create the project skeleton for supes-scraper.
Files to create:
- requirements.txt (with minimal deps)
- scraper/__init__.py
- scraper/utils.py (include read_urls_from_csv, append_jsonl, safe_mkdir)
- scraper/extractors.py (placeholder)
- scraper/llm_schemas.py (pydantic models)
- scraper/scrape.py (main runner)
- data/.gitkeep
Write runnable code and include docstrings. Ensure relative imports work.

Task B — CSV reader + run CLI

Task: Implement scraper/scrape.py that:
- reads urls.csv via scraper.utils.read_urls_from_csv
- supports two CLI modes: single (url) or batch (reads csv)
- for each url: calls a function extract_page(url) (implement an empty function that returns a dict for now)
- writes results into data/meetings.jsonl using utils.append_jsonl
- prints progress and prints a final stats summary

Task C — Css extractor + example schema

Task: Implement scraper/extractors.py with:
- MEETING_TABLE_SCHEMA (as shown in the crawler-requirements spec)
- function extract_table_css(url) that uses JsonCssExtractionStrategy and returns Python dict
- add clear error handling and docstrings

Task D — LLM extraction function

Task: Implement scraper/llm_extractor.py that:
- defines the MeetingSchema Pydantic model in llm_schemas.py
- defines function extract_with_llm(url, provider, api_token) that uses LLMExtractionStrategy to return parsed JSON
- includes sensible default extra_args (temperature=0, max_tokens=1500)
- ensures deterministic extraction

Task E — Integrate the two extractors

Task: Modify scraper/scrape.py to:
- for each url: try extract_table_css(url)
- if result is empty or missing meetingItems: fallback to extract_with_llm(url)
- merge CSS and LLM outputs (CSS overrides if more complete)
- return the final standardized dict matching the JSON schema
- write the dict to data/meetings.jsonl

Task F — Unit tests (optional but valuable)

Task: Add tests in tests/test_extractors.py:
- test_read_urls_from_csv: uses a temp csv
- test_css_extraction_on_sample_html: use raw://html string via crawler to test JsonCssExtractionStrategy
- test_llm_extraction_mocked: mock LLMExtractionStrategy output


⸻

8 — Quick runbook (how to run locally)
	1.	Export your Google Sheet as data/urls.csv (File → Download → Comma-separated values). Put it at project root data/urls.csv.
	2.	Create venv, install requirements:

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt


	3.	Run a single URL:

python -m scraper.scrape "https://example.com/meeting1"


	4.	Run batch:

python -m scraper.scrape --batch data/urls.csv


	5.	Check data/meetings.jsonl for results.

⸻

9 — Test checklist & demo script

Before the hackathon demo, ensure:
	•	data/meetings.jsonl has at least 5 successful records with agenda_text and meetingItems.
	•	For one meeting, download & parse the agenda PDF and show derived.pdfs_parsed.
	•	The runner prints a compact summary: total URLs, successes, failures, time elapsed.
	•	One sample record is converted to Markdown or displayed nicely for the frontend demo.

Demo script (30–60s):
	•	Show CSV with URLs → run the scraper → display a sample JSON record → show a short query in the frontend that uses the agenda_text and meetingItems. If you complete the stretch, show a word cloud from agenda_text.

⸻

Example: end-to-end minimal script (put in scraper/quick_run.py)

This is a copy-paste runnable sample integrating the pieces (very small, for hackathon):

# scraper/quick_run.py
import asyncio, json
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai import JsonCssExtractionStrategy
from scraper.utils import read_urls_from_csv, append_jsonl

SIMPLE_SCHEMA = {
  "name": "meetingItems",
  "baseSelector": "table.meeting-items tr",
  "fields": [
    {"name": "title", "selector": "td.title", "type": "text"},
    {"name": "fileNumber", "selector": "td.file", "type": "text"}
  ]
}

async def run_one(url):
    async with AsyncWebCrawler() as crawler:
        config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS,
                                  extraction_strategy=JsonCssExtractionStrategy(SIMPLE_SCHEMA))
        res = await crawler.arun(url=url, config=config)
        out = {"url": url, "raw": res.markdown.raw_markdown[:1000]}
        if res.extracted_content:
            out["extracted"] = json.loads(res.extracted_content)
        return out

async def main():
    rows = read_urls_from_csv("data/urls.csv")
    urls = [r["url"] for r in rows][:10]
    for url in urls:
        try:
            out = await run_one(url)
            append_jsonl("data/meetings.jsonl", out)
            print("[OK]", url)
        except Exception as e:
            print("[ERR]", url, e)

if __name__ == "__main__":
    asyncio.run(main())


⸻

Final notes & recommended priorities for the 4-hour hackathon

MVP (first 2–2.5 hours)
	1.	Export CSV, wire up scrape.py to perform single-page crawl and print markdown (validate crawl4ai access).  ￼
	2.	Implement CSS extraction for the obvious cases (meeting items table).
	3.	Output to data/meetings.jsonl for a handful (5–10) meetings.

Stretch (last 1.5 hours)
	•	Add LLM extraction fallback for messy pages.
	•	Add PDF parsing for agenda/minutes attachments.
	•	Add a small visual: word cloud script that reads agenda_text.
