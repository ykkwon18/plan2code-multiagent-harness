#!/usr/bin/env python3
# Trigger: PostToolUse(Bash) matcher: "git commit"
"""Warn after `git commit` if the most recent commit message has no `Task:` line.

Fail-open. Always exits 0.

§7-2: 모든 커밋 메시지에 `Task: <id>` 라인을 포함해야 한다.
§11-3: 결정적 탐지 + 잊기 쉬움 + fail-open 경고 — 도입 기준 모두 통과.

이 훅은 PostToolUse(Bash)로 작동하지만, Bash 명령이 git commit이 아닐 때는
조용히 종료한다. tool_input.command 검사는 Claude Code가 stdin으로 JSON을
넘겨주는 형태에 의존한다 — 다른 호출 컨텍스트에서는 fallback으로 단순히
HEAD 커밋만 본다.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b")


def main() -> int:
    # PostToolUse 호출 시 stdin으로 JSON 페이로드가 옴
    payload_text = ""
    try:
        if not sys.stdin.isatty():
            payload_text = sys.stdin.read()
    except Exception:
        pass

    is_git_commit = True
    if payload_text:
        try:
            payload = json.loads(payload_text)
            cmd = payload.get("tool_input", {}).get("command", "")
            is_git_commit = bool(GIT_COMMIT_RE.search(cmd))
        except Exception:
            pass

    if not is_git_commit:
        return 0

    out = subprocess.run(
        ["git", "log", "-1", "--format=%H%n%B"],
        cwd=REPO, capture_output=True, text=True,
    )
    if out.returncode != 0:
        return 0
    lines = out.stdout.splitlines()
    if not lines:
        return 0
    head_hash = lines[0][:7]
    body = "\n".join(lines[1:])

    if re.search(r"^Task:\s*\S", body, re.MULTILINE):
        return 0

    print(
        f"warn[missing-task-tag]: HEAD={head_hash} 커밋 메시지에 `Task: <id>` 라인이 없습니다. "
        "§7-2 규칙. 이 커밋의 변경은 attribution(grep 기반)에서 silently 빠집니다. "
        "필요하면 `git commit --amend`로 추가하세요.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
