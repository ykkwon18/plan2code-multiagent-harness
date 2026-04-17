한국어로 답변

## Multi-agent audits: re-verify minority claims

병렬 audit에서 1/N 에이전트만 주장하는 내용은 소스를 직접 재확인하기 전까지 적용 금지. 과거 1-of-N "fix"가 정상 코드를 오염시킨 전례 있음.

## codex review

유저 요청 없이 자율 사용. 공격적으로 spawn (gpt 200$ 계정).
- 자율 사용 상황: 디버깅 난항, 위험한 수정 계획, 사이드이펙트 예상, 수식 작업
- 기본: `--model gpt-5.4 --effort high`. 심층 분석 시 `--effort xhigh`
- effort: `none < minimal < low < medium < high < xhigh`

### 호출 방법

**MJS**: `node "$HOME/.claude/plugins/cache/openai-codex/codex/<version>/scripts/codex-companion.mjs"` (openai-codex 플러그인 설치 경로. 버전은 로컬 설치본 확인)

**task (rescue)** — 백그라운드 지원:
```bash
node <MJS> task --background --model gpt-5.4 --effort high "프롬프트"
# 옵션: --write (파일 수정 허용), --effort <level>, --model <model>, --prompt-file <path>
```

**review / adversarial-review** — mjs는 foreground만, 백그라운드는 Skill 경유:
```bash
# foreground (mjs 직접)
node <MJS> review
node <MJS> adversarial-review "focus text"
# 옵션: --base <ref>, --scope <auto|working-tree|branch>, --model <model>

# background (Skill 경유)
Skill codex:review --background
Skill codex:adversarial-review --background "focus text"
```

**status / result / cancel**:
```bash
node <MJS> status --all --json
node <MJS> status <job-id> --json
node <MJS> result <job-id>
node <MJS> cancel <job-id>
```

### 파일 단위 리뷰 루프

코드/수식/설정 파일 하나 수정 완료 시마다 2개 이상 병렬 spawn (`review` + `adversarial-review` 또는 `rescue` 조합). trivial docs-only 편집은 제외.

- 파일 저장 직후 spawn, 다음 파일 작업과 병렬로 결과 회수. 치명적 지적이면 중단 반영.
- 폴링은 `ScheduleWakeup` 3분. `sleep` 루프 금지.
- **재리뷰 최대 3회**: 피드백 반영 후 불확실하면 재spawn. 3회 후에도 미해결이면 사용자 보고.
- high로 미해결 시 `--effort xhigh`로 에스컬레이션.

## Documentation workflow

전체 규약은 `docs/documentation-workflow-guide.md`. 스크립트는 **`.venv/bin/python`으로 실행**.

- 계획 필요 시 `.venv/bin/python docs/scripts/new_task.py <slug>`. trivial이면 `new_catalog.py`로 직행 (사용자 동의 후).
- **모든** 커밋에 `Task: <id>` 라인 필수. 누락 시 이력에서 소실.
- 완료/중단 시 `.venv/bin/python docs/scripts/close_task.py <id> [--status done|abandoned]`. catalog 본문은 사후 손편집 금지.
- plan-task 진행 중 Phase 항목 완료마다 즉시 plan 문서 반영 (체크박스 `[x]` + 진행 노트). 몰아쓰기 금지.
- `docs/user_inbox/`는 유저가 넣은 연구계획서·proposal 원본이 영구 보존되는 read-only 앵커. plan 작성·구현 중 의도 충돌 시 여기를 single source of truth로 삼는다.

### Plan review lane

상세 절차: `docs/plan-review-methodology.md`. 아래는 자동 운영 규칙.

**진입 정책** — plan-task 생성 시 **기본으로 review lane 적용**. 생략하려면 사용자 동의 필요.

- **기본 동작**: plan 초안 작성 → 곧바로 review lane 진입. 별도 트리거 없음.
- **생략 제안 가능 조건** (이 중 하나 이상이면 "default lane 가도 될 것 같습니다" 제안):
  - 단순 trivial 수정 / 기계적 리팩토링
  - 명백한 one-line bugfix
  - docs-only 편집
  - 이미 review를 통과한 plan의 후속 기계적 확장 (범위·수식 변경 없음)
- **생략 절차**: 위 조건 근거를 1~2줄로 제시 + 유저에게 "review 생략하고 default lane으로 진행할까요?" 명시적 동의 요청. 동의 전까지는 review lane 유지.
- 애매하면 review lane으로 간다 (과잉 review 비용 < 누락 review 비용).

**Review 루프** (유저 지시 불요, 자율 실행):
1. plan 초안 작성 후 입력 패킷(`r1_packet.md`) 구성 → `docs/plan-task/review/<task-id>/`
2. codex 리뷰어 3~4명 병렬 spawn (`task --background --effort high`). 루브릭: 의도 무결성 / 실행 가능성 / 수식 정합성 / privilege·leakage / 검증 가능성 / 운영 비용
3. 결과 회수 → moderator 종합(`rN_moderator.md`): 합의 이슈 반영, 소수의견은 원문 재검증 후 채택 여부 결정 (다수결 금지)
4. plan 수정 → Round 2 동일 루프. critical/high unresolved 남으면 Round 3까지 허용
5. **GO/NO-GO gate**: critical 0개 + high 모두 해결/봉합 + acceptance 기준 명시 → GO. 아니면 NO-GO (사용자 보고)
6. **GO 시 변경 성격 판정 → 구현 착수 전 분기**:
   - **Semantic** (수식·아키텍처·원안 문서 해석이 결과를 바꿀 수 있음): 최종 plan 요약을 사용자에게 제시 + 명시적 승인 요청 → 동의 후 구현 시작
   - **Mechanical** (와이어링·리팩토링·마이그레이션·shape 정비·deps 범프 등 해석 여지 없음): 자율 구현 시작
   - 애매하면 semantic 쪽 (과잉 승인 비용 < 오해석 구현 비용)
7. **Decision point**: 제품/연구 의도 판단이 필요한 미결 항목은 선택지 + tradeoff 정리 후 사용자에게 질문. 임의 확정 금지

**구현 중 체크포인트**:
- **C1** (첫 구조 변경 직후): plan 인터페이스가 실제 코드와 맞는지 확인. drift 발생 시 plan 진행 노트 기록
- **C4** (close_task 직전): 최종 구현이 승인된 plan 범위 내인지 확인. 벗어났으면 catalog에 drift·이유 기록
