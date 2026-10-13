"""Append-only audit trail for the Campus Customs team (CC-OPS-31).

One JSON object per line in output/audit_trail.json. JSONL rather than a single
JSON array for one reason that matters: a run can append without reading,
rewriting, or risking truncation of everything written before it. The file is
opened in append mode and never in write mode, anywhere in this project.

The schema extends the one HW 3 established for this shop, so both homeworks'
trails can be read with the same tooling.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.config import AUDIT_PATH, MAX_TRACE_CHARS

_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def prompt_version(text: str) -> str:
    """Short stable hash of a prompt, so a trail says which prompt produced it."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def clip(value: Any, limit: int = MAX_TRACE_CHARS) -> str:
    """Shorten a value for the trail (CC-OPS-30), marking what was cut."""
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… [+{len(text) - limit} chars]"


def append(entry: dict, path: Path | None = None) -> None:
    """Append one record. Never truncates; creates the file if missing."""
    target = Path(path or AUDIT_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, default=str, ensure_ascii=False)
    with _lock:
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def read_all(path: Path | None = None) -> list[dict]:
    """Read the trail back. Tolerates a trailing partial line."""
    target = Path(path or AUDIT_PATH)
    if not target.exists():
        return []
    out = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out
