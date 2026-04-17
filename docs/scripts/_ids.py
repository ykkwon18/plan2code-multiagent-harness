"""ID generation helpers — YYYY-MM-DD_NN_<slug>."""

from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

ID_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{2})_([a-z0-9-]+)$")
SLUG_OK = re.compile(r"[^a-z0-9]+")

DOCS = Path(__file__).resolve().parent.parent
REPO = DOCS.parent
PLAN = DOCS / "plan-task"
CATALOG = DOCS / "catalog"


def slugify(raw: str) -> str:
    s = SLUG_OK.sub("-", raw.lower()).strip("-")
    if not s:
        raise ValueError("slug must contain at least one alphanumeric character")
    return s


def next_id(slug: str, search_dirs: list[Path], today: str | None = None) -> str:
    """Pick the next NN for today across the given dirs."""
    today = today or date.today().isoformat()
    used: set[int] = set()
    for d in search_dirs:
        if not d.exists():
            continue
        for entry in d.iterdir():
            name = entry.stem if entry.is_file() else entry.name
            m = ID_RE.match(name)
            if m and m.group(1) == today:
                used.add(int(m.group(2)))
    nn = 1
    while nn in used:
        nn += 1
    return f"{today}_{nn:02d}_{slug}"


def head_commit(short: bool = True) -> str:
    args = ["git", "rev-parse", "HEAD"]
    if short:
        args = ["git", "rev-parse", "--short", "HEAD"]
    return subprocess.check_output(args, cwd=REPO, text=True).strip()
