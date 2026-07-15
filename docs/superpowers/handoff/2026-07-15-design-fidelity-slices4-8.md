# 세션 핸드오프 — 2026-07-15 (디자인 정합, 슬라이스 4~8 인계)

> **모드**: superpowers (spec/plan + SDD) - 저장 관례 `docs/superpowers/`
> **Feature**: 디자인 정합 (fontagit-v2 목업 대비 실제 화면 90%+ 일치)
> **이전 세션 종결 사유**: 컨텍스트 길이 → 품질 유지 위해 인계
> **브랜치**: develop (미푸시, 로컬 커밋만). 작업 대상: `apps/web` (Next.js 16 웹)

## 한 줄 요약

폰트 상세(슬라이스1)-홈(2)-목록(3)을 목업과 90%+ 일치시켜 완료-검증했다. 남은 슬라이스 4(트렌드)-5(비교)-6(캔버스)-7(컬렉션)-8(등록)을 **동일한 흐름**으로 이어가면 된다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** — 컨텍스트 복원 순서:

1. **진행 원장(레저)을 읽는다 — 가장 중요**: `.superpowers/sdd/progress.md`
   - 태스크별 완료 상태-이탈 이력-결정-교훈이 durable하게 기록됨. 이게 SSoT.
2. **스펙을 읽는다**: `docs/superpowers/specs/2026-07-15-design-fidelity-v2-design.md`
   - 전체 슬라이스 정의-판정 배점(2.2)-프레임-라우트 매핑표(2.1)-수용한 차이(7).
3. **완료된 슬라이스 플랜 3개를 훑는다**(패턴 참고용): `docs/superpowers/plans/2026-07-15-design-fidelity-slice0-1.md`, `-slice2-home.md`, `-slice3-list.md`
4. **git 상태 확인**: `git log --oneline -25` (마지막 웹 커밋 `bb9d2af` = 슬라이스3 조립)
5. **아래 "다음 단계 → MUST"부터 시작** (슬라이스 4 트렌드).

---

## 작업 컨텍스트

### 사용자 원본 요청

> 디자인필터링(정합) 진행. `docs/design/fontagit-v2`(154KB 단일 HTML 다중 프레임)와 실제 화면을 **90% 이상 동일**하게 구현, 구현요소 빼먹지 말 것. 작업 결과물과 브라우저 스크린샷 비교(/e2e-Playwright)로 최대한 동일하게 맞출 것.

### 확정된 결정-제약 (반드시 준수, 뒤집지 말 것)

🔴 **must**:
- **색/토큰 재설계 금지**: `apps/web/styles/tokens.css`는 이미 목업과 일치. 기존 CSS 변수만 사용.
- **상단 네비 6개 유지**(폰트/트렌드/캔버스/비교/컬렉션/등록) — 목업의 미니멀 헤더(폰트/트렌드만)와 의도적 차이. **수용한 divergence**(헤더 채점에서 네비 항목 수/라벨 제외).
- **미들닷(가운뎃점) 렌더는 코드에서 `{String.fromCharCode(183)}`** 로 작성. 리터럴 가운뎃점 문자를 쓰면 저장 훅(replace-banned-symbols.sh)이 하이픈으로 치환해 디자인이 깨진다. (`→ › ✓ ✕ ₩`는 훅에 안 걸림, 그대로 사용 가능.)
- **커밋 위생**: 구현자는 `git add`에 **명시 파일만**. `git add .`/`-A`/`commit -a` 금지. `docs/**`-`.superpowers/**` 등 미추적 파일 커밋 금지.
- **PoC 아님, 정식 구현**. 인라인 스타일은 견본 fontFamily만 예외(`style={{ fontFamily }}`).

---

## 진행 상태 (Progress)

### 완료 (슬라이스 1~3) — 전부 로컬 develop 커밋

| 슬라이스 | 프레임 | 결과 | 시각검증(배점90+) |
|---------|--------|------|------------------|
| 0 데이터모델+공통 | - | License 확장(webfont/redistribution/type/priceFrom) + `lib/license.ts` | - |
| 1 폰트 상세 | 1g/6a | 2단(본문 + 사이드바 라이선스카드/무료대안카드), Breadcrumb/SpecimenBox/LicenseSummaryCard/AlternativesCard | 유료데스크톱~98/무료~97/다크~95/모바일~93 |
| 2 홈 | 1d | 2단(히어로+검색+칩 / 인기 TOP 10 패널), Hero 정합+WeeklyRankPanel | 데스크톱~96/다크~95/모바일~93 |
| 3 목록 | 1f | 2단(필터 사이드바 + 개수/정렬 툴바 + 미니멀 카드그리드), FontFilters/FontCard 미니멀 | 데스크톱~96/다크~95/모바일~92 |

- 검증: 전체 스위트 14파일/59 테스트 PASS, `npm run build` SSG 35페이지, tsc 0. 캡처 `docs/review/screens/{paid,free,home,list}-*.png`.
- 마지막 웹 커밋: `bb9d2af`.

### 남은 슬라이스 (4~8) — 스펙 섹션 5 + 2.1 매핑표 참고

| 슬라이스 | 프레임 | 라우트 | 핵심 갭(요약) |
|---------|--------|--------|--------------|
| 4 트렌드 | 1h | `/trends` | TOP 10 확장(주간/월간) 레이아웃 정합 |
| 5 비교 | 5a | `/compare` | 최대 3열 캔버스 + 공유 입력 동기화 |
| 6 캔버스 | 3a | `/playground` | 한 글자를 전체 폰트로 세로 스택, 딥그린 톤 |
| 7 컬렉션 | 8a | `/collections/[slug]` (+목록) | 서문 + 폰트별 한 줄 코멘트 |
| 8 등록 | 8b | `/submit` | 폼 레이아웃 + 검증 상태 정합 |

각 슬라이스는 모바일(4a/4b/4c) + 다크(9b)도 함께 검증.

---

## 확립된 실행 프로세스 (이대로 반복)

각 슬라이스마다:
1. **참조 팩 수집**: 서브에이전트(Sonnet)로 (A) 디자인 프레임 세부(라벨/숫자 정확히) + (B) 현재 라우트 코드 전문(page.tsx/컴포넌트/CSS)을 뽑는다. 디자인 HTML: `docs/design/fontagit-v2/project/FontAgit 화면 세트.dc.html`.
2. **슬라이스 플랜 작성**(writing-plans 패턴): `docs/superpowers/plans/2026-07-15-design-fidelity-slice{N}-{name}.md`. 태스크별 완전한 코드(플레이스홀더 금지) + TDD 스텝 + Global Constraints(위 제약 복사) + 시각검증 태스크. 커밋.
3. **SDD 실행**(subagent-driven-development): 태스크별 `scripts/task-brief PLAN N`로 브리프 추출 → 구현자 디스패치 → **컨트롤러가 diff 직접 검증** → 다음.
4. **시각검증**: dev 서버(`localhost:3000`, 이미 가동 중일 수 있음 / 없으면 `cd apps/web && npm run dev`)에서 Playwright로 라우트 캡처(데스크톱1280/모바일390/다크 data-theme=dark) → 디자인 프레임과 배점(모듈40/레이아웃30/간격-타이포20/텍스트10, 합격90) 비교 → 90 미만만 CSS 조정.
5. 레저(`.superpowers/sdd/progress.md`)에 태스크 완료 1줄씩 append.

### 🔴 반드시 지킬 교훈 (반복 확인됨)

- **저가 구현자(Sonnet)가 브리프에 코드 전문이 있어도 로직/CSS/테스트를 임의 변경하는 이탈이 잦다**(0.1 심각-1.4 중대-3.1 이탈 → 전부 Opus fix로 복원). **컨트롤러가 매 태스크 diff를 grep/git show로 직접 대조 검증**해야 잡힌다(리뷰어도 놓친 적 있음). 특히 테스트를 구현에 맞춰 조작하는 케이스 주의.
- **판단이 필요한 태스크(콘텐츠 제거/재구성)는 처음부터 Opus 구현자**로. 순수 verbatim 전사-조립은 Sonnet로 충분. Opus 전환이 fix 왕복을 없앤다.
- 디스패치 프롬프트에 항상: "브리프 verbatim 전사, 임의 변경 금지, 테스트 조작 금지, 커밋 명시 파일만, 미들닷은 String.fromCharCode(183)".
- 컴포넌트가 `@/lib/fonts`(fontKeyToVar)를 import하면 vitest에서 next/font/google 로더 에러 → `vitest.setup.ts`에 이미 목 존재(추가 작업 불필요).

---

## 블로커 - 미해결 (Blockers)

| # | 이슈 | 영향 | 다음 |
|---|------|------|------|
| 1 | ⚠️ Minor 2건(슬라이스1 유래, 비차단): `lib/data.ts` checkIntegrity가 webfont/redistribution을 enum-includes 대신 truthiness로 검증 / "무료=SIL OFL 아니면 throw" 정책(향후 non-OFL 무료 폰트 추가 시 오throw = misuse landmine) | 낮음(현재 데이터 정합) | PR 전 통합 final-review에서 교정 판단 |
| 2 | ⚠️ 동시성: 다른 세션이 develop에 **파이프라인/docs 커밋을 계속 인터리브**(예 32e77d5, 060e827, 0227e2e). 파일 도메인 비겹침(그쪽=apps/pipeline-docs, 이쪽=apps/web) | 낮음 | 공유 브랜치 히스토리 재작성 금지. 슬라이스 커밋 BASE는 매번 직전 HEAD로 잡을 것 |
| 3 | ⚠️ 슬라이스 1~3 별도 whole-branch final-review 미실시(1은 실시=APPROVED, 2-3은 컨트롤러검증+시각으로 게이트) | 낮음 | PR 시점에 슬라이스 1~3 통합 final-review 권장 |
| 4 | ⚠️ 미푸시: 전부 로컬 develop. PR/머지는 사용자 명시 필요(하드-리버스 액션) | - | 사용자 지시 시 develop→main PR |

---

## 다음 단계 (Next)

🔴 **MUST** (다음 세션 시작점):
- [ ] 슬라이스 4(트렌드 1h, `/trends`) 착수: 참조 팩 → 플랜 → SDD → 시각검증. (현재 `/trends`는 FilterChip 주간/월간 + TrendTable 2개 추정 — 참조 팩으로 확정)

🟡 **SHOULD**:
- [ ] 슬라이스 5~8 순차 진행(비교/캔버스/컬렉션/등록).
- [ ] 각 슬라이스 모바일+다크 캡처까지 배점 90+ 확인.

🟢 **NICE-TO-DO**:
- [ ] 블로커 #1 Minor 2건 교정(checkIntegrity).
- [ ] 목록 모바일 필터를 스택 대신 접이식 시트로(선택).
- [ ] 사용자 지시 시 develop→main PR + 통합 final-review.

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| 진행 원장(SSoT) | `.superpowers/sdd/progress.md` |
| 스펙 | `docs/superpowers/specs/2026-07-15-design-fidelity-v2-design.md` |
| 완료 플랜 | `docs/superpowers/plans/2026-07-15-design-fidelity-slice0-1.md`, `-slice2-home.md`, `-slice3-list.md` |
| 디자인 목업 | `docs/design/fontagit-v2/project/FontAgit 화면 세트.dc.html` |
| 웹 앱 | `apps/web` (라우트 `app/`, 컴포넌트 `components/`, 토큰 `styles/tokens.css`, 데이터 `data/`, `lib/`) |
| 시각 캡처 | `docs/review/screens/*.png` |
| SDD 스크립트 | `/Users/joel.silver/.claude/plugins/cache/claude-plugins-official/superpowers/6.1.1/skills/subagent-driven-development/scripts/{task-brief,review-package}` |
| 이 핸드오프 | `docs/superpowers/handoff/2026-07-15-design-fidelity-slices4-8.md` |

---

## 검증 상태 (슬라이스 1~3 기준)

| 항목 | 상태 | 비고 |
|------|------|------|
| 단위/컴포넌트 테스트 | ✅ 14파일/59 PASS | vitest |
| 빌드 | ✅ SSG 35페이지 | `npm run build` |
| tsc | ✅ 0 오류 | |
| 시각 정합 | ✅ 슬라이스1~3 각 3~4뷰 배점 90+ | Playwright 캡처 |
| whole-branch final-review | ⚠️ 슬라이스1만 실시(APPROVED). 2-3 미실시 | PR 시점 통합 권장 |
| PR/머지 | ⚠️ 미실시(미푸시) | 사용자 명시 필요 |

---

## 재개 프롬프트 (다음 세션에 그대로 복사-붙여넣기)

```
이전 세션(디자인 정합 작업)을 이어받습니다. 먼저 아래 핸드오프 파일을 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/superpowers/handoff/2026-07-15-design-fidelity-slices4-8.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. 진행 원장 `.superpowers/sdd/progress.md`(SSoT)를 읽는다
3. 스펙 `docs/superpowers/specs/2026-07-15-design-fidelity-v2-design.md`를 읽는다
4. 완료된 슬라이스 플랜 3개(docs/superpowers/plans/2026-07-15-design-fidelity-slice*.md)를 패턴 참고로 훑는다
5. `git log --oneline -25`로 현재 상태 확인(마지막 웹 커밋 bb9d2af)
6. 확정된 결정-제약(색/토큰 재설계 금지, 네비 6개 유지, 미들닷=String.fromCharCode(183), 커밋 명시파일만)을 반드시 준수 — 뒤집지 말 것
7. "확립된 실행 프로세스"와 "반드시 지킬 교훈"(Sonnet 이탈 잦음→컨트롤러 diff검증 필수, 판단 태스크는 Opus)을 그대로 따른다

그다음 슬라이스 4(트렌드 1h, /trends)부터 시작: 참조 팩 수집 → 슬라이스 플랜 작성 → subagent-driven-development로 구현(컨트롤러 diff 검증) → Playwright 시각검증(배점 90). 진행 전에 핸드오프를 읽었음을 확인하고 슬라이스 4 착수 계획을 한 줄로 보고해주세요.
```

---

✅ 핸드오프 메모 작성 완료. 다음 세션은 위 재개 프롬프트로 시작.
