#!/usr/bin/env python3
# Trigger: PreToolUse(Bash)
"""Warn when a Bash tool call tries to manually `git mv` plan-task → catalog.

Reads Claude Code hook JSON from stdin. Fail-open: always exits 0.
"""

from __future__ import annotations

import json
import re
import sys

PATTERN = re.compile(r"\bgit\s+mv\b.*plan-task.*catalog", re.IGNORECASE)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "")
    if PATTERN.search(cmd):
        print(
            "warn[manual-mv]: detected manual `git mv plan-task ... catalog`. "
            "Use scripts/close_task.py instead — it runs the preflight validation "
            "and finalizes frontmatter consistently.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
