# 코드베이스 문서화 워크플로우 가이드

AI가 대부분의 코드를 작성하는 환경에서, **설계 의도**와 **프롬프트-작업 인과관계**를 추적 가능하게 유지하기 위한 문서화 설계.

---

## 1. 의도

git은 "무엇이 바뀌었나"를 기록하지만 "왜 그렇게 바꾸기로 했는지", "어떤 프롬프트에서 나왔는지", "어떤 대안을 기각했는지"는 소실된다. AI 작업은 같은 코드 변경이라도 프롬프트 뉘앙스에 따라 구현이 갈리므로, 사후에 "이 방향을 되돌리고 싶다"는 판단이 들었을 때 git diff만으론 외과적 롤백이 불가능하다.

이 워크플로우는 다음 세 가지를 보존한다.

1. **설계 의도** — 코드를 읽어도 알 수 없는 "왜"
2. **작업 이력** — 프롬프트 원문, 전제, 기각한 대안, 만들어진 커밋들
3. **현재 진행 중인 작업의 계획** — 중단·재개·방향 수정이 가능하도록

---

## 2. 디렉토리 구조

```
docs/
├── documentation-workflow-guide.md  # 이 문서
├── plan-task/                       # 진행 중인 작업. 단명. 계획이 필요한 변경만.
│   └── YYYY-MM-DD_NN_<slug>.md
├── catalog/                         # 완료·중단된 작업의 감사 로그. 영구 보존.
│   └── YYYY-MM-DD_NN_<slug>.md
├── templates/
│   ├── plan-task.md
│   └── catalog.md
└── scripts/                         # 워크플로 자동화. 프로젝트 코드와 의도적으로 분리.
    ├── new_task.py                  # plan-task 파일 생성
    ├── new_catalog.py               # trivial 직행 catalog 생성 (§3-1)
    ├── close_task.py                # plan-task → catalog 이동 + 메타 확정
    └── hooks/                       # Claude Code 훅 (§11-3)
        ├── warn_session_doc_trace.py
        ├── warn_manual_git_mv.py
        └── warn_files_touched_edit.py
```

워크플로 스크립트는 **`docs/scripts/`** 아래 둔다 — 프로젝트 코드(`src/`)와 분리해 운영 도구를 한 곳에 모은다.

**단순화 원칙**: plan-task와 catalog는 하위 디렉토리 없이 flat하게 유지한다.

---

## 3. 생명주기와 라우팅

작업의 규모에 따라 두 경로로 갈린다.

```
  [작업 요청 도착]
        │
        ▼
  ┌─────────────────┐  YES   docs/plan-task/<id>.md  (active)
  │ 계획이 필요한가? ├──────►      │
  └────────┬────────┘             │ 작업 진행
           │ NO                    ▼
           │                ┌────────────┐
           │         ┌──────┤ 완료/중단? ├──┐
           │         │ 완료 └────────────┘ │ 중단
           │         ▼                     ▼
           │    git mv →                git mv →
           │    docs/catalog/           docs/catalog/
           │    (done)                  (abandoned)
           │
           └──────────────► docs/catalog/<id>/<id>.md 직접 작성 (done)
```

### 3-1. 라우팅 규칙 — plan-task를 만들 것인가, 직접 catalog로 갈 것인가

**plan-task를 만들어야 하는 경우** (계획이 필요한 변경):
- 설계 결정이나 트레이드오프 판단이 포함됨
- 여러 모듈에 걸친 변경
- 커밋이 2개 이상 나올 것 같음
- 대안을 고려한 뒤 하나를 골라야 함
- 진행 중 방향 수정이 일어날 가능성이 있음

**plan-task를 건너뛰고 catalog로 직행하는 경우** (trivial change):
- 오타/주석/포매팅 수정
- 단일 값·상수 조정
- 명백한 one-line 버그 수정
- 이미 결정된 리팩토링의 기계적 반복 적용
- 의존성 업데이트 같은 단순 버전 변경

경계가 애매하면 **plan-task를 만드는 쪽**을 택한다. 사후에 "계획이 불필요했네"로 평가되어도 비용은 낮고, 반대 방향(계획 없이 시작했다가 엉킴)의 비용이 훨씬 크다.

**판정 절차**: 변경을 시작하기 전 모델/에이전트가 위 체크리스트로 trivial 여부를 1차 판정하고, trivial이라고 보면 사용자에게 명시적 동의를 구한다. 동의가 떨어지면 plan-task 단계만 건너뛰고 **catalog 항목은 반드시 생성한다**. plan-task 생략은 "계획 단계 생략"이지 "기록 생략"이 아니다.

**trivial route는 2단계 흐름**(§10):
1. `.venv/bin/python docs/scripts/new_catalog.py prepare <slug>` — id가 박힌 stub catalog 파일을 만들고 stage. 출력에서 새 id를 받는다.
2. trivial 변경 + 그 stub catalog 파일을 함께 한 커밋에 묶고, 커밋 메시지에 `Task: <id>` 라인을 포함한다(§7-2).
3. `.venv/bin/python docs/scripts/new_catalog.py finalize <id>` — `Task: <id>` 태그가 붙은 커밋들에서 `head_commit`/`files_touched`를 채우고 `status=done`으로 만든다. 그 결과를 별도 커밋으로 확정한다.

이 2단계는 "아직 존재하지 않는 history를 박는다"는 거짓 메타데이터를 원천 차단하기 위해 도입됐다(§10 갭 메모 참조). 단일 호출 자동 모드는 의도적으로 제거.

### 3-2. 상태 집합

- **`active`** — `plan-task/`에 존재. 진행 중.
- **`blocked`** — `plan-task/`에 존재. 외부 요인으로 대기 중. 본문 진행 노트에 대기 원인을 기록한다.
- **`done`** — `catalog/`에 존재. 정상 완료.
- **`abandoned`** — `catalog/`에 존재. 중단됨. `abandon_reason` 필수.

위치(디렉토리)와 `status` 필드는 항상 일관성 있어야 한다. 검증 스크립트가 확인한다.

### 3-3. 후속 작업으로 대체될 때 (lineage)

어떤 catalog 항목이 후속 작업으로 대체되는 경우, 기존 항목의 프론트매터에 `superseded_by: <new-id>` 필드를 **선택적으로** 추가할 수 있다. 별도 상태로 승격하지는 않는다 — 드문 케이스에 상태 기계를 늘리는 것은 과설계. 필드 하나로 lineage 링크만 남기면 충분하다.

### 3-4. catalog 불변성

catalog 항목 **본문**은 사후 수정 금지. 프론트매터 중 `superseded_by` 링크 추가만 예외적으로 허용한다.

---

## 4. 파일명과 ID 규칙

**형식**: `YYYY-MM-DD_NN_<slug>.md`

- `YYYY-MM-DD`: 작업 **시작일** (완료일 아님). 이동 후에도 이 날짜는 유지한다.
- `NN`: 같은 날짜 내 일련번호 `01`~`99`. 충돌 시 slug를 바꾸지 말고 번호를 올린다.
- `<slug>`: 소문자 ASCII kebab-case. `[a-z0-9]` 외 문자는 `-`로 치환, 연속 `-`는 축약, 양끝 `-` 제거.
- **파일 basename(확장자 제외)이 그대로 `id`가 된다.** 다른 파일에서 참조할 때 이 id를 사용한다.

예: `2026-04-13_01_<slug>.md` → id = `2026-04-13_01_<slug>`

---

## 6. plan-task / catalog — 작업 로그

같은 파일 템플릿을 쓰되 프론트매터 필드가 수명에 따라 늘어난다.

### 6-1. plan-task 프론트매터 (작업 시작 시)

```yaml
---
id: 2026-04-13_01_<slug>
title: <작업 제목>
status: active                   # active | blocked
started_at: 2026-04-13
base_commit: 3e3104c             # 작업 시작 시점 HEAD (단축 해시 OK)
---
```

### 6-2. plan-task 본문

```markdown
## 프롬프트 체인
<!-- 사용자가 AI에 준 지시의 원문. 의역/요약 금지. -->
1. (날짜/시각) 원문 그대로

## 전제와 제약
- 현재 코드의 이 부분이 어떻게 동작한다고 가정하고 시작함
- 건드리면 안 되는 영역

## 계획
- [ ] 단계 1
- [ ] 단계 2

## 고려한 대안
- A안: … / 기각 이유: …
- B안: … / 기각 이유: …

## 진행 노트
(작업 중 발견, 방향 수정, 막힌 지점 기록)
```

### 6-3. 완료·중단 시 추가되는 프론트매터 (→ catalog)

```yaml
closed_at: 2026-04-14
status: done                      # done | abandoned
abandon_reason: |                 # status=abandoned일 때만 필수
  (왜 포기했는지. 방향 전환의 근거가 되는 핵심 정보)
superseded_by: 2026-04-20_01_...  # 후속 작업이 이 항목을 대체할 때 선택적으로 추가
```

**derived value는 frontmatter에 저장하지 않는다.** 이 task의 commit 목록과 변경 파일은 `Task: <id>` 태그 grep으로 항상 재구성한다(§7-2):

```bash
# 이 task의 commit 목록
git log --grep="Task: <id>"

# 이 task가 만진 파일 (시점 무관, 항상 git 사실)
git log --grep="Task: <id>" --name-only --pretty=format: | sort -u
```

저장하지 않으니 `head_commit`/`files_touched`/`commits[]` 같은 필드는 catalog frontmatter에 두지 않는다. drift가 일어날 데이터 자체가 없다. catalog는 git에 대한 thin index — task id가 single foreign key.

**`base_commit`은 derived가 아니라 snapshot이다.** §7-1대로 "계획 시점 코드 스냅샷" 의미만 가지며 `git show <base>:<path>`로 당시 코드 상태를 복원하는 용도다. attribution에는 쓰이지 않고, `close_task.py`도 사후 보정하지 않는다.

**abandoned 분기**: `Task: <id>` 태그 commit이 0개여도 abandoned로 닫을 수 있다. `abandon_reason`이 필수. "계획만 하다 접은 작업"을 가짜 commit으로 포장하지 않기 위한 의도된 완화.

### 6-4. catalog 본문 추가 섹션

plan-task 본문은 **그대로 보존**하고, 아래 섹션만 아래에 덧붙인다.

```markdown
## 결과 요약
(최종적으로 무엇이 달라졌는가 — 2~4줄)

## 검증
- 테스트: …
- 수동 확인: …

## 사이드이펙트
(없으면 "없음". 있으면 해당 지점 최소 코드 조각 10줄 이내)

## 후속 조치
- [ ] 남은 TODO
```

### 6-5. catalog의 불변성

- catalog 본문과 프론트매터의 `files_touched`, `prompt_chain`, `head_commit`, `base_commit`은 **사후 수정 금지**.
- 유일한 예외: 후속 작업이 이 항목을 대체할 때 `superseded_by: <new-id>` 필드 추가.

---

## 7. 커밋 해시 앵커 전략

단일 main 브랜치 환경을 전제로 한다. feature branch/squash-merge 전략이 도입되면 이 절을 확장해야 한다.

### 7-1. 저장하는 단 하나의 해시 — `base_commit`

- `base_commit`: 작업 시작 시(=`new_task.py` 호출 시점) HEAD. **무엇을 전제로 계획을 세웠는지** 복원하기 위함. `git show <base>:<path>`로 당시 코드 상태를 원문 그대로 볼 수 있다. **attribution에는 쓰이지 않는다** — 인터리브 작업으로 base 이후 무관 commit이 끼어들 수 있어서 시간 윈도우 기반 attribution은 거짓이 되기 쉽다. base는 snapshot anchor일 뿐이지 task의 시작 commit이 아니다.

`head_commit`은 catalog frontmatter에 저장하지 않는다. "작업의 마지막 commit"이라는 의미는 항상 `git log --grep="Task: <id>" --reverse | tail -1`로 재구성한다. 저장하지 않으니 stale될 수 없고, close 시점에 아직 만들어지지 않은 catalog commit과의 timing 충돌도 사라진다.

이 작업이 만든 commit 목록과 변경 파일도 같은 원리로 모두 `Task: <id>` 태그 grep에서 재구성한다(§7-2). frontmatter에 `commits[]` / `head_commit` / `files_touched` 같은 필드를 두지 않는 이유는 중복 저장이며 드리프트 가능성이 있기 때문이다. **저장하지 않는 것이 가장 강한 무결성 보장**이라는 원칙.

### 7-2. 커밋 메시지 태그 — 강한 규칙 + 단일 source of truth

**모든 커밋 메시지 본문에 해당 작업의 id를 반드시 포함한다.** 이 태그는 task 추적의 single source of truth다. 태그가 누락되면 해당 commit은 작업의 이력에서 영구적으로 사라진다.

```
<type>(<scope>): <short summary>

Task: 2026-04-13_01_<slug>
```

한 commit이 여러 작업에 걸치면 `Task:` 라인을 여러 개 넣는다.

**재구성 명령** (catalog frontmatter에 저장하지 않는 모든 것은 이걸로 답한다):

```bash
# 이 task의 commit 목록 (chronological)
git log --grep="Task: <id>" --reverse

# 이 task가 만진 파일
git log --grep="Task: <id>" --name-only --pretty=format: | sort -u

# 가장 마지막 commit (= "head" 의미가 필요한 경우)
git log --grep="Task: <id>" --format=%H -n 1

# task의 commit 개수
git log --grep="Task: <id>" --format=oneline | wc -l
```

이 중 어느 것도 catalog 파일에 저장하지 않는다. 매번 git에 물어본다.

**`close_task.py` / `new_catalog.py finalize`의 검증 알고리즘**:
1. `--status done`인 경우: `git log --grep="Task: <id>"` 결과가 1개 이상 존재하는지 확인. 0개면 close 거부(§6-3 abandoned 분기 참조).
2. catalog frontmatter에 `head_commit`/`files_touched`를 채우는 단계는 **존재하지 않는다**. status·closed_at·(필요 시) abandon_reason만 갱신.

**검출 보강**: 태그를 깜빡 누락하는 사고를 줄이기 위해 `warn_missing_task_tag.py` 훅이 매 `git commit` 직후 메시지를 검사하고 stderr 경고를 낸다(§11-3).

### 7-3. 본문에 해시를 박지 말 것

모든 해시는 프론트매터에만 둔다. 본문 인라인 해시는 일괄 갱신이 불가능하고 grep 비용도 높다.

---

## 10. 자동화 스크립트 (day-1 최소 셋)

| 스크립트 | 역할 |
|---|---|
| `new_task.py` | `docs/templates/plan-task.md`를 복사해 `docs/plan-task/<id>.md` 생성. `base_commit`을 현재 HEAD로 채움. plan-task 파일을 끝에 `git add`로 stage(close_task가 untracked fallback을 폐기했기 때문). 사용자가 첫 작업 커밋에 묶어 `Task: <id>` 태그로 커밋. |
| `new_catalog.py prepare <slug>` | trivial change(§3-1) 1단계: id 생성 + stub catalog(`status=draft`) 작성 + `git add`. id를 사용자에게 안내. derived 필드(`head_commit`/`files_touched`)는 만들지 않는다 — task id grep으로 재구성. |
| `new_catalog.py finalize <id>` | trivial change 2단계: `Task: <id>` 태그 commit이 1개 이상 존재하는지 확인하고 `status=draft → done`으로 승격, `closed_at` 채움. 그뿐. derived 필드는 박지 않는다. |
| `close_task.py` | **2-phase** (preflight → apply). **preflight**: src 존재, dst 미존재, plan-task tracked(또는 `--adopt-untracked` 복구 모드), done이면 `Task: <id>` 태그 commit ≥1 존재. dirty worktree는 fail-soft 경고. **apply**: git mv → frontmatter write(`status`/`closed_at`/`abandon_reason`만) → `git add`. 검증 실패 시 변경 0. derived 필드는 박지 않는다 — `git log --grep="Task: <id>"`가 single source of truth. `--status abandoned`는 태그 commit 0개 허용 + `--reason` 필수. `--adopt-untracked`는 복구 전용 opt-in. |

**왜 이 셋인가**: 마감/직행/시작 세 상황 각각에 전용 스크립트가 하나씩. `close_task.py`가 마감 시 검증·이동을 단일 지점에서 결정적으로 수행한다. `new_catalog.py`는 trivial 직행을 자동화 — 손편집 유혹(특히 `files_touched` 손작성)을 차단하기 위해 스크립트로 묶었다.

**갭 메모 — `close_task.py` 후 별도 커밋 의무**: `close_task.py`는 `git mv`로 rename만 stage하고 frontmatter 갱신은 워킹트리에만 적용한다. 스크립트가 catalog 파일을 명시적으로 `git add`해 stage하지만, **커밋은 사용자/에이전트가 직접 수행해야 한다**. 잊으면 catalog가 git history에 들어가지 않은 채 다른 작업의 reset/rebase에 휩쓸려 사라질 수 있다. 이 별도 커밋 메시지에도 `Task: <id>` 라인을 포함한다. 즉 한 작업은 보통 **두 커밋**을 만든다 — (1) 작업 내용 커밋, (2) close_task의 산출물(catalog 이동) 커밋. trivial route도 동일 패턴 — (1) trivial 변경 + stub catalog 묶음 커밋, (2) `finalize` 산출물 커밋.

스크립트는 의사코드가 아니라 **실제로 돌아가는 최소 구현**이 있어야 한다. 없으면 워크플로우는 사람 성실성에 의존하게 되고, 그 순간 무너진다.

**이후 확장 (can defer)**: CI 통합, PR 체크, catalog 통계 대시보드.

---

## 11. CLAUDE.md 통합

Claude Code에는 glob 기반 조건부 규칙 로더가 없다. 조건부 로드는 가정하지 말고 다음 두 가지만 사용한다.

1. **CLAUDE.md에 핵심 규칙 명시** (항상 로드됨):

```markdown
## Documentation workflow
- 계획이 필요한 변경은 시작 전 `.venv/bin/python docs/scripts/new_task.py <slug>`로 `docs/plan-task/` 파일을 생성한다. trivial change는 `.venv/bin/python docs/scripts/new_catalog.py <slug>`로 catalog 직행 (§3-1).
- **모든** 커밋 메시지에 `Task: <id>` 라인을 반드시 포함한다. 이 태그는 `commits[]` 필드를 대체하는 강한 규칙이다.
- 작업 완료 또는 중단 시 `.venv/bin/python docs/scripts/close_task.py <id>`로 catalog로 이동한다. catalog 본문은 사후 손편집 금지.
```

2. **선택적 hook**: `.claude/settings.json`의 `Stop` 훅으로 "코드 변경이 있는데 plan-task/catalog 변경이 없으면 경고"를 걸 수 있다. 강제는 아니고 리마인더. 구체 정책은 §11-3.

3. **AGENTS.md 미러**: Claude Code 외 에이전트(Codex, Cursor, Aider, Devin, OpenHands, Copilot 등)가 인식하는 cross-tool 표준은 루트 `AGENTS.md`다. 필요 시 `CLAUDE.md`와 별개로 `AGENTS.md`를 두고 위 5줄과 동일한 워크플로 규약을 복제한다. 두 파일은 의도적으로 중복이며 — 독자(에이전트 종류)가 다르므로 동기화 부담을 감수한다. 동기화는 사람이 손으로 한다 (스크립트화하지 않음 — 이 정도 분량에서 또 하나의 자동화는 §11-1의 누적 압력 원칙에 어긋난다).

### 11-1. 누적 압력 경고

CLAUDE.md는 "항상 로드"라는 한 제약 때문에 **모든 조건부 규칙이 흘러드는 수챗구멍**이 된다. 스크립트 추가 → 사용 규칙 1줄, 다중 에이전트 사고 → 교훈 영구 조항, 이런 식으로 소리 없이 부풀고, 길이가 늘어날수록 개별 규칙의 구속력(신뢰 예산)이 떨어진다. 토큰 비용보다 **"읽긴 하지만 가중치 내려가는" 구간**에 진입하는 게 더 큰 위험이다.

대응 원칙:

- **새 규칙 추가 전 1줄 정당화**: "이 규칙이 hook/스크립트 배너/별도 문서로 갈 수 없는 이유"를 PR 설명에 적는다. 적을 게 없으면 CLAUDE.md에 넣지 말 것.
- **판단형 규칙만 남긴다**: 위반을 grep/훅/CI가 결정적으로 잡을 수 있는 규칙은 CLAUDE.md에서 빼고 그 탐지기를 만든다. 사람/에이전트의 판단이 필요한 것(trivial 경계, 설계 의도 변경, minority claim 재검증)만 남긴다.
- **길이 상한은 soft**: 섹션 린터는 단일 프로젝트 규모에서 또 하나의 dead policy 후보다. 수치적 상한보다 위의 1줄 정당화 규칙이 더 효과적이다.

### 11-3. 훅 정책

§11이 언급한 "선택적 hook"의 구체 범위. **훅은 규율의 본체가 아니라 마지막 경고등**이라는 원칙을 따른다. 소규모 솔로 코드베이스에서 훅 하나는 곧 소비자 하나 더 추가하는 일이고, §15의 dead policy 함정을 셸 훅으로 재현할 위험이 크다. 따라서 도입 기준을 좁게 둔다.

**도입 기준 (모두 충족)**:

1. 위반이 결정적으로 탐지 가능 (오탐 거의 없음)
2. 문서로만 두면 반드시 잊는 기계적 사항
3. **fail-open**: 경고만 한다. 차단 금지.

주기적 점검 규칙(예: "1주에 안 울리면 삭제")은 두지 않는다. **점검이 필요할 정도의 훅은 애초에 도입 자격이 없다** — 위 3개 기준을 통과한 훅은 자기 정당성이 자명해야 하고, 그렇지 않으면 추가하지 않는다.

**도입할 훅 (5개)**:

| 이벤트 | 매처 | 동작 |
|---|---|---|
| `Stop` | always | 세션에 `src/` 변경이 있고 `docs/plan-task/` · `docs/catalog/` 변경이 없으면 stderr 경고 1줄. trivial change면 무시 가능. |
| `Stop` | always | 코드 경로(`src/`·`tests/` 등, 프로젝트별 설정) 변경 LOC가 임계값(기본 5)을 넘고 `.codex_review_head` 마커가 현재 HEAD와 다르면 codex review를 권하는 경고 1줄. 워킹트리 + unpushed 커밋 양쪽 모두 검출. 리뷰 후 `git rev-parse HEAD > .codex_review_head`로 마커 갱신해 경고를 끈다. |
| `PreToolUse(Bash)` | `^git mv .*plan-task.* catalog` | 수동 `git mv`로 plan-task를 catalog로 옮기려 할 때 경고. `close_task.py`를 쓰지 않으면 preflight 검증(Task 태그 commit 존재 등)과 frontmatter 일관 처리가 우회된다. |
| `PreToolUse(Edit\|Write)` | `^docs/catalog/.*\.md$` | 편집 대상이 catalog 하위 임의 마크다운(`<id>.md` 또는 `<id>/review/*.md`)이고 패치에 `files_touched:` 변경이 있으면 경고. 이 필드는 §6-3에서 1회 생성 후 절대 불변으로 못박힘. |
| `PostToolUse(Bash)` | `\bgit\s+commit\b` | `git commit` 직후 HEAD 커밋 메시지에 `Task: <id>` 라인이 없으면 stderr 경고 1줄. 누락 시 attribution(grep 기반)에서 silently 빠지는 위험을 알린다. fail-open이라 차단 안 함 — `--amend`로 사후 보정 가능. |

다섯 훅 다 **차단하지 않는다**. 경고만 띄우고 사람/에이전트가 넘길 수 있다. 차단형 훅은 깨진 중간 상태를 빠르게 스냅샷해야 하는 경우(디버깅 중 임시 수정, 실험 증거 보존 등)를 막아 작업 손실을 일으키므로 도입하지 않는다.

**도입하지 않는 훅 (자주 제안되지만 명시적으로 거부)**:

- **`git commit` 메시지에 `Task: <id>` 강제 (`commit-msg` 차단)**: 위의 PostToolUse 경고와 다르다. 차단형은 깨진 상태 커밋을 막아 실험 증거를 잃게 만들고, 결국 가짜 Task ID나 `--no-verify` 습관을 만든다. fail-open 경고가 두 위험을 모두 피하면서 검출 신호는 보존한다.
- **`SessionStart`에서 문서 상태 자동 주입**: 대규모 리팩터링 과도기에 매 세션마다 상태 리포트를 주입하면 전부 노이즈가 되고 신호가 죽는다. 주기적 수동 실행이 트리거 빈도와 신호 강도 양쪽에 적절하다.
- **`last_modified` 필드 PostToolUse 자동 갱신**: 그 필드 자체를 만들지 않는 게 첫 원칙이다 (§15의 파생 가능성 검사). git log로 충분히 파생된다.
- **plan-task 생성 강제 (`new_task.py` 미실행 차단)**: trivial 경계는 판단 문제다. 한 줄 상수 수정도 곧 `tests/`, 관련 모듈까지 번질 수 있다. 훅이 재단할 일이 아니라 §3-1의 사람 판단과 `new_task.py` 실행 시 배너로 충분하다.
- **catalog `files_touched` / `base_commit` / `head_commit` **차단**형 보호**: 차단은 과하다. 경고로 충분하고, 진짜 보호는 git history에 있다.

**훅 파일 위치 규약**: 훅 스크립트는 `docs/scripts/hooks/` 아래에 두고, `.claude/settings.json`에서 절대 경로로 호출한다. 각 훅 파일 상단에 `# Trigger: <event>` 주석으로 트리거 이벤트를 명시한다.

---

## 12. 예외 케이스

| 상황 | 처리 |
|---|---|
| plan-task가 방치됨 | 주기적으로 `plan-task/`를 훑어 N일 이상 업데이트 없는 active/blocked 작업을 찾는다. 사람이 판단해 이어가거나 `close_task.py --status abandoned`로 닫는다. |
| catalog의 `files_touched` 경로가 이후 삭제됨 | 그대로 둔다. 역사적 기록이다. `base_commit`에서 `git show`로 언제든 복원 가능. |
| 한 커밋이 여러 plan-task를 동시에 다룸 | 커밋 메시지에 `Task:` 라인을 여러 개 넣는다. `git log --grep`이 각 작업 단위로 정확히 매칭된다. |
| 완료 후 발견된 사이드이펙트 | 새 plan-task 또는 catalog 항목을 만들고, 그 문서의 본문에서 원본 catalog 파일을 참조한다. 원본은 수정하지 않는다. |
| trivial change (§3-1) | plan-task를 건너뛰고 catalog에 직접 작성. `base_commit`과 `head_commit`이 동일해도 무방. |
| 후속 작업이 기존 항목을 대체함 | 기존 catalog 항목의 프론트매터에 `superseded_by: <new-id>` 필드만 추가한다. 본문은 건드리지 않는다. |

---

## 13. 운영 가이드

### 부채 방지

- "모든 걸 문서화"를 목표로 하지 말 것. 범위가 좁아야 정확해진다.
- `plan-task/`가 쌓이면 대개 실제로는 abandoned인 것들이 섞여 있다. 주기적으로 훑어 `close_task.py --status abandoned`로 정리한다.

### 검색 패턴

```bash
# 특정 slug 관련 모든 작업 (plan-task + catalog)
rg -l "<slug-or-keyword>" docs/catalog/ docs/plan-task/

# 특정 task id의 commit 이력
git log --grep="Task: <id>"
```

프론트매터 필드명(`status` 등)과 프롬프트 키워드로 `rg`를 조합하면 대부분의 검색은 해결된다.

---

## 15. 부록: 채택하지 않은 대안

설계 과정에서 검토하고 기각한 대안들. 향후 재논의될 때 근거가 되도록 남긴다.

- **2-directory 안 (intent + worklog)**: plan-task와 catalog를 단일 `worklog/`로 합치고 `status:` 필드로 상태 구분. 더 단순하지만 "진행 중 목록"을 시각적으로 분리하기 어려워 리마인더 효과가 약해진다. 3-dir를 유지하되 이동 기반 생명주기로 간결성을 확보했다.
- **모든 변경에 plan-task 강제**: trivial change까지 4단계를 거치면 워크플로우가 첫 주에 무시된다. §3-1의 라우팅 규칙으로 경미한 변경은 catalog 직행을 허용했다.
- **feature branch + finalize 단계**: rebase/squash 환경의 사후 해시 재작성은 단일 main 환경에서 불필요. 브랜치 전략 도입 시 §7 확장.
- **코드 스냅샷을 changelog에 포함**: git show로 복원 가능하므로 중복. 예외는 사이드이펙트 섹션의 최소 조각.
- **prompt를 attribution의 최소 단위로**: 단위는 **작업(work_id = 파일 id)**이고 프롬프트는 `prompt_chain[]`으로 누적.
- **`commits[]` 프론트매터 필드**: `git log --grep='Task: <id>'`로 완전히 파생 가능하며, 프론트매터 드리프트 위험만 남는다. 제거하고 커밋 메시지 태그 규칙(§7-2)을 강한 규칙으로 승격했다.
- **`files_touched` 손편집 허용**: 사람이 쓰는 파일 목록은 실제 diff와 반드시 괴리된다. `close_task.py`가 `git diff --name-only`로 1회 생성하고 이후 불변.
- **`type` 필드 (feature/bugfix/refactor/docs)**: 어떤 스크립트도 타입으로 게이트하지 않으면 taxonomy drift가 빠르게 일어나 "fast filter"가 "low-trust filter"로 전락한다. 제거.
- **`depends_on: []` 필드**: 리졸버·스케줄러가 소비하지 않는 의존성 그래프는 손으로 유지되며 실제보다 빠르게 drift한다. 의존성 정보는 `blocked` 상태의 본문 진행 노트에 자연어로 기록.
- **`superseded` 별도 상태**: 드문 케이스에 여섯 번째 semantic bucket을 도입할 가치 없음. `superseded_by` 필드만 `done` 상태에서 선택적으로 부착.
- **확장 신호 섹션 (200 항목, worker suffix, 500줄 분할)**: 현재 스크립트가 소비하지 않는 투기적 미래 걱정은 dead policy.
- **wiki / 모듈 레지스트리 레이어**: 처음 설계에는 `docs/wiki/`(topics, reviews, modules, risk_tags)와 `_registry.yaml` 기반 메타데이터 레이어가 있었다. 소비자 스크립트(`check_stale.py` 등) 없이 손으로 유지되는 메타데이터는 수개월 내 dead policy로 전락했다. 하니스에서 제거. 필요한 프로젝트는 catalog의 `modules[]` / wiki 디렉토리 / stale 검출기를 함께 재도입해야 한다 — 부분 도입은 바로 drift 유발.
