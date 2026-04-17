# Plan Review Methodology

`plan-task`를 바로 구현으로 넘기지 않고, 다중 리뷰어 검증 루프를 거쳐
실행 가능성과 의도 무결성을 먼저 다지는 방법론.

이 문서는 [documentation-workflow-guide.md](./documentation-workflow-guide.md)를
대체하지 않는다. 관계는 다음과 같다.

- `documentation-workflow-guide.md`: 작업 기록의 기본 생명주기와 파일 규약
- `plan-review-methodology.md`: 고위험 `plan-task`를 검증하는 운영 절차

즉 이 문서는 "언제 plan-task를 만들까"보다, "만들어진 plan-task를 어떻게
검증해서 안전하게 구현으로 넘길까"에 초점을 둔다.

---

## 1. 목적

이 방법론의 목표는 네 가지다.

1. 구현 시작 전에 plan의 **실행 가능성**을 검증한다.
2. 원 요구 문서의 **의도와 불변식**이 plan에서 손상되지 않았는지 본다.
3. 구현자가 혼자 plan을 재해석하며 drift하는 일을 줄인다.
4. 작업 중간에도 같은 기준으로 상태를 점검해, "이미 많이 만들었으니 그냥 간다"
   식의 관성 진행을 막는다.

핵심 원칙은 간단하다.

- plan 리뷰는 코드 리뷰의 대체물이 아니다.
- 코드보다 **먼저** plan을 검증하면 비용이 훨씬 싸다.
- 다중 리뷰어를 쓰더라도 **다수결**로 결정하지 않는다.
- 소수의견은 AGENTS 규칙대로 원문 재검증 후 채택 여부를 결정한다.

---

## 2. 적용 대상

모든 task에 이 절차를 강제하지 않는다. 아래 조건 중 1개 이상이면 적용 후보다.

- 수식, 손실함수, 확률모형, 좌표계, 시간축 해석이 핵심인 작업
- CTDE / leakage / privilege 경계가 중요한 작업
- 여러 모듈을 동시에 건드리는 구조 변경
- 의도 오독 시 사이드이펙트가 큰 작업
- 요구 문서 자체가 길거나 애매해서 재해석 위험이 큰 작업
- 구현 전에 대안 비교와 명시적 decision fixing이 필요한 작업

반대로 trivial 수정, 기계적 리팩토링, 명백한 one-line fix에는 과하다.

권장 운영은 2-lane이다.

- **default lane**: 일반 `plan-task` 후 구현
- **review lane**: 본 문서의 다중 plan-review 루프를 거친 뒤 구현

---

## 3. 역할

### 3-1. 요구 문서 작성자

- 사용자 또는 상위 설계 문서
- 해결하려는 문제, 비목표, 제약, 성공 조건의 원천

### 3-2. 메인 작업자 / 사회자

보통 메인 Claude Code가 맡는다.

책임:

- 요구 문서로부터 초기 `plan-task` 초안 작성
- 리뷰어들에게 동일한 입력 세트 배포
- 리뷰 결과를 분류하고 충돌을 정리
- 소수의견 재검증
- 수정된 plan 재배포
- 구현 시작/보류 결정

금지:

- 리뷰어 의견을 근거 없이 "분위기상" 요약
- unresolved 쟁점을 묻어둔 채 구현으로 넘기기
- 다수결만으로 수식/의도 문제를 확정하기

### 3-3. Codex 리뷰어

여러 명을 병렬로 붙일 수 있다.

책임:

- plan의 실행 가능성, 의도 일치, 테스트 가능성, side effect를 독립적으로 점검
- "문제 있다/없다"가 아니라 **근거 + 영향 + 권고안** 형태로 작성
- 구현 제안보다 먼저 plan의 모순, 누락, 오해를 찾는다

금지:

- 자유 감상문
- 사회자 문구를 그대로 되받아 쓰기
- 코드까지 마음대로 확장 설계하기

### 3-4. 최종 승인자

보통 사용자.

책임:

- unresolved decision point 중 제품/연구 의도와 연결되는 항목 확정

---

## 4. 산출물 구조

진행 중 위치:

`docs/plan-task/review/<task-id>/`

close 후 위치 (close_task.py가 자동 이동):

`docs/catalog/<task-id>/review/`

권장 파일:

- `r1_packet.md`: 리뷰어에게 배포한 입력 패킷
- `r1_codex-a.md`, `r1_codex-b.md`, ...: 개별 리뷰
- `r1_moderator.md`: 사회자 종합
- `r2_packet.md`, `r2_*.md`: 후속 라운드
- `summary.md`: 최종 합의, unresolved, 구현 gate 요약

권장 원칙:

- 라운드별로 파일을 끊는다.
- 사회자 문서는 "최종 결론"이 아니라 "현재 라운드의 판단 + 다음 액션"을 쓴다.
- 요구 문서, plan-task, moderator 문서를 서로 링크한다.
- plan-task 본문이 리뷰 파일을 참조할 때는 `docs/plan-task/review/<task-id>/...` 형태로 써둔다. close 시점에 `review/...` 상대경로로 자동 재작성된다 (close_task.py `_rewrite_review_paths`).

---

## 5. Round 0: 입력 정리

리뷰를 시작하기 전에 사회자는 먼저 입력을 고정한다. 최소 구성은 다음과 같다.

1. 요구 문서 원문
2. 현재 `plan-task`
3. 관련 코드/문서 경로
4. 이미 확정된 decision
5. 이번 라운드의 질문 목록

이 단계에서 plan 초안에는 최소한 아래 항목이 있어야 한다.

- 문제 정의
- 스코프 / 비목표
- 제약과 불변식
- 계획 단계
- 고려한 대안
- acceptance 기준
- open questions

이게 없으면 리뷰어가 같은 문서를 읽고도 서로 다른 문제를 검토하게 된다.

---

## 6. 리뷰 루브릭

리뷰어는 아래 루브릭을 기준으로 본다. 형식은 자유여도 되지만, 관점은 고정한다.

### A. 의도 무결성

- 요구 문서의 핵심 의도가 plan에 제대로 반영되었는가
- plan이 요구를 몰래 완화하거나 바꿔치기하지 않았는가
- 용어 정의가 코드 의미와 어긋나지 않는가

### B. 실행 가능성

- 현 코드베이스와 인터페이스 기준으로 실제 구현 가능한가
- 필요한 전제나 선행 작업이 누락되지 않았는가
- 단계 순서가 의존성에 맞는가

### C. 수식 / 의미 정합성

- loss, metric, target 정의가 서로 호환되는가
- 좌표계, 단위, 시간축, indexing, shape가 일관적인가
- "평가 지표는 있는데 그걸 학습하는 loss는 아닌" 식의 불일치가 없는가

### D. privileged / leakage / side effect

- plan이 train/test 비대칭 정보를 몰래 끌어오지 않는가
- offline GT와 online inference 경계가 명확한가
- 기존 모듈을 건드리지 않는다고 써놓고 사실상 깨는 구조는 아닌가

### E. 검증 가능성

- 구현 후 무엇을 테스트하면 되는지 plan만 보고 알 수 있는가
- smoke와 convergence 기준이 분리되어 있는가
- GO/NO-GO 기준이 애매하지 않은가

### F. 운영 비용

- 데이터/메모리/실험 시간이 현실적인가
- 라운드 수, 구현 범위, 산출물 크기가 불필요하게 비대해지지 않는가

---

## 7. 리뷰 코멘트 포맷

권장 포맷:

- 심각도: `critical`, `high`, `med`, `low`
- 위치: plan 섹션 또는 관련 코드 경로
- 주장: 무엇이 문제인가
- 근거: 왜 그런가
- 영향: 구현 시 어떤 실패로 이어지는가
- 권고: 어떤 수정이 필요한가

좋은 예:

- `high`: Gate 2 target 정의와 평가 지표가 수학적으로 맞지 않음.
  GaussianNLL은 residual variance를 학습하지 `σ²_gt`를 직접 맞추지 않으므로,
  현재 R² 평가 문구는 제거하거나 손실을 바꿔야 함.

나쁜 예:

- "좀 위험해 보임"
- "이건 아닌 듯"
- "개인적으로는 B안 선호"

---

## 8. 사회자 종합 규칙

사회자는 리뷰 결과를 아래 세 그룹으로 나눈다.

### 8-1. 합의된 이슈

2명 이상이 독립적으로 지적했고, 원문 재검증에서도 맞는 항목.

처리:

- plan에 반영
- 수정 사항을 명시
- 다음 라운드에서는 "반영 후 남은 우려"만 다시 본다

### 8-2. 소수의견

1명만 제기했지만 치명적일 수 있는 항목.

처리:

- AGENTS 규칙대로 원문 또는 코드 재검증
- 사실 claim이면 재현/원문 확인 후 채택 여부 결정
- 해석 claim이면 decision point로 승격하거나 보류

금지:

- 1/N이니까 자동 폐기
- 사회자가 대충 맞는 것 같다는 이유로 채택

### 8-3. 취향 차이

정합성 이슈가 아니라 선호도 차이인 항목.

처리:

- plan 본문에 명시할 가치가 없으면 버린다
- 구현 자유도를 남길 수 있으면 "허용 범위"만 적는다

---

## 9. 라운드 운영

기본은 2라운드다.

### Round 1

목적:

- 큰 모순, 누락, 의도 오독, 실행 불가능 요소를 찾는다.

출력:

- major issue 목록
- decision point 목록
- plan 수정본 초안

### Round 2

목적:

- Round 1 수정이 실제로 문제를 해결했는지 확인한다.
- 새로 도입된 side effect를 본다.

출력:

- implementable / blocked 판정
- 남은 unresolved 목록
- 구현 중 체크포인트 정의

### Round 3

기본적으로 하지 않는다. 아래일 때만 한다.

- critical/high unresolved가 아직 남음
- Round 2에서 plan 구조가 크게 바뀜
- 수식 해석이나 의도 해석이 계속 갈림

라운드가 늘수록 품질이 자동으로 좋아지는 것은 아니다. 3회차부터는
"무엇을 다시 볼지" 범위를 줄이지 않으면 잡음이 늘기 쉽다.

---

## 10. 구현 시작 Gate

아래 조건을 만족하면 구현으로 넘긴다.

1. critical 이슈 0개
2. high 이슈는 모두 수정되었거나, 명시적 decision으로 봉합됨
3. open question이 구현 blocker인지 비-blocker인지 분류됨
4. acceptance / smoke 기준이 문서에 명시됨
5. plan drift를 감지할 체크포인트가 정의됨

권장 문구:

- `GO`: 구현 시작 가능. unresolved는 있으나 현재 phase blocker는 아님.
- `NO-GO`: 구현 시작 보류. 아래 이슈 해결 전 plan 승인 불가.

애매하게 끝내지 않는다.

### 10-1. GO 시 변경 성격 분기

GO 판정 직후, 구현에 들어가기 전에 변경의 성격을 분류하고 사용자 승인 필요 여부를 결정한다.

**Semantic** — 원안 문서(`docs/user_inbox/...`), 수식, 아키텍처 해석이 결과를 바꿀 수 있는 변경:

- 새 loss/reward 수식 도입 또는 수정
- 모델 구조(레이어 조합, attention 분기, pooling 방식 등) 결정
- 학습 패러다임 (CTDE·privileged·auxiliary task 구조 등)
- 프로토콜/인터페이스 의미론 정의 (token semantics, key contract)
- 원안 proposal의 다의적 문구에 대한 해석을 plan에 고정한 경우

→ **사용자 승인 필요**. moderator가 최종 plan 요약(해석 결정 포함)을 제시하고 명시적 승인을 구한 뒤 구현 시작.

**Mechanical** — 해석 여지 없이 결과가 일의적인 변경:

- 기존 스펙을 만족하는 와이어링·배선
- 이름 변경, 파일 분리·병합, 모듈 이동
- 동등한 표현으로의 리팩토링 (가독성·중복 제거)
- 스키마 마이그레이션, shape/dtype 정비
- 의존성 버전 범프, CI 설정 변경

→ **자율 구현**. moderator summary에 분류 근거만 1~2줄 남기고 바로 착수.

애매한 경계(예: "리팩토링인데 일부가 의미 변화"): semantic으로 분류. 과잉 승인 요청 비용 < 오해석 구현 비용.

판정 결과는 moderator의 `summary.md` 또는 마지막 `rN_moderator.md` 말미에 `변경 성격: semantic|mechanical` + 근거 1~2줄로 기록한다.

---

## 11. 구현 중 체크포인트 감사

plan review는 구현 시작 전에 끝나지 않는다. 다만 항상 상시 감시로 붙이면 비용이
크므로, 체크포인트 기반으로 부른다.

권장 체크포인트:

### C1. 첫 구조 변경 직후

- plan의 주요 인터페이스가 실제 코드 구조와 맞게 들어갔는지 본다.
- "구현하다 보니 바뀜"이 발생했는지 확인한다.

### C2. 첫 smoke 이전

- 테스트 데이터, loss wiring, key contract, shape contract를 본다.
- acceptance 기준이 실제 실행 가능하게 옮겨졌는지 확인한다.

### C3. plan drift 발생 시

징후:

- 새 wrapper / adapter / cache / dataset builder가 추가됨
- 원래 없던 privileged path가 생김
- 대안 중 기각했던 안으로 사실상 이동함

처리:

- `plan-task`의 진행 노트에 drift를 기록
- 필요하면 mini review round 재개

### C4. close_task 직전

- 최종 구현이 승인된 plan 범위를 벗어나지 않았는지 본다.
- 벗어났다면 catalog에는 drift와 이유를 남긴다.

---

## 12. Decision Point 관리

좋은 plan은 모든 것을 미리 결정하지 않는다. 대신 "무엇이 미결정인지"를
정확히 노출한다.

Decision point는 아래 조건을 만족할 때만 남긴다.

- 구현자가 임의로 정하면 의도가 바뀔 수 있음
- 두 선택지 모두 합리적이지만 결과가 달라짐
- 사용자 또는 상위 설계 판단이 필요함

권장 형식:

- 질문
- 선택지 A / B / C
- 각 선택지의 tradeoff
- 추천안
- 누가 결정해야 하는가

Decision point가 너무 많으면 plan이 아니라 브레인스토밍 문서가 된다.
정말 중요한 갈림길만 남긴다.

---

## 13. Anti-pattern

### A. 다수결 plan

리뷰어 3명이 말했으니 맞다고 확정하는 방식. 금지.

### B. 리뷰어를 설계 대행으로 쓰기

초안 plan이 빈약한 상태에서 리뷰어에게 사실상 설계를 떠넘기는 방식.

### C. 구현 후 역문서화

이미 코드가 나온 뒤 plan을 거꾸로 정당화하는 방식.

### D. unresolved 은닉

합의 안 된 쟁점을 사회자 문서에서 뭉개고 "대체로 괜찮음"으로 넘기는 방식.

### E. full rerun 집착

Round 2에서도 Round 1 전체를 다시 보게 해서 토큰과 시간이 낭비되는 방식.

---

## 14. 최소 운영안

처음부터 과하게 돌리지 말고, 아래 정도로 시작하는 것을 권장한다.

1. high-risk task에서만 적용
2. Codex 리뷰어 3~4명
3. 기본 2라운드
4. 사회자 문서는 `convergent / minority / decisions / next actions` 네 섹션 고정
5. 구현 중 체크포인트는 `C1`, `C4` 두 번만

이 정도만 해도 "혼자 plan 오독 후 대형 수정" 위험은 꽤 줄어든다.

---

## 15. 권장 템플릿

### 15-1. `r<N>_packet.md`

```md
# Round N Packet

## Inputs
- requirement:
- current plan:
- relevant code:

## Review Questions
1. ...
2. ...

## Fixed Decisions
- ...

## Output Contract
- severity + claim + evidence + impact + recommendation
```

### 15-2. `r<N>_moderator.md`

```md
# Round N Moderator Summary

## Convergent Findings
- ...

## Minority Findings
- ...

## Decisions
- ...

## Required Plan Edits
- ...

## Go / No-Go
- ...
```

### 15-3. `summary.md`

```md
# Review Summary

## Final Status
- GO / NO-GO

## Locked Decisions
- ...

## Residual Risks
- ...

## Implementation Checkpoints
- C1
- C2
- C4
```

---

## 16. 권장 운영 조합

이 하니스에서는 다음 조합을 기본으로 삼는다.

- 사회자: 메인 Claude Code
- 리뷰어: Codex 다수
- 리뷰 라운드 산출물 위치: `docs/plan-task/review/<task-id>/` (진행 중) → `docs/catalog/<task-id>/review/` (close 후, 자동 이동)
- 코드 변경 후 별도 검토 흔적: `warn_codex_review.py`가 요구하는 review marker

특히 아래 종류의 task는 review lane을 적극 권장한다.

- reward shaping
- uncertainty / variance / calibration
- pairwise disagreement
- observation adapter / history cache
- CTDE 경계가 바뀌는 구조 수정

반대로 아래는 default lane이면 충분한 경우가 많다.

- 문서 수정
- 명백한 bugfix
- 이미 고정된 구조의 기계적 확장

---

## 17. 한 줄 요약

좋은 plan-review 루프는 "리뷰어를 많이 붙이는 것"이 아니라,
"사회자가 무엇을 다시 확인해야 하는지 분명한 상태에서 plan drift를 조기에 잡는 것"
이다.
