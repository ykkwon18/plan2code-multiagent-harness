"""Minimal frontmatter helpers shared by workflow scripts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DELIM = "---"


def split(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith(DELIM):
        return {}, text
    end = text.find(f"\n{DELIM}", len(DELIM))
    if end < 0:
        return {}, text
    raw = text[len(DELIM) : end].strip("\n")
    body = text[end + len(DELIM) + 1 :]
    body = body.lstrip("\n")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter root must be a mapping")
    return data, body


def join(data: dict[str, Any], body: str) -> str:
    raw = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip("\n")
    return f"{DELIM}\n{raw}\n{DELIM}\n\n{body.lstrip(chr(10))}"


def read(path: Path) -> tuple[dict[str, Any], str]:
    return split(path.read_text(encoding="utf-8"))


def write(path: Path, data: dict[str, Any], body: str) -> None:
    path.write_text(join(data, body), encoding="utf-8")
