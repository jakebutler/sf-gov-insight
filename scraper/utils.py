import csv
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from uuid import uuid4
from datetime import datetime, timezone


def safe_mkdir(path: str | Path) -> None:
    """Create a directory if it does not already exist."""
    Path(path).mkdir(parents=True, exist_ok=True)


def _pick_primary_url(row: Dict[str, str], fieldnames: List[str]) -> Optional[str]:
    """Pick a primary URL from common field names, preferring meeting details."""
    preferred_order = [
        "url",
        "URL",
        "Url",
        "Link",
        "link",
        "Meeting Details URL",
        "Agenda URL",
        "Minutes URL",
        "Transcript URL",
    ]
    for key in preferred_order:
        if key in fieldnames and row.get(key):
            return row.get(key)
    return None


def read_urls_from_csv(path: str = "data/urls.csv") -> List[Dict[str, str]]:
    """Read rows from a CSV, normalizing each row to include a 'url' key.

    Accepts common header variations like 'Meeting Details URL', 'Agenda URL', etc.
    Returns list of dicts; raises ValueError if no viable URL columns are present.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise ValueError(f"CSV file not found at {csv_path!s}")
    rows: List[Dict[str, str]] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("CSV must have a header row")
        for r in reader:
            # Normalize: ensure 'url' exists using preferred columns
            primary = _pick_primary_url(r, reader.fieldnames)
            if not primary:
                # Skip rows without any usable URL
                continue
            r = dict(r)
            r.setdefault("url", primary)
            # Normalize meeting date if present
            if "Meeting date" in reader.fieldnames and r.get("Meeting date"):
                r.setdefault("meeting_date", r.get("Meeting date"))
            # Normalize additional URLs
            if "Agenda URL" in reader.fieldnames and r.get("Agenda URL"):
                r.setdefault("agenda_url", r.get("Agenda URL"))
            if "Minutes URL" in reader.fieldnames and r.get("Minutes URL"):
                r.setdefault("minutes_url", r.get("Minutes URL"))
            if "Transcript URL" in reader.fieldnames and r.get("Transcript URL"):
                r.setdefault("transcript_url", r.get("Transcript URL"))
            rows.append(r)
    return rows


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    """Append a JSON object to a JSONL file, creating directories if needed."""
    out_path = Path(path)
    safe_mkdir(out_path.parent)
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def generate_meeting_id(prefix: str = "supes") -> str:
    """Generate a unique meeting id with a prefix and ISO date."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{ts}-{uuid4()}"
