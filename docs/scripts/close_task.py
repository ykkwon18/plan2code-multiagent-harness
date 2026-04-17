#!/usr/bin/env python3
"""Move a plan-task to catalog and finalize its frontmatter.

Catalog layout — 디렉토리 단위 스냅샷:

    docs/catalog/<id>/
    ├── <id>.md          # frontmatter + body (plan-task에서 이어받음)
    └── review/          # plan-review-methodology §4 산출물 (lane 돌린 경우만)

이전엔 `catalog/<id>.md` 단일 파일이었지만, review 산출물이 완료 이후에도
`plan-task/review/<id>/` 아래 고아로 남는 문제가 있었다. close 시점에 디렉토리
단위로 같이 옮겨서 "completed task의 모든 산출물은 한 경로"로 유지한다.

Catalog는 git에 대한 thin index — derived value(`head_commit`, `files_touched`)는
frontmatter에 저장하지 않는다. 이 task의 commit/files는 항상 grep으로 재구성한다:

    git log --grep="Task: <id>"
    git log --grep="Task: <id>" --name-only --pretty=format: | sort -u

저장하지 않으니 stale될 수 없다. §7-2의 `Task: <id>` 태그가 single foreign key.

2-phase 실행 — preflight → apply:
  preflight: 모든 검증을 mutation 전 수행.
             - plan-task 존재
             - dst 미존재 (디렉토리/파일 둘 다)
             - plan-task tracked (untracked는 --adopt-untracked로만 복구)
             - status=done이면 `Task: <id>` 태그 commit 1개 이상 존재
             - dirty worktree 경고 (fail-soft)
  apply:     검증 통과 후에만 git mv → write → git add.
             - plan-task/<id>.md        → catalog/<id>/<id>.md
             - plan-task/review/<id>/   → catalog/<id>/review/   (있을 때만)
             - body 내 `docs/plan-task/review/<id>/` 경로는 `review/` 상대경로로 재작성
               (순수 mechanical rewrite, 의미 변경 없음 — §6-5 immutability는 "사후 손편집 금지"를 말하므로 close 시점의 경로 정리는 허용)

abandoned 분기:
  - 태그 commit 0개 허용
  - --reason 필수
  - "계획만 하다 접은 일"을 가짜 commit으로 포장하지 않기 위함

Usage:
    .venv/bin/python docs/scripts/close_task.py <id> [--status done|abandoned]
                                                     [--reason "..."]
                                                     [--adopt-untracked]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fm import read, write  # noqa: E402
from _ids import CATALOG, DOCS, PLAN  # noqa: E402

REPO = DOCS.parent


def _git_ok(*args: str) -> bool:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True
    ).returncode == 0


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


def worktree_dirty() -> str:
    """git status --porcelain 결과(빈 문자열이면 깨끗)."""
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO, capture_output=True, text=True,
    )
    return out.stdout if out.returncode == 0 else ""


def untracked_under(path: Path) -> list[str]:
    """Return untracked (not --exclude-standard ignored) files under `path`.

    빈 리스트면 모든 파일이 tracked 상태. `git ls-files --error-unmatch`는
    디렉토리에 tracked 파일이 하나라도 있으면 성공하므로 mixed 상태 검출이
    불가. `--others --exclude-standard`로 실제 untracked만 수집.
    """
    if not path.exists():
        return []
    out = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", str(path)],
        cwd=REPO, capture_output=True, text=True,
    )
    return [l for l in out.stdout.splitlines() if l.strip()]


@dataclass
class Plan:
    src: Path
    dst_dir: Path
    dst_file: Path
    review_src: Path
    review_dst: Path
    data: dict
    body: str
    status: str
    reason: str | None


def preflight(args: argparse.Namespace) -> Plan | int:
    """모든 검증을 수행하고 산출물(Plan)을 반환. 실패 시 정수 종료코드."""
    tid = args.task_id
    src = PLAN / f"{tid}.md"
    dst_dir = CATALOG / tid
    dst_file = dst_dir / f"{tid}.md"
    review_src = PLAN / "review" / tid
    review_dst = dst_dir / "review"

    if not src.exists():
        print(f"plan-task not found: {src}", file=sys.stderr)
        return 1

    if dst_dir.exists():
        print(f"refusing to overwrite {dst_dir}", file=sys.stderr)
        return 1

    if args.status == "abandoned" and not args.reason:
        print("--reason required when --status abandoned", file=sys.stderr)
        return 1

    # plan-task가 git에 있는지 (untracked fallback 폐기)
    tracked = _git_ok("ls-files", "--error-unmatch", str(src))
    if not tracked and not args.adopt_untracked:
        print(
            f"plan-task is not tracked by git: {src}\n"
            "먼저 `git add` + `git commit`으로 trackable 상태로 만든 뒤 다시 시도하거나, "
            "복구 목적이면 `--adopt-untracked` 를 명시하라.",
            file=sys.stderr,
        )
        return 1

    # review/<id>/ 서브트리도 동일 정책. 일부만 tracked인 mixed 상태도 차단 —
    # 그대로 git mv하면 tracked 파일만 rename되고 untracked는 부분이동되어
    # catalog에 어정쩡한 상태가 남는다. abandoned 분기에서도 동일 검사를 거쳐
    # 미완 scratch 리뷰 노트가 무심코 immutable catalog에 올라가는 것을 방지.
    if review_src.exists() and not args.adopt_untracked:
        review_untracked = untracked_under(review_src)
        if review_untracked:
            msg = "\n  ".join(review_untracked[:10])
            more = f"\n  ... (+{len(review_untracked)-10} more)" if len(review_untracked) > 10 else ""
            print(
                f"review subtree has untracked files under {review_src}:\n  {msg}{more}\n"
                "먼저 commit하거나, 복구/import 목적이면 `--adopt-untracked` 를 명시하라.",
                file=sys.stderr,
            )
            return 1

    data, body = read(src)
    if not data.get("base_commit"):
        print(f"missing base_commit in {src}", file=sys.stderr)
        return 1

    # done은 task commit 최소 1개 필요. abandoned는 0개 허용 (--reason 보유).
    if args.status == "done" and not has_task_commits(args.task_id):
        print(
            f"no commits with `Task: {args.task_id}` tag found.\n"
            "작업 결과를 먼저 커밋하라 (커밋 메시지에 `Task: {id}` 라인 포함). "
            "계획만 하다 접은 경우라면 --status abandoned --reason \"...\" 로 닫아라.",
            file=sys.stderr,
        )
        return 1

    # dirty worktree 경고 — fail-soft. 진짜 차단하면 디버깅 중간 상태 스냅샷이 막힘.
    dirty = worktree_dirty()
    if dirty:
        print(
            "warn[close-task]: working tree에 미커밋 변경이 있습니다. "
            "이 task와 무관한 변경이면 무시해도 되지만, task 작업의 일부가 미커밋 상태라면 "
            "먼저 커밋하고 다시 close_task를 돌리는 게 안전합니다.\n" + dirty,
            file=sys.stderr,
        )

    return Plan(
        src=src, dst_dir=dst_dir, dst_file=dst_file,
        review_src=review_src, review_dst=review_dst,
        data=data, body=body,
        status=args.status, reason=args.reason,
    )


def _rewrite_review_paths(body: str, task_id: str) -> str:
    """body 내 old review 경로를 catalog 내부 상대경로로 재작성.

    Suffix-있는 경우 (파일 링크):
        `docs/plan-task/review/<id>/r1.md` → `review/r1.md`
        `plan-task/review/<id>/r1.md`      → `review/r1.md`
        `../plan-task/review/<id>/r1.md`   → `review/r1.md`

    Suffix-없는 경우 (디렉토리 참조):
        `docs/plan-task/review/<id>` → `review`
        `plan-task/review/<id>`      → `review`
        `../plan-task/review/<id>`   → `review`

    Round 3에서 참조하는 이전 라운드 파일 링크 등 body에 박힌 절대·상대경로를
    close 시점에 일괄 정리. 의미 변경 없는 mechanical rewrite.

    주의: `../user_inbox/...` 같은 **review 밖 relative link**는 plan-task(`docs/plan-task/<id>.md`)
    기준이었던 것이 catalog(`docs/catalog/<id>/<id>.md`)로 옮겨가면서 한 레벨 더 깊어져
    의미가 바뀐다. 자동 재작성은 위험하므로 여기선 건드리지 않고, apply()에서 warn만 띄운다.
    """
    # 순서 중요: `plan-task/review/<id>/`는 `docs/plan-task/review/<id>/` 및
    # `../plan-task/review/<id>/`의 substring이므로 가장 마지막에 돌려야
    # 앞 두 변형이 먼저 완전 치환된다. 안 그러면 `../plan-task/.../...`에서
    # 내부 substring이 먼저 치환돼 `../review/...`가 남는다.
    for with_slash in (
        f"docs/plan-task/review/{task_id}/",
        f"../plan-task/review/{task_id}/",
        f"plan-task/review/{task_id}/",
    ):
        body = body.replace(with_slash, "review/")
    for bare in (
        f"docs/plan-task/review/{task_id}",
        f"../plan-task/review/{task_id}",
        f"plan-task/review/{task_id}",
    ):
        body = body.replace(bare, "review")
    return body


def _warn_residual_relative_links(body: str, task_id: str) -> None:
    """close 후 catalog 본문에 남은 `../` relative link가 있으면 경고.

    plan-task 본문이 작성된 기준 경로는 `docs/plan-task/<id>.md`였지만 close 후엔
    `docs/catalog/<id>/<id>.md`로 한 레벨 깊어진다. review 경로는 _rewrite_review_paths가
    처리하지만, `../user_inbox/foo.md` 같은 외부 참조는 이제 다른 곳을 가리킨다
    (구 resolve: `docs/user_inbox/foo.md`, 신 resolve: `docs/catalog/user_inbox/foo.md`).

    자동 재작성은 오탐 위험이 커서(다양한 markdown 컨텍스트) 경고만 띄운다.
    catalog immutability(§6-5) 때문에 작성자는 close 전에 `docs/...` 절대경로로
    바꾸거나, 경고 확인 후 catalog 바디에 주석으로 명시하는 식으로 대응해야 한다.
    """
    # 간단한 휴리스틱: markdown/plain text에서 자주 쓰이는 컨텍스트의 `../` 접두.
    # 정확한 파서는 과공. false-positive는 허용 (경고일 뿐).
    import re
    pattern = re.compile(r"(?:\]\(|`| |\"|')\.\./")
    hits = pattern.findall(body)
    if hits:
        print(
            f"warn[close-task]: catalog 본문에 `../` relative link가 {len(hits)}건 남아 있음. "
            "plan-task → catalog 이동으로 경로 깊이가 1 증가해 외부 참조가 다른 파일을 가리킬 수 있음. "
            "review 외 참조는 가능하면 `docs/...` 절대경로로 써두길 권장.",
            file=sys.stderr,
        )


def apply(plan: Plan) -> int:
    """preflight 통과 후에만 호출. 모든 mutation을 여기서만 수행.

    이동 순서는 review → main. 이유: review mv가 실패해도 main은 아직
    plan-task/에 남아 있어 rerun이 가능하다. 반대 순서면 main이 catalog로
    가버린 뒤 review mv 실패 시 dst_dir이 이미 존재해 preflight가 막는다.
    """
    plan.data["status"] = plan.status
    plan.data["closed_at"] = date.today().isoformat()
    if plan.reason:
        plan.data["abandon_reason"] = plan.reason
    # head_commit / files_touched 는 의도적으로 frontmatter에 저장하지 않는다.
    # `git log --grep="Task: <id>"`로 항상 재구성 가능. (§7-2)
    # 혹시라도 plan-task에 잔재가 있으면 제거.
    plan.data.pop("head_commit", None)
    plan.data.pop("files_touched", None)

    body = _rewrite_review_paths(plan.body, plan.data["id"])

    plan.dst_dir.mkdir(parents=True, exist_ok=True)

    # (1) review/<id>/ 먼저 이동 (있을 때만). 실패해도 main은 아직 안전.
    if plan.review_src.exists():
        review_tracked = _git_ok("ls-files", "--error-unmatch", str(plan.review_src))
        try:
            if review_tracked:
                subprocess.check_call(
                    ["git", "mv", str(plan.review_src), str(plan.review_dst)], cwd=REPO
                )
            else:
                plan.review_src.rename(plan.review_dst)  # --adopt-untracked 경로
        except Exception as e:
            print(
                f"ERROR: review/<id>/ 이동 실패: {e}\n"
                f"  src={plan.review_src}\n  dst={plan.review_dst}\n"
                f"catalog 파일은 아직 이동되지 않았으므로 dst_dir을 지우고 다시 시도 가능:\n"
                f"  rm -rf {plan.dst_dir}",
                file=sys.stderr,
            )
            return 2

    # (2) main plan-task 파일 이동.
    tracked = _git_ok("ls-files", "--error-unmatch", str(plan.src))
    try:
        if tracked:
            subprocess.check_call(["git", "mv", str(plan.src), str(plan.dst_file)], cwd=REPO)
        else:
            plan.src.rename(plan.dst_file)  # --adopt-untracked 복구 경로
    except Exception as e:
        print(
            f"ERROR: main plan-task 이동 실패: {e}\n"
            f"  src={plan.src}\n  dst={plan.dst_file}\n"
            f"review/는 이미 {plan.review_dst}로 이동됨. 복구하려면:\n"
            f"  git mv {plan.review_dst} {plan.review_src}  # 또는 mv\n"
            f"  rm -rf {plan.dst_dir}",
            file=sys.stderr,
        )
        return 2

    write(plan.dst_file, plan.data, body)
    subprocess.check_call(["git", "add", str(plan.dst_file)], cwd=REPO)
    if plan.review_dst.exists():
        subprocess.check_call(["git", "add", str(plan.review_dst)], cwd=REPO)

    _warn_residual_relative_links(body, plan.data["id"])

    print(plan.dst_file)
    print(
        "REMINDER: catalog 디렉토리가 staged 상태입니다. "
        f"별도 커밋(메시지에 `Task: {plan.data['id']}` 포함)으로 확정하세요.",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("task_id")
    p.add_argument("--status", choices=["done", "abandoned"], default="done")
    p.add_argument("--reason", default=None, help="abandon_reason; required when abandoned")
    p.add_argument(
        "--adopt-untracked",
        action="store_true",
        help="recovery only: allow closing a plan-task that was never git-add'd",
    )
    args = p.parse_args()

    plan = preflight(args)
    if isinstance(plan, int):
        return plan
    return apply(plan)


if __name__ == "__main__":
    raise SystemExit(main())
