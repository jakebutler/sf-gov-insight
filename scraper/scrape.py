"""Scraper CLI: reads URLs and writes normalized JSONL records.

MVP behavior:
- Supports single URL or batch mode via --batch.
- Uses placeholder extraction that you can later replace with CSS and/or LLM extractors.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Optional

import pdfplumber
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from scraper import extractors
from scraper.utils import append_jsonl, generate_meeting_id, read_urls_from_csv


def _fetch_markdown(url: str) -> str | None:
    """Fetch page markdown via Crawl4AI; return None on failure."""
    try:
        from crawl4ai import AsyncWebCrawler  # lazy import to keep CLI usable
    except Exception:
        return None

    import asyncio

    async def _run() -> str | None:
        try:
            async with AsyncWebCrawler() as crawler:
                res = await crawler.arun(url)
                if res and res.markdown and getattr(res.markdown, "raw_markdown", None):
                    return res.markdown.raw_markdown
        except Exception:
            return None
        return None

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # In case an event loop is already running (unlikely in CLI), create a new loop
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_run())
        finally:
            loop.close()


def _normalize_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    # Replace non-breaking spaces and collapse repeated whitespace
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\u200b\ufeff]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def _fetch_html_text(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        txt = soup.get_text("\n")
        return _normalize_text(txt)
    except Exception:
        return None


def _fetch_pdf_text(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        resp.raise_for_status()
        bio = BytesIO(resp.content)
        parts = []
        with pdfplumber.open(bio) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t:
                    parts.append(t)
        return _normalize_text("\n\n".join(parts))
    except Exception:
        return None


def _fetch_url_text_auto(url: str) -> Optional[str]:
    """Detect content type and fetch text accordingly (PDF vs HTML)."""
    try:
        head = requests.head(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
            allow_redirects=True,
        )
        ctype = head.headers.get("Content-Type", "").lower()
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            return _fetch_pdf_text(url)
    except Exception:
        # Fallback to GET below
        pass
    # Try HTML fetch as default
    text = _fetch_html_text(url)
    if text:
        return text
    # If html fetch failed, try pdf fetch as last resort
    return _fetch_pdf_text(url)


def _normalize_meeting_date(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    try:
        dt = dateparser.parse(raw, dayfirst=False, yearfirst=False, fuzzy=True)
        # Only keep date component
        return dt.date().isoformat()
    except Exception:
        return raw


def extract_page(url: str, row: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Placeholder extraction that returns a minimal standardized record.

    Now attempts CSS-first extraction for meetingItems and merges into the record.
    LLM fallback can be added in a next iteration.
    """
    record: Dict[str, Any] = {
        "meetingId": generate_meeting_id(),
        "meetingName": None,
        "meetingDate": _normalize_meeting_date((row or {}).get("meeting_date") if row else None),
        "meetingLocation": None,
        "url": url,
        "metadata": {
            # Persist source URLs for better citations downstream
            "agenda_url": (row or {}).get("agenda_url") if row else None,
            "minutes_url": (row or {}).get("minutes_url") if row else None,
            "transcript_url": (row or {}).get("transcript_url") if row else None,
            "meeting_date_raw": (row or {}).get("meeting_date") if row else None,
        },
        "meetingItems": [],
        "agenda_text": None,
        "minutes_text": None,
        "transcript_text": None,
        "derived": {},
        "provenance": {
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "crawler_version": "placeholder-0.1",
            "raw_html_path": None,
        },
    }
    # CSS-first extraction for meetingItems (best-effort)
    try:
        css_result = extractors.extract_table_css(url)
        if isinstance(css_result, dict):
            # Common shapes: { "meetingItems": [...] } or "data": { "meetingItems": [...] }
            items = (
                css_result.get("meetingItems")
                or (css_result.get("data") or {}).get("meetingItems")
            )
            if items:
                record["meetingItems"] = items
    except Exception:
        # Graceful fallback; keep placeholder record
        pass

    # Populate agenda/minutes/transcript from row-specific URLs if available
    if row:
        turl = row.get("transcript_url")
        aurl = row.get("agenda_url")
        murl = row.get("minutes_url")
        if turl and not record["transcript_text"]:
            record["transcript_text"] = _fetch_url_text_auto(turl) or _fetch_html_text(turl)
        if aurl and not record["agenda_text"]:
            record["agenda_text"] = _fetch_url_text_auto(aurl)
        if murl and not record["minutes_text"]:
            record["minutes_text"] = _fetch_url_text_auto(murl)

    # Markdown fallback for meeting page content if still empty
    if not record["agenda_text"] and not record["minutes_text"] and not record["transcript_text"]:
        md = _fetch_markdown(url)
        if md:
            record["agenda_text"] = md

    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="SF Supes Scraper")
    parser.add_argument("url", nargs="?", help="Single URL to scrape")
    parser.add_argument("--batch", help="Path to CSV with a 'url' column")
    parser.add_argument("--out", default="data/meetings.jsonl", help="Output JSONL path")
    args = parser.parse_args()

    if not args.url and not args.batch:
        parser.error("Provide either a single URL or --batch <csv>")

    if args.url:
        rec = extract_page(args.url)
        append_jsonl(args.out, rec)
        print("[OK] wrote one record to", args.out)
        return

    # Batch mode
    rows = read_urls_from_csv(args.batch)
    ok = 0
    for r in rows:
        url = r.get("url")
        if not url:
            continue
        try:
            rec = extract_page(url, row=r)
            append_jsonl(args.out, rec)
            ok += 1
            print("[OK]", url)
        except Exception as e:
            print("[ERR]", url, e)
    print(f"Done. Wrote {ok} records to {args.out}")


if __name__ == "__main__":
    main()
