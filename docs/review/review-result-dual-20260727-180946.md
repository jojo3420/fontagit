# Dual Plan Review Report: 2026-07-27-home-revamp.md

> Generated: 2026-07-27 18:20
> Reviewers: Codex (gpt-5.5, xhigh) + Antigravity agy (Gemini 3.5 Flash High)
> Mode: **Degraded — Codex 단일 모델** (agy는 리뷰 대신 CLI 플래그 탐색 로그만 출력, 리뷰 무효 처리)

---

## 1. 모델별 리뷰 원문

- Codex: `docs/review/review-result-codex-20260727-180946.md` (27건 지적, 종합 7/10)
- agy: `docs/review/review-result-agy-20260727-180946.md` — **무효.** 프롬프트를 수행하지 않고 `--dangerously-skip-permissions` 플래그 조사만 수행함 (exit 0이지만 리뷰 내용 없음)

## 2. Claude 통합 크로스 리뷰

### 종합 소견

Codex 리뷰는 실행 모호성-검증 확실성 관점에서 유효 타격이 많다. 다만 [Blocker] 4건 중 실제 Blocker는 1건(Task 8 멱등성)이고, 2건은 이 세션에서 실측한 코드 원문 근거로 반박되며, 1건은 확인 결과 이미 동작한다. 나머지 지적 다수는 문서 명확화로 수용.

### 항목별 판정 (Codex 번호 기준, 전 건 원본-실측 대조)

| # | 지적 요지 | 판정 | 근거 |
|---|---|---|---|
| 1 | [B] created_at select 미확인 | 부분 동의 → Should | 실측: `lib/db/fonts.ts:13` `.select("*")` — 이미 조회됨. 근거 문서화만 추가 |
| 2 | [B] FontCard 전체 교체 위험 | 부분 동의 → Should | 계획의 교체 코드는 현재 파일 전문(33줄) 실측 기반이라 유실 없음. 단 실행 시점 드리프트 대비 "교체 전 대조" 지시 추가 |
| 3 | [B] preset useEffect 사용자 선택 덮어씀 | 비동의 → 패스 | preset은 HomeCompareSection useState 보관 — 참조 안정. 재렌더로 새 객체 생성 안 됨. 같은 프리셋 재클릭 시 재적용은 의도된 동작 |
| 4 | [B] Task 8 부분 실패 시 반쪽 데이터 | **동의 → Must** | insert_collection이 items 실패 후 재실행 시 "이미 존재" 스킵 → 빈 컬렉션 잔존. 멱등성 보강 필요 |
| 5 | plan_recategorization 반환 구조 느슨 | 부분 동의 → Nice | 테스트가 구조를 정확히 고정하고 있음 |
| 6 | resolve_category 시그니처 표기 불일치 | 동의 → Should | Interfaces 블록만 `list[str]` — 구현/테스트는 `list[str] \| None` |
| 7 | PATCH 검증 로그 의존 | 부분 동의 → Should | 재실행 changed=0은 있음. jq JSON 확인 명령 추가 |
| 8 | prod dry-run과 apply 한 스텝 | 동의 → Should | prod 상태는 dev와 다를 수 있어 prod 리포트 검토 후 apply로 분리 |
| 9 | 경로 기준(cwd) 혼동 | 동의 → Should | 명령은 apps/pipeline, git add는 루트 기준 — 명시 추가 |
| 10 | 최신순 전제 약함 | 부분 동의 → Nice | 실측: getAllFonts `.order("created_at", desc)` — 전제 유효 |
| 11 | invalid createdAt NaN | 부분 동의 → Nice | NaN 비교는 false → 뱃지 없음(안전한 기본값) |
| 12 | 한글 쿼리 인코딩 | 동의 → Should | 기존 buildFilterQuery가 URLSearchParams 사용 — 동일 패턴으로 통일 |
| 13 | FilterChip button/aria-pressed 전제 | 비동의 → 패스 | 실측: FilterChip 원문이 `<button aria-pressed={active}>` 렌더 확인됨 |
| 14 | 전체 보기 카드로 그리드 9개 | 부분 동의 → Nice | 의도된 구성(8종+링크 1). 문서에 의도 명시됨 |
| 15 | badge 좁은 화면 겹침 | 동의 → Should | .name 말줄임 + footRight 축소 방지 CSS 추가 |
| 16 | out/ 상세 라우트 검증 부족 | 비동의 → 패스 | Task 9 Step 3에 이미 존재 (`ls out/collections/` + 목록 index 부재 확인) |
| 17 | _redirects 호스팅 의존 | 부분 동의 → Nice | 설계 문서에 Cloudflare Pages 명시됨. 계획에도 한 줄 병기 |
| 18 | /#collections 헤더 가림 | 비동의 → 패스 | scroll-margin-top 반영 + Task 9 수동 체크 포함 |
| 19 | familyOf(null) 안전성 | 비동의 → 패스 | PAIRINGS slug 6종 모두 mock fontKey 非null. 기존 CompareCanvas와 동일 패턴 |
| 20 | PAIRINGS slug 데이터 테스트 분리 | 부분 동의 → Nice | 저비용 개선이나 필수 아님 |
| 21 | HomeCompareSection 클라 경계 | 비동의 → 패스 | CompareLazy-PairingPresets 모두 원래 클라이언트. 경계 변화 미미 |
| 22 | sort_order 10~13 하드코딩 | 동의 → Should | prod는 0~9 실측 확인, dev는 미확인 — dry-run 리포트에 기존 count/충돌 포함 |
| 23 | 후보 0개도 published 생성 | 동의 → Should | 사람 게이트가 있어 Must는 아니나 최소 후보 수 가드 추가 |
| 24 | prod 수렴 확인 부족(컬렉션) | 동의 → Should | prod에도 count=14 + item 수 Expected 추가 |
| 25 | pnpm start 애매 | 비동의 → 패스 | 실측: package.json `"start": "serve out"` |
| 26 | 모바일 시각 확인 부족 | 동의 → Should | Task 9 수동 체크에 모바일 폭 추가 |
| 27 | PR base main 의문 | 비동의 → 패스 | 현 브랜치가 main에서 분기, deploy.sh main 전용, 최근 릴리스 모두 main |

### 모델 합의도 분석

- 합의 지적: 0건 (agy 무효로 합의 판정 불가 — Degraded)
- Codex 단독: 27건 (동의 4 + 부분 동의 11 + 비동의 8 + Nice로 수용 4)
- Claude 자체 발견: dev DB collections 상태 미실측 → #22 반영에 포함

## 3. 통합 권고사항 (합집합)

### 즉시 반영 (Must)
1. Task 8 `insert_collection` 멱등성: 기존 컬렉션 존재 시 item 수 확인-보정, 최소 후보 수 미달 시 생성 중단 (#4, #23 통합)

### 검토 후 반영 (Should) — 본 리뷰 직후 계획 문서에 반영함
- #1 created_at select("*") 근거 명시 / #2 교체 전 현재 파일 대조 지시 / #6 시그니처 표기 통일 / #7 jq 검증 추가 / #8 prod 스텝 분리 / #9 경로 기준 명시 / #12 URLSearchParams 통일 / #15 badge CSS 방어 / #22 sort_order 충돌 리포트 / #24 prod 수렴 Expected / #26 모바일 체크

### 참고 (Nice-to-have, 미반영)
- #5 반환 구조 주석, #10 정렬 전제 테스트 고정, #11 invalid date 테스트, #14 그리드 9개 명시, #17 CF Pages 병기, #20 데이터 테스트 분리

## 4. 메타데이터

- Codex 종료 코드: 0 / agy 종료 코드: 0 (내용 무효)
- Codex 리뷰: `docs/review/review-result-codex-20260727-180946.md`
- agy 리뷰: `docs/review/review-result-agy-20260727-180946.md`
- 본 리포트: `docs/review/review-result-dual-20260727-180946.md`
