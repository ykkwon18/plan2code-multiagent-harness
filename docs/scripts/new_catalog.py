#!/usr/bin/env python3
"""Create a catalog entry directly for trivial changes (§3-1) — 2-stage.

Trivial route는 plan-task 단계를 건너뛰지만, 여전히 attribution은
`Task: <id>` 태그(§7-2) 기반이라 사용자가 id를 미리 알아야 커밋 메시지에 박을 수 있다.
이를 위해 2단계로 쪼갠다:

  1) prepare:  id 생성 + stub catalog 디렉토리/파일 작성(status=draft) + git add stub
               → 사용자에게 id 안내
  2) finalize: 같은 id로 호출. `Task: <id>` 태그 commit이 1개 이상 존재하는지
               확인하고 status=draft → done 으로 승격. git add 후 리마인더.

Layout (close_task.py와 일관):

    docs/catalog/<id>/
    └── <id>.md

trivial 경로엔 review/ 서브디렉토리가 없지만, plan-task 출신 catalog와 동일한
중첩 구조를 유지해 hook·스크립트의 경로 분기를 없앤다.

derived value(`head_commit`, `files_touched`)는 frontmatter에 저장하지 않는다.
이 catalog의 commit/files는 항상 grep으로 재구성한다 (§7-2):

    git log --grep="Task: <id>"
    git log --grep="Task: <id>" --name-only --pretty=format: | sort -u

Usage:
    .venv/bin/python docs/scripts/new_catalog.py prepare <slug> [--title "..."]
    .venv/bin/python docs/scripts/new_catalog.py finalize <id>
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

TEMPLATE = DOCS / "templates" / "catalog.md"
REPO = DOCS.parent


def has_task_commits(task_id: str) -> bool:
    out = subprocess.run(
        [
            "git", "log",
            f"--grep=Task: {task_id}",
            "--format=%H",
            "-n", "1",
        ],
        cwd=REPO, capture_output=True, text=True,
    )
    return out.returncode == 0 and bool(out.stdout.strip())


def cmd_prepare(args: argparse.Namespace) -> int:
    slug = slugify(args.slug)
    cid = next_id(slug, [PLAN, CATALOG])
    target_dir = CATALOG / cid
    target = target_dir / f"{cid}.md"
    if target_dir.exists():
        print(f"refusing to overwrite {target_dir}", file=sys.stderr)
        return 1

    head = head_commit()
    data, body = read(TEMPLATE)
    data["id"] = cid
    data["title"] = args.title or slug.replace("-", " ")
    data["status"] = "draft"
    today = date.today().isoformat()
    data["started_at"] = today
    data["base_commit"] = head
    # head_commit/files_touched는 의도적으로 저장하지 않음 (§7-2 grep 기반).

    target_dir.mkdir(parents=True, exist_ok=True)
    write(target, data, body)
    subprocess.check_call(["git", "add", str(target)], cwd=REPO)
    print(target)
    print(
        "\nREMINDER (prepare 단계 완료):\n"
        f"  1. trivial 변경 + 이 catalog stub을 함께 커밋하세요.\n"
        f"     커밋 메시지에 반드시 `Task: {cid}` 라인 포함.\n"
        f"  2. 그 다음 `.venv/bin/python docs/scripts/new_catalog.py finalize {cid}` 실행.\n",
        file=sys.stderr,
    )
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    cid = args.task_id
    target_dir = CATALOG / cid
    target = target_dir / f"{cid}.md"
    if not target.exists():
        print(
            f"catalog stub not found: {target}\n"
            "먼저 `new_catalog.py prepare <slug>`로 stub을 만드세요.",
            file=sys.stderr,
        )
        return 1

    data, body = read(target)
    if data.get("status") not in ("draft", None):
        print(
            f"catalog status is `{data.get('status')}`, expected `draft`. "
            "이미 finalize된 항목입니다 (catalog는 §6-5에 의해 immutable).",
            file=sys.stderr,
        )
        return 1

    if not has_task_commits(cid):
        print(
            f"no commits with `Task: {cid}` tag found.\n"
            "trivial 변경 + stub catalog를 먼저 커밋하세요 (Task 태그 포함).",
            file=sys.stderr,
        )
        return 1

    data["status"] = "done"
    data["closed_at"] = date.today().isoformat()
    # frontmatter 잔재 제거 (이전 schema 호환)
    data.pop("head_commit", None)
    data.pop("files_touched", None)

    write(target, data, body)
    subprocess.check_call(["git", "add", str(target)], cwd=REPO)
    print(target)
    print(
        "REMINDER: finalize된 catalog가 staged 상태입니다. "
        f"별도 커밋(메시지에 `Task: {cid}` 포함)으로 확정하세요.",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("prepare", help="generate id + stub catalog (stage 1)")
    pp.add_argument("slug")
    pp.add_argument("--title", default=None)
    pp.set_defaults(func=cmd_prepare)

    pf = sub.add_parser("finalize", help="confirm task commits and mark done (stage 2)")
    pf.add_argument("task_id")
    pf.set_defaults(func=cmd_finalize)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
