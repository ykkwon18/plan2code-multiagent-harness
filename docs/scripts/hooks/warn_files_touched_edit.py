#!/usr/bin/env python3
# Trigger: PreToolUse(Edit|Write)
"""Warn when an Edit/Write touches files_touched: in a catalog file.

Fail-open. Always exits 0.
"""

from __future__ import annotations

import json
import sys

CATALOG_PREFIX = "docs/catalog/"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if CATALOG_PREFIX not in path:
        return 0
    blob = " ".join(
        str(tool_input.get(k, "")) for k in ("new_string", "content", "old_string")
    )
    if "files_touched" in blob:
        print(
            "warn[files-touched]: editing catalog files_touched is forbidden by §6-3 "
            "(frozen after close_task.py). If you really need to fix it, justify in PR.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
