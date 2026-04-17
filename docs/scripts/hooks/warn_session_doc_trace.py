#!/usr/bin/env python3
# Trigger: Stop
"""Warn on session end if src/ changed but no plan-task/catalog change is staged.

Fail-open. Always exits 0.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def changed(*pathspecs: str) -> bool:
    args = ["git", "status", "--porcelain", "--", *pathspecs]
    out = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    return bool(out.stdout.strip())


def main() -> int:
    if not changed("src"):
        return 0
    if changed("docs/plan-task", "docs/catalog"):
        return 0
    print(
        "warn[doc-trace]: src/ changed but no docs/plan-task or docs/catalog change. "
        "If non-trivial, run docs/scripts/new_task.py; if trivial (§3-1), run docs/scripts/new_catalog.py.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
