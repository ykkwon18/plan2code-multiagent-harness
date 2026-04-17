# Claude + Codex Harness

Claude Code 작업 + Codex 리뷰 기반 프로젝트의 plan-task-catalog 기반 워크플로우.
프롬프트와 작업 내역 기반으로 프로젝트를 관리함.

`docs/user_inbox/` 에 연구계획서를 넣고 작업을 지시하여, agent가 plan 작성 및 task 중에 codex로부터 리뷰를 받고, 구현이 연구 의도를 벗어나지 않도록 함.

3 가지 핵심 계층

- **plan-task**: 지시받은 작업의 계획&진행 문서 작성 task id 기반으로 관리됨, 고민했던 대안, 유저가 준 프롬프트 원문
- **review lane**: 메인 claude가 사회자로, codex를 다중 스폰하여 교차 토론을 시키는 단계. plan의 의도와 구현 상세 무결성을 리뷰함.
- **catalog**: 작업이 끝나면 계획&진행 문서는 자동으로 `docs/catalog` 폴더로 `review/` 와 함께 이동함. git commit msg에는 task id가 올라가서, 이후 git의 commit 이력과 작업 내역, 의도를 직접 대조 가능.


---

## 1. Setting

```bash
# 1) 적용할 프로젝트 루트에서 실행
git remote add harness https://github.com/ykkwon18/plan2code-multiagent-harness.git
git fetch harness
git checkout harness/harness-export -- \
    CLAUDE.md .claude .codex .gitignore docs

# 2) venv 만들기 (스크립트가 PyYAML을 씀)
python -m venv .venv
.venv/bin/pip install pyyaml

# 3) codex 플러그인 codex로 리뷰를 돌리기 위한 핵심 플러그인. openai 공식.
Claude Code 안에서:
/plugin marketplace add anthropics/claude-code
/plugin install codex@openai-codex
```

확인할 것:
- `.claude/settings.json` 은 `$CLAUDE_PROJECT_DIR/.venv/bin/python` 으로 스크립트를 돌림. venv 위치가 다르면 이 JSON의 경로만 고치면 됨.
- `CLAUDE.md` 는 하니스 공용 규칙만 들어 있음. 프로젝트에만 해당되는 것(GPU 고정, 도메인 규칙 등)은 맨 위에 섹션으로 추가.
- `.codex/config.toml` 은 `model=gpt-5.4, effort=xhigh` 가 기본값. 필요하면 바꾸면 됨.

### 주의 — `.claude/` 위치

`CLAUDE_PROJECT_DIR` 은 Claude Code가 켜질 때 **가장 가까운 `.claude/` 가 있는 상위 폴더**를 찾아서 잡음 (없으면 git repo 루트). 그래서:

- **하니스 옮겨올 때 `.claude/` 빼먹으면 훅이 조용히 안 돌아감.** 오류도 없고 경고도 없어서 모르고 지나치기 쉬움. 위 `git checkout` 줄에서 `.claude` 들어갔나 확인.
- **nested repo / subproject 쓰는 경우**: 상위 리포에 이미 `.claude/` 가 있고 서브프로젝트를 따로 하니스로 쓰려고 하면, 서브프로젝트 루트에 `.claude/` 를 **하나 더** 놓아야 함. 안 그러면 `CLAUDE_PROJECT_DIR` 이 위쪽을 가리켜서 서브프로젝트의 venv랑 훅이 다 무시됨.

### 주의 — Windows

settings.json은 **bash/zsh 변수 문법(`$CLAUDE_PROJECT_DIR`)을 씀**. Windows에서 훅을 돌리는 shell이 뭐냐에 따라 문법이 달라짐:

- `cmd.exe`: `%CLAUDE_PROJECT_DIR%`
- PowerShell: `$env:CLAUDE_PROJECT_DIR`

Linux / macOS / WSL에선 그대로 돌아감. 네이티브 Windows Claude Code에서 쓰려면 `.claude/settings.json` 의 커맨드를 그 shell 문법으로 바꾸거나, Python wrapper를 중간에 끼워서 shell을 안 타게 해야 함. 현재 설계는 Unix만을 대상으로 함.

WSL / Docker처럼 경로가 매핑되는 환경에선 `CLAUDE_PROJECT_DIR` 이 호스트 경로로 잡히는지 컨테이너 경로로 잡히는지 한 번 찍어보자. bind mount 경로 기준으로 맞춰 두면 안 엉킴.

---

## 2. 워크플로우

유저가 작업을 지시하면, 모델이 먼저 **"이거 plan까지 세울 일이냐, 그냥 바로 고칠 일이냐"** 를 판단함. 계획이 불필요해보이면 유저한테 "이건 단순 작업 같은데 plan 생략해도 될까요?" 하고 동의를 구함. 유저가 OK 하면 trivial 경로(A), 아니면 plan-task 경로(B).
지침상 plan이 디폴트.

```
[작업 요청 도착]
      │
      ▼
 "이거 plan 세울 일인가?"      ── 모델이 먼저 판단
      │
      ├── YES → plan-task 경로 (아래 B)
      │
      └── NO  → 유저한테 "생략해도 되겠냐" 물어봄
                │
                ├── 유저 OK → trivial 경로 (아래 A)
                └── 유저 NO → plan-task 경로로 돌아감
```

### A. Trivial 경로 (plan-task 생략)

오타 고치기, 값 하나 바꾸기, 딱 봐도 one-line 버그, 기계적으로 반복되는 리팩토링, 의존성 버전 올리기 같은 것. `new_catalog.py` 의 `prepare` → `finalize` 2단계로 끝냄.

```bash
# 1) stub 만들고 ID 받기
.venv/bin/python docs/scripts/new_catalog.py prepare <slug>
# → docs/catalog/<new-id>/<new-id>.md (status=draft 상태로 staged)

# 2) 실제 고친 파일이랑 stub을 같이 묶어서 커밋.
#    커밋 메시지에 `Task: <new-id>` 줄이 꼭 들어가야 함.
git add <changed-files>
git commit -m "feat: <뭘 바꿨는지>

Task: <new-id>"

# 3) draft → done 으로 올리기
.venv/bin/python docs/scripts/new_catalog.py finalize <new-id>
# → 또 따로 커밋 (메시지에 다시 Task: <new-id>)
```

**`Task: <id>`가 commit보다 우선적으로 관리됨**: `Task: <id>` 태그가 모든 걸 묶는 유일한 키라서, 커밋 메시지에 박을 id를 먼저 손에 쥐고 있어야 함. `prepare` 가 그 id를 만들어 돌려주는 역할.

### B. plan-task 경로 (plan 필요)

설계 결정, 트레이드오프 따져야 함, 여러 모듈 동시 수정, 대안 비교, 하다가 방향 틀어질 가능성 있음 — 이 중 하나라도 걸리면 이쪽으로 감.

```bash
# 1) plan-task 파일 만들기
.venv/bin/python docs/scripts/new_task.py <slug> [--title "..."]
# → docs/plan-task/<new-id>.md (status=active, staged)
```

만들고 나면 템플릿 본문을 채움. 최소한 들어가야 하는 것들 (`plan-review-methodology.md` §5 참고):
- 프롬프트 체인 (유저가 준 지시 원문)
- 전제, 제약, 건드리면 안 되는 것
- 단계별 체크리스트 (`- [ ]`)
- 고민한 대안과 왜 버렸는지
- acceptance 기준
- 남은 질문들

**plan 초안이 서면 review lane이 실행됨**. 필요없다고 판단해도 agent가 유저에게 동의를 구함.
작업 진행중 plan문서는 그 때 그 때 업데이트 됨.

```bash
# 2) 작업 중 — Phase 한 개 끝낼 때마다:
#    - plan의 [ ] → [x] 로 체크
#    - ## 진행 노트 에 뭘 발견했는지 / 뭘 바꿨는지 한 줄
#    - 코드·수식·설정 파일 하나 저장할 때마다 codex review 2개 이상 병렬 (§4 참고)

# 3) 작업 끝나거나 접을 때
.venv/bin/python docs/scripts/close_task.py <id> [--status done|abandoned]
# → docs/plan-task/<id>.md       → docs/catalog/<id>/<id>.md
# → docs/plan-task/review/<id>/  → docs/catalog/<id>/review/  (있을 때만)
```

`close_task.py` 가 plan 본문이랑 review 폴더를 한 번에 catalog 아래로 옮기고, 본문에 박혀 있던 review 경로도 자동으로 고쳐줌. 옮긴 뒤에 커밋됨. (커밋 메시지에 `Task: <id>`).

---

## 3. Plan Review Lane (plan-task일 때 기본값)

plan 초안 쓰자마자 바로 들어감. codex 3~4명이 같은 plan을 각자 뜯어보고, moderator가 그 결과들을 모아서 GO/NO-GO 찍음. GO 여야 구현 시작.

### 어디에 뭐가 쌓이는가

작업 중:
```
docs/plan-task/
├── <task-id>.md
└── review/
    └── <task-id>/
        ├── r1_packet.md         # 리뷰어들에게 돌린 입력
        ├── r1_codex-a.md ...    # 각자 낸 리뷰 (a, b, c, d)
        ├── r1_moderator.md      # moderator 종합
        ├── r2_*.md              # Round 2
        └── summary.md           # 최종 gate 판정
```

close 하면 알아서 옮겨감:
```
docs/catalog/<task-id>/
├── <task-id>.md
└── review/                      # 그대로 따라옴
    ├── r1_*.md
    └── ...
```

plan 본문에 `docs/plan-task/review/<task-id>/...` 로 박아 둔 링크는 close 시점에 `review/...` 상대경로로 바뀜 (`_rewrite_review_paths`).

### 루프 토론 구조 (`plan-review-methodology.md` 에 자세히)

1. **r1_packet 준비**: plan을 작성한 agent가 토론 주제 `review/r1_packet.md` 작성. 요구 문서·plan·관련 코드 경로·남은 질문 전부 포함
2. **Round 1 spawn**: codex 3~4개 병렬로 띄움(어려운 태스크일수록 많이 권장) (`task --background --model gpt-5.4 --effort high`). 보는 관점: 의도가 plan에 그대로 살아있나 / 실제로 돌아갈 수 있나 / 수식 맞나 / privilege·leakage / 검증할 수 있나 / 운영 비용
3. **moderator 종합**: 토론 사회자인 claude가 결과를 모아서 2차 토론 주제 `r1_moderator.md` 씀. 다들 동의하는 건 바로 반영, 일부 subagent만  주장하는 의견은 **원문을 다시 찾아본 뒤** 받을지 말지 정함 (다수결은 지양해야 함)
4. **Round 2**: plan 고치고 같은 루프 한 번 더. critical / high가 아직 남아 있으면 Round 3까지 허용. 더 늘리라고 지시해도 됨.
5. **GO**: critical 0개 + high 전부 해결되거나 "이건 이렇게 간다" 찍어놓고 접어둠 + acceptance 기준 적혀있음 → 구현 시작
6. **NO-GO**: 유저한테 "이 이슈들이 남았다. 선택지 A/B/C 중 어느 쪽?" 정리해서 보고. 기본값은 유저에게 판단을 요청하도록 되어있음.

### 생략 조건 (유저 동의 필요)

아래 중 하나라도 해당되면 "이번엔 default lane(리뷰 없이) 가도 될 것 같습니다" 하고 물어봄 → 유저가 OK 하면 생략:
- 그냥 trivial 수정 / 기계적 리팩토링
- 누가 봐도 one-line 버그 수정
- 문서만 고치는 편집
- 이미 review 통과한 plan에 기계적인 후속만 붙이는 경우 (범위·수식 안 바뀜)

애매하면 그냥 review lane 감 (괜히 review 돌리는 비용 < 빼먹고 가서 터지는 비용).

---

## 4. 작업하면서 codex로 교차 검증 — 파일 하나 저장할 때마다

코드 / 수식 / 설정 파일 하나 저장할 때마다 codex를 **2개 이상 병렬**로 띄워서 그 파일(이나 그 시점 diff)을 보게 시킴. 보통 `review` + `adversarial-review` 같이 돌리거나 `rescue` 같이 돌림.

- Claude Code `Skill`(/ 커맨드)는 유저가 직접 터미널에서 사용해야 함. agent가 사용시 블로킹 걸림. `codex-companion.mjs` 를 **Bash + `run_in_background: true`** 로 직접 호출하도록 `claude.md`에서 명시함.
- 기본 옵션: `--model gpt-5.4 --effort high`. 수식 / 아키텍처 깊게 볼 때는 `--effort xhigh`
- 폴링은 `ScheduleWakeup` 1~3분
- **같은 파일 최대 3번까지 재리뷰**: 피드백 반영한 게 찝찝하면 같은 파일로 다시 2개 이상 돌림. 3번 돌려도 안 끝나면 유저한테 보고
- 오타 고친다거나 링크만 바꾼다거나 하는 건 뺌

실제로 부르는 모양:
```bash
node "$HOME/.claude/plugins/cache/openai-codex/codex/<ver>/scripts/codex-companion.mjs" \
  task --background --model gpt-5.4 --effort high "<프롬프트>"
# → job id 받음. status --all --json 으로 상태 보고, result <job-id> 로 결과 가져오기
```

---

## 5. 커밋 규칙

**모든** 커밋 메시지에 `Task: <id>` 줄이 꼭 들어감. 이 태그가 코드 수정과 작업 내역을 연결하는 **유일한 연결 키**임. 빠지면 commit으로부터 task 추적이 어려움. 스크립트로 알아서 관리됨.

```
<type>(<scope>): <subject>

<body>

Task: 2026-04-17_03_<slug>
```

catalog frontmatter에는 `head_commit` 이나 `files_touched` 같이 "git에서 뽑아낼 수 있는 값"은 안 적음. 커밋 목록이랑 바뀐 파일은 항상 grep으로 다시 뽑음:

```bash
git log --grep="Task: <id>"
git log --grep="Task: <id>" --name-only --pretty=format: | sort -u
```

---

## 6. Hooks

`.claude/settings.json` 에 훅 5개가 걸려 있음. agent에게 경고를 던져주는 역할 (fail-open):

| Trigger | Hook | When |
|---|---|---|
| `Stop` | `warn_session_doc_trace.py` | 코드는 바뀌었는데 `docs/plan-task` 나 `docs/catalog` 쪽은 안 바뀜 |
| `Stop` | `warn_codex_review.py` | 코드가 꽤 많이(LOC threshold 이상) 바뀌었는데 `.codex_review_head` 마커가 옛날 상태 |
| `PreToolUse(Bash)` | `warn_manual_git_mv.py` | `git mv` 로 plan-task를 catalog로 수동으로 옮기려고 할 때 (close_task.py 우회) |
| `PreToolUse(Edit\|Write)` | `warn_files_touched_edit.py` | 이미 닫힌 catalog의 `files_touched` 를 손대려고 할 때 |
| `PostToolUse(Bash)` | `warn_missing_task_tag.py` | 방금 한 커밋 메시지에 `Task: <id>` 가 빠짐 |

각 훅이 어떤 조건에서 뜨는지는 해당 `.py` 파일 맨 위 docstring 에 명시됨.

---

## 7. 폴더 구조

```
CLAUDE.md                            # 지침
.claude/settings.json                # Hooks 설정
.codex/config.toml                   # codex CLI 기본 model/effort
docs/
├── documentation-workflow-guide.md  # 워크플로 전체 규칙(agent가 읽는 파일은 아님)
├── plan-review-methodology.md       # review lane 상세 (agent가 읽는 파일은 아님)
├── templates/                       # plan-task / catalog 템플릿
├── scripts/
│   ├── new_task.py                  # plan-task 만들기
│   ├── new_catalog.py               # trivial 경로 (prepare / finalize)
│   ├── close_task.py                # plan-task → catalog 옮기고 마감
│   └── hooks/                       # fail-open warn 훅 5개
├── plan-task/                       # 작업 지시를 받아 작업 진행을 관리하는 폴더
│   └── review/<id>/                 # review lane(토론) 과정 및 결과물 (close 시에 catalog로 같이 넘어감)
├── catalog/                         # 작업 내역(기본적으로 사후 수정은 하지 않음)
│   └── <id>/
│       ├── <id>.md
│       └── review/                  # `close_task.py` 가 plan-task/review/<id>/ 에서 옮겨 옴
└── user_inbox/                      # 유저가 던져 준 원본 proposal / 요구 문서 (손 안 대고 그대로)
```

---

## 설계 이유와 세부 설명서

- `docs/documentation-workflow-guide.md` — 워크플로 전체 규칙 (§1~§15)
- `docs/plan-review-methodology.md` — review lane 자세히 (§1~§12)
- 각 스크립트 맨 위 docstring — 그 스크립트가 뭘 확인하고 어디서 실패할 수 있는지
