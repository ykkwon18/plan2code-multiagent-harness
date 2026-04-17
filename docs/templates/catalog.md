---
id: <YYYY-MM-DD_NN_slug>
title: <한 줄 제목>
status: done                      # done | abandoned
started_at: <YYYY-MM-DD>
closed_at: <YYYY-MM-DD>
base_commit: <short-hash>         # 계획 시점 코드 스냅샷 (attribution 아님, §7-1)
# abandon_reason: |               # status=abandoned일 때만 필수
#   (왜 포기했는지)
# superseded_by: <new-id>         # 후속 작업이 대체할 때만
---

<!--
  derived value(head_commit, files_touched)는 frontmatter에 저장하지 않는다.
  이 task의 모든 commit과 변경 파일은 git에서 직접 재구성한다 (§7-2):
    git log --grep="Task: <id>"
    git log --grep="Task: <id>" --name-only --pretty=format: | sort -u

  trivial change(§3-1) 직행 시: 본문은 1~3줄 changelog만.
  plan-task에서 마감된 경우: plan-task 본문을 그대로 보존하고 아래 섹션만 덧붙인다.
-->

## 결과 요약
(최종적으로 무엇이 달라졌는가 — 2~4줄)

## 검증
- 테스트: …
- 수동 확인: …

## 사이드이펙트
(없으면 "없음". 있으면 해당 지점 최소 코드 조각 10줄 이내)

## 후속 조치
- [ ] 남은 TODO
