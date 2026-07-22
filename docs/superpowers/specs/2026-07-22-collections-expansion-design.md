# /collections 컬렉션 확장 설계

작성일: 2026-07-22
상태: 설계 승인 대기 (브레인스토밍 산출물)
관련 이슈: (신규)

---

## 1. 배경과 문제 재정의

표면 문제는 "prod/dev `/collections` 페이지에 컬렉션이 3개뿐"이다. 하지만 실측 결과 진짜 병목은 두 가지다.

1. **컬렉션을 만드는 수단이 없다.** 현재 컬렉션은 시드 파일(`supabase/migrations/0003_seed_collections.sql`)에 3개가 하드코딩돼 있고, 자동 생성 로직도 관리 UI도 없다.
2. **폰트 분류 데이터가 빈약하다.** 폰트는 1,240종으로 충분하지만, 이들을 의미 있게 나눌 메타데이터(스타일 태그-굵기)가 대량 결측이다.

이 두 번째가 핵심이며, `/collections`와 `/fonts`가 **공유하는 근본 문제**다. 따라서 이 설계는 "컬렉션 페이지"만 고치는 게 아니라 두 페이지의 공통 데이터 토대를 세운다.

## 2. 실측 근거 (dev `fontagit.fonts`, published 1,240종, 2026-07-22 REST 조회)

값별 count는 정확치, 굵기-subset은 1,000행 샘플 기준.

| 항목 | 실측 | 함의 |
|---|---|---|
| category_ko(스타일) | 고딕 1,198 / 명조 20 / 장식 14 / 손글씨 8 | 고딕 96.6% 극단 편중 |
| license_type | custom-free 1,111 / OFL 128 / UFL 1, NULL 0 | 라이선스로는 거의 안 갈림 |
| is_commercial_free | 샘플 전부 true | "무료 상업용" = 전체, 축으로 무의미 |
| tags | 전부 빈 배열 `[]` | 스타일-무드 컬렉션 재료 없음 |
| weights(굵기) | 718/1,000 결측(빈 배열) | 굵기축 재료 72% 없음 |
| subsets(다국어) | 914/1,000 결측 | 다국어는 사실상 Tier A만 |
| source_tier | A 130 / B 1,110 | 견고 축 후보 |
| variants italic | 37/1,000 | 이탤릭 축 무의미 |

핵심 결론: **Tier B 1,110종(대량 폰트)은 "고딕"이라는 것 외에 아는 정보가 거의 없다.** 태그뿐 아니라 굵기-subset도 비어 있다.

## 3. 목표 / 비목표

**목표**
- 컬렉션을 3개에서 우선 10개 안팎(B단계)으로, 데이터 정비 후 수십 개(A단계)로 확대한다.
- 2단 계층(상위 축 → 하위 컬렉션)으로 조직한다.
- 자동 파이프라인 중심 + 에디토리얼 소수의 하이브리드로 운영한다.
- `/fonts`와 이중관리가 없는 **공유 데이터 엔진** 위에 세운다.

**비목표**
- `/collections` 폐기 후 `/fonts` 일원화(적대적 리뷰 대안 B) — 채택 안 함. 역할 재정의로 간다.
- 완전 자동 무제한 교차 컬렉션(얇은 페이지 양산) — 안 함.
- 컬렉션 관리용 어드민 UI 신규 구축 — 이번 범위 밖(규칙 엔진 + 시드로 갈음).

## 4. 아키텍처: 3층 + 4단계

**3층**
- **데이터층**: 폰트에 분류 메타데이터(굵기-태그)를 채운다. 눈누 재크롤링(enrich) 확장.
- **생성층(공유 엔진)**: 태그-속성 규칙으로 컬렉션을 자동 구성. `/fonts` 섹션과 같은 재료를 공유.
- **표현층**: `/fonts`는 용도 브라우징, `/collections`는 축별 착지 페이지 + 에디토리얼.

**단계(로드맵) — 0순위 정비를 앞에 신설**
- **0단계 (데이터 정비, 선행 필수)**: 굵기(weights)와 태그(tags)를 채운다. 이게 `/fonts` 섹션 복구와 컬렉션 자동화의 공통 토대.
- **B단계 (0단계 정비 후 착수)**: 견고 축(OFL-Tier A-명조-장식-굵기)으로 자동 컬렉션 → 10개 안팎.
- **A단계 (근본)**: 태그로 스타일-무드 컬렉션 대량화 + `/fonts` 섹션 균형 → 수십 개.

## 5. 역할 분담 (이중관리 제거)

- **`/fonts`**: 용도(본문-제목-브랜딩-손글씨-장식) 탐색 도구. 0단계 정비로 굵기가 채워지면 섹션 불균형이 해소된다.
- **`/collections`**: `/fonts`에 없는 축 — 스타일-무드(태그), 굵기-특성, 라이선스(OFL), 엄선(Tier A) — 을 2단 계층으로. + 사람이 만든 에디토리얼.

두 페이지는 **같은 데이터-규칙을 공유하되 표현만 다르게** 한다. 이것이 이중관리 리스크를 없애는 핵심.

## 6. 데이터 모델: DB 규칙 엔진

적대적 리뷰가 "코드 하드코딩 규칙"의 재빌드-유연성 열위를 지적 → **DB 규칙 엔진** 채택.

기존 `collections` 테이블(`supabase/migrations/0001`)에 컬럼 추가(신규 마이그레이션):

| 컬럼 | 타입 | 용도 |
|---|---|---|
| kind | text ('editorial'\|'auto') default 'editorial' | 자동/에디토리얼 구분 |
| rule | jsonb null | auto일 때 축-필터 정의. 예: `{"axis":"license_type","op":"eq","value":"OFL"}` |
| generated_at | timestamptz null | auto 컬렉션 마지막 갱신 시각 |
| noindex | bool default false | 임계값 미만 시 검색 제외 |

**auto 컬렉션 채우기 방식**: 빌드타임에 `rule`을 평가해 `collection_items`를 **materialize**(실체화)하고 `generated_at` 기록. 조회는 기존 경로(`collection_items` 조인) 그대로 재사용 → SSG(정적 생성)와 궁합. (동적 쿼리 대비 조회 단순, 갱신은 트리거로 해결.)

**중복 처리**: 같은 폰트가 auto+editorial 양쪽에 나타나는 것은 허용하되, UI에서 컬렉션 성격(자동/추천) 뱃지로 구분. `is_auto_generated`는 `kind`로 대체.

## 7. 2단 계층 - 표현 - SEO

**계층 구조**
```
[스타일-무드]  둥근 고딕 - 각진 고딕 - 제목용 고딕 - 귀여운 손글씨 …   (A단계, 태그 필요)
[굵기-특성]    다양한 굵기 - 가변 폰트                              (B단계, 0단계 굵기 정비 후)
[라이선스]     OFL 폰트 모음                                       (B단계)
[엄선]         에디터 추천(Tier A)                                 (B단계)
[에디토리얼]   새벽 감성 명조 - 카페 메뉴판용 …                       (사람 큐레이션)
```

**임계값 N**: 폰트 N종 미만 컬렉션은 노출/색인 제한. 잠정 N=12(writing-plans에서 실측 기반 확정). N 미만이면 `noindex=true`.

**SEO(thin content 방어)**
- 얇은 컬렉션은 `noindex`로 색인 제외(Google thin/duplicate 평가 회피).
- og:image = 컬렉션 대표 폰트 견본 자동 생성(기존 견본 렌더 재사용).
- description = 템플릿 자동 생성("무료 상업용 OFL 한글 폰트 N종 모음" 형태).
- 기존 sitemap/robots/GA4 파이프라인(`2026-07-18-sitemap-robots-ga4-design.md`)에 컬렉션 URL 편입.

## 8. 거버넌스 / 운영

- **태깅 검수**: 눈누 원본 태그는 출처가 명확해 신뢰도 높음. 자동 정규화(표준 태그 사전) 적용 후 **샘플 사람검수(10% 감사)**. 전수 수동검수(5천여 항목)는 비현실적이므로 배제. 기존 감사 거버넌스(`2026-07-18-prod-font-data-audit-design.md`) 재사용.
- **갱신 트리거**: 폰트 추가-tier 변경 시 파이프라인 끝단에서 auto 컬렉션 `rule` 재평가 → `collection_items` 갱신 → SSG 재빌드 트리거. "언제 재빌드하나"를 명시(예: 시드/정비 배치 직후).
- **효과 측정**: 컬렉션 클릭 - 컬렉션→폰트 진입을 GA4 이벤트로. 어느 컬렉션이 유효한지 데이터로 판단.

## 9. 리스크 & 미해결 질문 (writing-plans에서 해소)

- **눈누 재크롤링**: robots.txt 차단 - rate limit - 페이지 구조 변경(정규식 취약, `noonnu_enrich.py:188`) - 저작권/크롤링 정책. → 재크롤링 정책-백오프-구조변경 감지 필요.
- **태그 표준화 사전 미정**: "둥근/둥근폰트/동글" 정규화 규칙. 표준 태그 목록 정의 필요.
- **임계값 N 미정**: 축별 폰트 개수 실측으로 확정.
- **prod=dev 볼륨 가정**: 실측은 dev. prod 재확인 권장(메모리상 prod도 1,240종).
- **`/fonts` 현행 섹션 손상 실증**: 굵기 결측 시 `mappers.ts` 기본값 `[400]` → `sections.ts:51` 전부 body 분류 → headline 섹션 공백 가능. 라이브 확인 권장.
- **`/fonts` vs `/collections` UX**: 사용자가 두 경로를 혼동하는지 실사용 미검증.

## 10. 관련 기존 설계 / 코드 경로

**기존 설계(참조-재사용)**
- `docs/superpowers/specs/2026-07-18-noonnu-tier-b-enrich-design.md` — 눈누 enrich (0단계 굵기/태그 정비의 기반)
- `docs/superpowers/specs/2026-07-20-fonts-section-hierarchy-canvas-design.md` — `/fonts` 섹션 계층
- `docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md` — 감사/검수 거버넌스
- `docs/superpowers/specs/2026-07-18-sitemap-robots-ga4-design.md` — sitemap/SEO/GA4

**코드 경로**
- `apps/web/lib/sections.ts:49` — `sectionOf()` 자동 매핑
- `apps/web/lib/db/mappers.ts` — `rowToFont` weights 기본값 `[400]` (굵기 결측 함정 지점)
- `apps/web/lib/db/collections.ts` — `getAllCollections`, `getCollectionBySlug`
- `apps/web/app/collections/` — 목록/상세 페이지(SSG)
- `apps/pipeline/src/fontagit_pipeline/noonnu_enrich.py` — `extract_styles`(굵기), `build_proposal`. **`extract_tags()` 신규 구현 대상.**
- `supabase/migrations/0001_fontagit_schema.sql`(collections 스키마), `0017_font_audit_schema.sql`(tags 컬럼)

## 11. 착수 전 확정 항목 (듀얼 리뷰 반영)

2026-07-22 dual plan review(Codex gpt-5.5, xhigh) 반영. agy는 실패로 Codex 단독(Degraded). 상세: `docs/review/review-result-dual-20260722-153145.md`.

### 11-1. 구현 착수 전 필수 확정 (Must)
1. **materialize 실패 처리**: "임시 테이블 생성 → 검증 → 원자적 교체" 방식. 실패 시 기존 `collection_items` 유지(빈 페이지 정적 생성 방지).
2. **SSG 재빌드 트리거 구체화**: 재빌드 주체/조건/환경(develop-main-prod)을 명시. 어떤 데이터 변경이 어느 환경 재빌드를 유발하는가.
3. **rule jsonb 스키마 확정**: 고정 필드(`axis`, `op`, `value`, `minItems`, `sort`, `limit`, `noindexBelow`)와 허용값 목록 정의. 잘못된 rule의 빌드 붕괴 방지.
4. **눈누 재크롤링 fallback**: 실패 시 기존 데이터 유지, 실패 URL 기록, 재시도 제한, 수동 보강 파일 허용.

### 11-2. 검토 후 확정 (Should)
5. prod 데이터 검증을 writing-plans 첫 작업으로(dev vs prod의 fonts/collections/weights/tags 차이).
6. B단계 첫 자동 컬렉션 8~12개 목록 + 각 `rule` + 예상 개수.
7. 자동 컬렉션 내 폰트 정렬 기준(Tier A 우선/이름순/굵기 보유 우선 등).
8. noindex(검색엔진 색인 제외)와 내부 목록 노출 숨김을 분리 정의.
9. 태그 출처 3구분(눈누원본/자동추론/사람검수) + 출처별 신뢰도.
10. auto 컬렉션 slug 영속성 정책(rule 변경 시 slug/URL 유지 → SEO 링크 보호).
11. 태그 표준 체계(무드-형태 표준 태그 사전), 노출 임계값 N 확정값(축별 폰트 개수 실측 후).

### 11-3. 참고 (Nice-to-have)
- SEO description 컬렉션별 고유화 규칙(템플릿 반복 완화).
- auto 컬렉션 간 near-duplicate 감지.

> 다음 단계: 이 스펙을 writing-plans 스킬로 넘겨 0단계(데이터 정비) → B단계(자동 컬렉션) → A단계(태그 컬렉션) 순의 구현 계획으로 분해한다. 11-1 Must 4건은 각 단계 계획에서 우선 해소한다.
