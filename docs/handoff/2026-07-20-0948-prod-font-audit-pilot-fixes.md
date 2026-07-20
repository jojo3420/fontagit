# 세션 핸드오프 — 2026-07-20 09:48 KST

> **모드**: simple-change (연계 문서는 superpowers specs/plans)
> **Feature**: prod-font-data-audit — dev legal 파일럿 첫 실행-버그 수정
> **이전 세션 종결 사유**: 사용자 인계 요청 (컨텍스트 길어짐, 남은 갈림길 다수)

## 한 줄 요약

감사 파이프라인을 **처음으로 실제 실행**(dev legal 50종 파일럿)해 실행을 막던 **버그 3개를 발견-수정-커밋**했다. 실제 데이터 수집(verified)은 아직 0이며, 눈누 크롤링 정책 미승인(사용자 법적 판단)과 Google Tier A pending 때문이다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** — 복원 순서:

1. **이 핸드오프 파일을 읽는다**
2. **Plan/Design/이전 핸드오프를 읽는다**:
   - Design(spec): `docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md`
   - Plan: `docs/superpowers/plans/2026-07-18-prod-font-data-audit.md` (Task 12~13)
   - 직전 핸드오프: `docs/handoff/2026-07-19-2212-prod-font-data-audit-pipeline-verify.md`
3. **git 확인**: `git fetch && git log --oneline -5 && git branch --show-current`
   - 현재 작업 브랜치 `fix/audit-pilot-dev-font-id-mapping` (push됨, PR 미생성). 공유 워킹트리라 다른 세션이 브랜치를 바꿀 수 있음 — reflog로 확인 후 정렬.
4. **아래 "다음 단계 → MUST"부터 시작**

---

## 작업 컨텍스트

### 사용자 원본 요청
직전 핸드오프의 파이프라인 실행-검증 이어받기. 이번 세션 지시: (1) legal 50종 파일럿 실행 후 전수 `--all` 구현, (2) metadata 한글판별 우회는 Docker/colima로 처리.

### 사용자 제약-금지사항 (반드시 준수)
🔴 반드시:
- prod DB 쓰기-마이그레이션-배포는 **사용자 명시 승인 전 금지**. 자동 승인 금지(needs_review 게이트 유지).
- 다른 worktree의 미커밋 파일 미침해.
- 결정 사항 표(cmap 판정, 빈 subsets=미확인 등)는 뒤집지 않음(변경 시 사용자 확인).
- **눈누 크롤링 정책(crawl_allowed) 승인은 사용자만** 할 수 있는 법적 판단 — 임의 승인 금지.

---

## 이번 세션 성과 (증거)

### 실행 차단 버그 3개 해결
1. **allowlist 미기입(#82)**: `SUPABASE_AUDIT_DEV_ALLOWLIST`가 비어 dev 쓰기 자격증명 게이트에서 막힘 → `apps/web/.env.local`에 dev project ref(`zgxtfc…`) 채워 해결. (env 파일, gitignore)
2. **prod↔dev UUID FK 위반**: 파일럿이 prod 기준선 font_id를 dev DB에 직접 써서 `font_source_snapshots_font_id_fkey` 위반. prod 흰꼬리수리=`13f2a10d…`, dev=`a7b9d2f4…`(다름), dev fonts 1,294 vs prod 1,240.
3. **resolve_font_id select 버그**: 매핑 함수가 `select("id")`만 해서 name_ko 비교 불가 → 항상 None.

→ 커밋 `ca8a189` (fix 브랜치, push됨). 수정: `audit_store.resolve_font_id`(복합키 slug+NFC name_ko+source_tier, select에 name_ko/name_en 포함), `audit_runner._resolve_dev_font_ids`(dev 쓰기 전 치환, dry-run pass-through, 실패 시 ValueError), `__main__.main_audit_run` 호출, `tests/test_audit_resolver.py`(7종). 복합키 매칭 prod 1,240 전부 dev와 정확히 1:1(검증됨).

### 파일럿 결과 (dev, 실제 실행)
- 50종 dev 저장 성공(run `23c49d23…` completed). **verified 0 / needs_review 26(눈누) / pending 24(Google) / broken 0 / 외부 크롤링 0건**.
- 게이트 `pending remains`로 파일럿 미완료 처리 = **정상 안전 동작**.

---

## 결정 사항 (Decisions) — 뒤집지 말 것

| # | 결정 | 근거 |
|---|------|------|
| 1 | codex/prod-font-data-audit 브랜치 **병합 금지**(stale) | audit 코드-cmap 웹연동 이미 main 보유. 병합 시 #85 env SSoT 리그레션 |
| 2 | dev 저장 font_id 해석은 **B안: 안정키 복합키(slug+NFC name_ko+source_tier)** | dev에 font_sources(진짜 안정키) 0건, slug 100% 매칭. prod 적용 manifest는 기존대로 안정키 재해석 |
| 3 | metadata 한글판별은 **Docker/colima Linux 컨테이너**로 우회 | macOS는 `sys.platform` Linux 격리로 차단. colima 설치돼 있음 |
| 4~11 | 이전 세션 결정 유지 | cmap으로 한글 판정, 빈 subsets=미확인, 출처 우선순위(공식>공공>눈누 참고) 등 (design 3절) |

---

## 블로커-미해결 이슈

| # | 이슈 | 영향 | 다음 시도 |
|---|------|------|----------|
| 1 | 눈누 crawl_allowed=unknown(structured-only) | 실제 legal 수집 차단, verified 0 | 눈누 robots.txt-약관 확인 후 **사용자**가 crawl 승인. `output/audit/source-policy.json` + `docs/runbooks/prod-font-data-audit.md` |
| 2 | Google Fonts Tier A 24종 pending | 파일럿 게이트 미통과 | legal 단계 Tier A 처리 갭 조사(후보 URL/판정 로직) |
| 3 | metadata 실수집 macOS 불가 | 한글 subsets 못 채움 | Docker/colima Linux 컨테이너서 `font-audit-run --stage metadata` 실행 |
| 4 | 전수 `--all` CLI 미구현 | 파일럿(--limit)만 가능 | `font-audit-run`에 전수 옵션 구현 |
| 5 | dev에 잔여 run: 이전 실패 run(legal running) 1건 + 이번 파일럿 run(completed) | 재실행 시 running 누적 | service_role로 실패 run 정리(append-only 유의) |

---

## 다음 단계 (Next)

🔴 **MUST**:
- [ ] 눈누 robots-약관 확인 → 사용자 crawl_allowed 승인 여부 결정 → 승인 시 실제 legal 파일럿 재실행
- [ ] Google Tier A 24종 pending 원인 조사-수정 (게이트 통과 선결)
- [ ] fix 브랜치 PR 생성 여부-base 결정 (develop이 통합 브랜치. PR 링크: https://github.com/jojo3420/fontagit/pull/new/fix/audit-pilot-dev-font-id-mapping)

🟡 **SHOULD**:
- [ ] metadata: Docker/colima Linux 컨테이너 실행 경로 구축 → 한글판별 파일럿
- [ ] 전수 `--all` CLI 구현
- [ ] dev 잔여 run 정리

🟢 **NICE-TO-DO**:
- [ ] 파일럿 needs_review 52%(>10% 게이트) 대응: 제작사-문서 템플릿별 결정론적 규칙 보강

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| Design | `docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md` |
| Plan | `docs/superpowers/plans/2026-07-18-prod-font-data-audit.md` |
| 매핑 수정 | `apps/pipeline/src/fontagit_pipeline/audit_store.py`(resolve_font_id), `audit_runner.py`(_resolve_dev_font_ids), `__main__.py`(main_audit_run) |
| 테스트 | `apps/pipeline/tests/test_audit_resolver.py` |
| 파일럿 산출물 | `apps/pipeline/output/audit/pilot-legal.{json,md}` (gitignore) |
| 정책 | `apps/pipeline/output/audit/source-policy.json`, `docs/runbooks/prod-font-data-audit.md` |
| 기준선/bootstrap | `output/audit/prod-fonts-baseline.json`(1,240, 재생성됨), `bootstrap-manifest.json`(matched 1,238/unmatched 2=geist-mukta) |

---

## 검증 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| pytest | ✅ 187+7 passed | pipeline 전체 + test_audit_resolver |
| ruff | ✅ 통과 | |
| mypy | ⚠️ 1건 | `noonnu_seed.py:346` 기존 오류(범위 밖) |
| dev 파일럿 저장 | ✅ 50종 | run completed, FK/resolve 문제 없음 |
| 파일럿 게이트 | ⚠️ pending remains | 정상 미완료(수집 정책 미승인이 근본) |
| prod 적용 | ⛔ 미실행 | 사용자 승인 전 금지 |

---

## 재개 프롬프트 (다음 세션에 복사)

```
이전 세션 작업을 이어받습니다. 다음 핸드오프를 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/handoff/2026-07-20-0948-prod-font-audit-pilot-fixes.md

복원 순서:
1. 위 핸드오프 전체를 읽는다
2. Plan/Design/직전 핸드오프(2212)를 읽는다
3. git fetch && git log --oneline -5 && git branch --show-current 로 상태 확인 (fix/audit-pilot-dev-font-id-mapping)
4. "다음 단계 → MUST"부터 시작
5. 사용자 제약 준수: prod 쓰기-크롤링 정책 승인은 사용자 판단, 다른 worktree 미커밋 미침해, 결정 사항 표 유지
6. 결정 사항(cmap 판정, B안 매핑, Docker metadata 등)은 뒤집지 않음(변경 시 사용자 확인)

핸드오프를 읽었음을 확인하고, MUST 중 어디부터 시작할지 한 줄로 보고해주세요.
```
