#!/usr/bin/env python3
# Trigger: Stop
"""Warn at session end if code changed but no recent Codex review marker.

Fail-open. Always exits 0. §11-3 정책에 따라 차단하지 않는다.

검출 범위:
  - CODE_PATHS 의 워킹트리 변경 (기본: src/, tests/ — 프로젝트별로 조정)
  - 같은 경로를 건드린 origin/main 대비 unpushed 커밋

발화 조건 (모두 충족):
  1) 위 경로에 변경이 있다
  2) 변경 합산 LOC ≥ THRESHOLD (한 줄 typo는 면제)
  3) `.codex_review_head` 마커가 없거나 현재 HEAD와 다르다

리뷰 후 마커 갱신:
  git rev-parse HEAD > .codex_review_head
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CODE_PATHS = ("src", "tests")
MARKER = REPO / ".codex_review_head"
LOC_THRESHOLD = 5


def run(*args: str) -> str:
    out = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    return out.stdout


def has_remote_main() -> bool:
    out = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "origin/main"],
        cwd=REPO,
        capture_output=True,
    )
    return out.returncode == 0


def parse_loc(shortstat: str) -> int:
    total = 0
    for part in shortstat.split(","):
        part = part.strip()
        if "insertion" in part or "deletion" in part:
            try:
                total += int(part.split()[0])
            except ValueError:
                pass
    return total


def main() -> int:
    dirty = bool(run("git", "status", "--porcelain", "--", *CODE_PATHS).strip())
    unpushed = False
    if has_remote_main():
        unpushed = bool(
            run("git", "log", "origin/main..HEAD", "--oneline", "--", *CODE_PATHS).strip()
        )
    if not (dirty or unpushed):
        return 0

    loc = parse_loc(run("git", "diff", "HEAD", "--shortstat", "--", *CODE_PATHS))
    if unpushed:
        loc += parse_loc(
            run("git", "diff", "origin/main..HEAD", "--shortstat", "--", *CODE_PATHS)
        )
    if loc < LOC_THRESHOLD:
        return 0

    head = run("git", "rev-parse", "HEAD").strip()
    if MARKER.exists() and MARKER.read_text(encoding="utf-8").strip() == head:
        return 0

    paths_label = "/".join(CODE_PATHS)
    print(
        f"warn[codex-review]: {paths_label} changed (~{loc} LOC) but HEAD={head[:7]} "
        "has no review marker. Run `/codex:review`, then "
        "`git rev-parse HEAD > .codex_review_head` to silence this warning.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
