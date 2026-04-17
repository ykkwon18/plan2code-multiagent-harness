#!/usr/bin/env python3
"""Create a new plan-task file from the template.

Plan-task 자체를 끝에 `git add`로 stage한다 — close_task가 untracked fallback을
폐기했기 때문에 plan-task가 git에 들어와 있는 게 전제다. 사용자가 별도 커밋만
하면 plan-task가 history에 안전하게 들어간다.

Usage: .venv/bin/python docs/scripts/new_task.py <slug> [--title "..."]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fm import read, write  # noqa: E402
from _ids import CATALOG, DOCS, PLAN, head_commit, next_id, slugify  # noqa: E402

TEMPLATE = DOCS / "templates" / "plan-task.md"
REPO = DOCS.parent


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("slug", help="kebab-case slug, e.g. auth-session-refactor")
    p.add_argument("--title", default=None)
    args = p.parse_args()

    slug = slugify(args.slug)
    task_id = next_id(slug, [PLAN, CATALOG])
    target = PLAN / f"{task_id}.md"
    if target.exists():
        print(f"refusing to overwrite {target}", file=sys.stderr)
        return 1

    data, body = read(TEMPLATE)
    data["id"] = task_id
    data["title"] = args.title or slug.replace("-", " ")
    data["status"] = "active"
    data["started_at"] = date.today().isoformat()
    data["base_commit"] = head_commit()

    PLAN.mkdir(parents=True, exist_ok=True)
    write(target, data, body)
    subprocess.check_call(["git", "add", str(target)], cwd=REPO)
    print(target)
    print(
        f"REMINDER: plan-task가 staged 상태입니다. 첫 작업 커밋에 함께 묶어"
        f" `Task: {task_id}` 라인을 포함해 커밋하세요.\n"
        f"          review lane이 기본값 — 생략하려면 유저 동의 먼저."
        f" 상세: docs/plan-review-methodology.md",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
