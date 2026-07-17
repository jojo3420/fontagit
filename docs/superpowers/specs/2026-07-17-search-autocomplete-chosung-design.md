# 설계 문서 — 검색어 자동완성(F-19) + 초성 검색(F-16)

> 작성일: 2026-07-17
> 대상 기능: 기획서 v3.0 F-19(검색어 자동완성 드롭다운, MUST), F-16(초성 검색, SHOULD)
> 상태: 브레인스토밍 확정 + Codex 리뷰(18건) 반영, 구현 대기
> 선행: 슬라이스2 F-04 알리아스 검색 완료(`search_fonts` RPC, 테스트 93/93)
> 리뷰 반영: `docs/review/review-result-20260717-124339.md`

---

## 1. 목표 한 줄

헤더 검색바에 글자를 입력하는 동안, 매칭되는 폰트를 실시간 드롭다운으로 제안한다. 매칭 범위는 별칭 정확/부분일치 + 오타(trgm) + 초성(ㅈㅁㅋ → 지마켓 산스)까지다. 이동은 항목 클릭/엔터로 폰트 상세(`/fonts/[slug]`)로 직행한다.

## 2. 범위와 비범위

**범위**
- F-16 초성 검색: `search_fonts` RPC에 초성 매칭 분기 추가 → 결과 페이지 검색도 자동으로 초성 지원.
- F-19 자동완성 드롭다운: 헤더 검색바(`HeaderSearch`)에만.

**비범위(이번 미포함)**
- `/search` 결과 페이지 입력창 자동완성 — 그 페이지는 이미 실시간 결과 목록을 그리므로 중복. 재사용 컴포넌트로 만들어 후속 이식 가능하게만 남긴다.
- F-17 실패어 로그 — 미구현 상태. 0건 안내까지만 하고 로그 연동은 후속.
- 어뷰징 방어, 검색 랭킹 고도화, 엘라스틱서치 도입(현 규모에서 과잉, 문서 판단).

## 3. 확정 결정 요약(브레인스토밍 결과)

| # | 결정 | 확정값 | 근거 |
|---|------|--------|------|
| 1 | 구현 범위 | F-16 초성 + F-19 함께 | 문서 확정 범위(초성 포함) 코드로 충족 |
| 2 | UI 부착 위치 | 헤더 검색바에만 | `/search`는 이미 실시간 결과 → 중복 회피 |
| 3 | 초성 엔진 | 저장 컬럼(생성 컬럼) + 색인 | 속도-유지보수, 자동완성은 호출 잦음 |
| 4 | 데이터 통로 | 기존 `search_fonts` 재활용 + `lim` 파라미터, 얇은 Route Handler | 결과 일관성, 공수 최소 |
| 5 | 하이라이트 | 프론트 계산(표시명 직접 매칭만) | 서버 응답 단순, 변경 유연 |
| 6 | UX 묶음 | 200ms 디바운스-8개-폰트명+제작사-상세직행-키보드-0건안내 | 눈누/카톡 이미지와 동일 체감 |
| 7 | 검색 백엔드 | PostgreSQL 유지(엘라스틱서치 미도입) | 수천 종 규모엔 PG로 충분, 서버비 0 원칙 |

## 4. 아키텍처 / 데이터 흐름

```
헤더 입력창(HeaderSearch)
  → 200ms 디바운스 + 요청 시퀀스 번호(마지막 응답만 반영) + AbortController
  → GET /api/suggest?q=...            (얇은 Route Handler)
  → lib/db/search.searchSuggestions(q, 8)
  → RPC fontagit.search_fonts(q, lim := 8)   ← 초성 분기 + lim clamp + foundry 반환
  → 오류=503 / 결과 0건=200 빈 배열
  → SearchSuggestions 드롭다운 렌더 + 프론트 하이라이트(표시명 직접 매칭만)
  → 클릭/엔터 → router.push(/fonts/[slug])
```

결과 페이지 검색(F-04)과 **같은 RPC-같은 정규화-같은 점수화**를 쓴다. 자동완성은 `lim` 값만 다르다(8 vs 20). 이로써 드롭다운 후보와 결과 목록이 어긋나지 않는다.

## 5. DB 계층 (마이그레이션 `0008_chosung_search.sql`)

실제 스키마(확인 완료): 스키마명 `fontagit`, 별칭 테이블 `fontagit.aliases`. `alias_norm text not null`은 **일반 저장 컬럼**(파이프라인이 `upsert_font` RPC로 직접 insert, 0002 확인)이므로 그 위에 생성 컬럼을 만들 수 있다. `fontagit.fonts.foundry` 존재.

### 5-1. 초성 추출 함수 `fontagit.to_chosung(text)`
- 입력 문자열을 **코드포인트 단위**로 순회. 한글 음절(가 U+AC00 ~ 힣 U+D7A3)이면 초성 인덱스 = floor((코드포인트 - 0xAC00) / 588), 초성 19자 배열 `[ㄱ,ㄲ,ㄴ,ㄷ,ㄸ,ㄹ,ㅁ,ㅂ,ㅃ,ㅅ,ㅆ,ㅇ,ㅈ,ㅉ,ㅊ,ㅋ,ㅌ,ㅍ,ㅎ]`에 매핑.
- 한글 음절이 아닌 문자(영문-숫자-자모-공백 등)는 **그대로 통과**.
- 선언: `language sql immutable strict`. IMMUTABLE은 생성 컬럼 필수 요건, STRICT는 NULL 입력 방어.
- ⚠️ 함수 정의를 나중에 바꿔도 이미 STORED된 `alias_chosung` 값은 자동 재계산되지 않는다. 함수 변경 시 컬럼 DROP → 재생성(또는 `UPDATE ... alias_norm = alias_norm`으로 강제 재계산) 절차를 마이그레이션에 포함한다.
- SSoT: 정규화된 `alias_norm`(NFC-공백제거-소문자, 0006)을 입력으로 받는다.

### 5-2. 초성 저장 컬럼 `fontagit.aliases.alias_chosung`
- `alias_chosung text generated always as (fontagit.to_chosung(alias_norm)) stored`.
- 별칭 저장-수정 시 자동 계산, 기존 행도 마이그레이션 시 자동 백필.
- 접두 매칭 색인: `create index idx_aliases_chosung on fontagit.aliases (alias_chosung text_pattern_ops)` — LIKE 'prefix%' 접두 검색이 색인을 타도록 `text_pattern_ops`. 실제 색인 사용 여부는 `EXPLAIN ANALYZE`로 구현 중 확인.

### 5-3. `fontagit.search_fonts` 재정의 (`q text, lim int default 20`)
- 기존 `search_fonts(q text)`를 `DROP FUNCTION`(CASCADE 금지) 후 `search_fonts(q text, lim int default 20)` 생성. `default 20` 덕에 기존 1-인자 호출(`/search` 페이지)이 그대로 동작.
- **lim 방어(함수 내부 강제)**: anon이 RPC를 직접 호출할 수 있으므로 함수 안에서 `lim`을 1~100으로 clamp하고 NULL/음수는 기본값으로. 클라이언트 신뢰 금지.
- 반환 컬럼에 `foundry text` 추가(nullable). 기존 컬럼(slug, name_ko, name_en, tier, category_ko, score) 유지.
- **초성 분기**: 정규화 결과 `v_normalized`가 초성 자모 19자로만 구성되면(문자 클래스 `[ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ]+`, 겹자모 ㄳㄵㄺ 등 제외) `alias_chosung LIKE v_normalized || '%'`(접두) 매칭으로 후보를 뽑고 초성 등급 점수(예: 45) 부여. 초성이 아니면 기존 매칭(정확 100 / 부분 50 / trgm 0~50).
- **집계-정렬은 기존 0006 구조 유지**: `from fonts f` + 별칭 `exists`로 폰트 단위 1행(중복 없음), `order by score desc, name_ko asc nulls last, name_en asc, slug asc` 동점 안정 정렬, `limit lim`.
- 권한: `revoke execute on function ... from public; grant execute on function ... to anon;`(0006 패턴). `security definer` + `set search_path = fontagit, pg_temp` 유지. published 필터로 비공개 폰트 미노출.
- 마이그레이션 말미: `notify pgrst, 'reload schema';` — PostgREST(Supabase) 스키마 캐시를 리로드해야 새 2-인자 시그니처가 즉시 인식된다(누락 시 일시적 404 위험).

### 5-4. 롤백
- 마이그레이션 하단에 롤백 SQL 주석: 인덱스 DROP → `alias_chosung` 컬럼 DROP → `to_chosung` DROP → `search_fonts`를 1-인자 원본(0006)으로 복원 → `notify pgrst`.

## 6. API 계층

> ⚠️ 구현 변경(PR #19 반영, 2026-07-17): `next.config.ts`가 `output: 'export'`(정적 내보내기)라 동적 Route Handler를 쓸 수 없다. 아래 `/api/suggest` 설계는 **미채택**하고, `useDebouncedSuggestions` 훅이 `searchSuggestions` RPC를 브라우저에서 직접 호출한다. 기존 `searchFonts`도 동일한 클라이언트 직접 호출 패턴이라 일관되며, 보안 경계는 하단의 RLS-published 필터-lim clamp-100자 제한으로 유지된다.

### `apps/web/app/api/suggest/route.ts` (신규 — 미채택)
- `GET`, 쿼리 파라미터 `q`.
- 검증: `q.trim()` 후 빈 문자열-100자 초과면 `200` + `{ items: [] }`(기존 `MAX_QUERY_LENGTH=100` 규칙 재사용).
- 정상: `searchSuggestions(q, 8)` → `200` + `{ items: [{ slug, nameKo, nameEn, foundry, tier, category }] }`.
- **오류(RPC/DB 예외)**: `503` + `{ items: [] }` + 서버 로그. 클라이언트는 503이면 드롭다운을 조용히 닫는다(0건 200과 구분). RPC 오류 메시지-키는 응답에 노출하지 않는다.
- 캐시 헤더: `Cache-Control: no-store`(실시간성). s-maxage 검토는 후속.

## 7. 데이터 계층 `apps/web/lib/db/search.ts`

- `RPCSearchRow`에 `foundry: string | null` 추가.
- `SearchResult`(types)에 `foundry` 추가 — 결과 페이지는 안 쓰면 그만(무해).
- `searchSuggestions(q: string, lim = 8): Promise<SearchResult[]>` 추가 — `supabaseClient.rpc('search_fonts', { q, lim })` 호출, 매핑 재사용. 기존 `searchFonts(q)`는 `{ q }`만 넘겨 그대로(하위호환).
- 예외는 throw하여 Route Handler가 503으로 흡수.

## 8. UI 계층

### `apps/web/components/SearchSuggestions.tsx` (신규, 재사용)
- props: `items`, `activeIndex`, `query`, `onSelect(slug)`, `onHover(index)`.
- 각 줄: 폰트명(name_ko 우선, 없으면 name_en) + 제작사(foundry, 있을 때만) + 무료/유료 뱃지(tier).
- **하이라이트**: `query`를 정규화 규칙과 동일하게 맞춰 **표시명(name_ko/name_en)에 직접 부분일치할 때만** 그 구간을 `<mark>` 강조. 별칭-오타(trgm)-초성 매칭은 표시명에 대응 구간이 없으므로 강조 없이 목록만 보여준다(헛 하이라이트 방지).
- 접근성: 입력에 `role=combobox`, `aria-expanded`, `aria-controls`(목록 id), `aria-autocomplete=list`, `aria-activedescendant`(활성 옵션 id). 목록 `role=listbox`, 항목 `role=option` + 고유 id. 색상 외 활성 표시(배경+테두리).

### `apps/web/components/HeaderSearch.tsx` (확장)
- 상태 추가: `suggestions`, `activeIndex`, `open`.
- 입력 변경 → `useDebouncedSuggestions`로 200ms 후 `/api/suggest` fetch. 이전 요청은 `AbortController` 취소 + **요청 시퀀스 번호**로 늦게 온 응답 무시(경쟁 조건 방어).
- 키보드: ↓/↑ 이동, **Enter는 `isComposing`(한글 조합 중)이면 무시**하고, 조합이 끝난 상태에서 활성 항목 있으면 상세 직행-없으면 기존 제출(`/search?q=`). ESC 닫기, 바깥 클릭 닫기.
- 항목 선택은 `onMouseDown` + `preventDefault`로 처리(입력 blur가 click보다 먼저 일어나 항목이 사라지는 문제 방지).
- 슬롯 높이 사전 확보로 레이아웃 밀림(CLS) 방지.

### `apps/web/hooks/useDebouncedSuggestions.ts` (신규)
- 입력값을 받아 디바운스+취소+시퀀스 처리, `{ items, loading, error }` 반환. `/search/page.tsx`의 cancelled 플래그 패턴 참고.

## 9. 오류-경계 처리

| 상황 | 처리 |
|------|------|
| RPC/DB 오류 | API 503 + 빈 배열. 훅은 503이면 드롭다운 조용히 닫기 + 서버 로그 |
| 결과 0건 | API 200 + 빈 배열. UI "결과 없음" 안내 줄. 실패어 로그(F-17)는 미구현→후속 |
| 늦게 온 응답 | AbortController + 요청 시퀀스 번호로 마지막 응답만 반영 |
| 빈/초과 입력 | 요청 안 보냄(200 빈 배열) |
| 한글 조합 중 Enter | isComposing이면 제출-이동 모두 무시 |
| 비한글-혼합 입력 | to_chosung 안전 통과, 초성 분기 아니면 기존 매칭 |
| 초성+음절 혼합("ㅈ마켓") | 초성 전용 클래스 불일치 → 기존 매칭 경로. 순수 초성만 초성 매칭 |

## 10. 접근성-보안-성능

- **보안**: Supabase `anon` 키는 원래 공개 가능한 키다. 따라서 보안 경계는 "키 은닉"이 아니라 (1) RPC `published` 필터 + RLS로 비공개 폰트 미노출, (2) 입력 길이 100자 제한, (3) `lim` 함수 내부 clamp, (4) `security definer`로 최소 권한 실행이다. `service_role` 키는 서버에서도 이 경로에 쓰지 않는다. 검색을 서버 라우트로 통과시키는 이유는 입력 검증-오류 처리-향후 캐싱/레이트리밋의 중앙화이며, anon 키 은닉이 목적이 아니다(기획서 6장 "키 노출 방지" 표현은 이 의미로 해석).
- **성능**: 200ms 디바운스 + 요청 시퀀스로 호출 억제, `lim 8`로 응답 경량. 초성 색인(text_pattern_ops) 접두 검색, `EXPLAIN ANALYZE`로 색인 사용 확인. 현 데이터 규모(수백~수천 종)에서 PG로 충분.
- **접근성**: 키보드 전 흐름 조작, 색상 외 상태 표시, ARIA 콤보박스(8장).

## 11. 테스트 범위

- **SQL(DB)**:
  - `to_chosung('지마켓 산스')` = `ㅈㅁㅋㅅㅅ`(정규화 입력 `지마켓산스` → 5음절 5초성). 영문-혼합 통과, NULL 입력 STRICT.
  - `search_fonts('ㅈㅁㅋ', 8)`가 지마켓 산스 매칭. `lim` clamp(0-음수-1000 → 1~100), 1-인자 하위호환.
  - **권한 테스트**: anon 역할로 비공개(draft/archived) 폰트가 결과에 없음.
- **API**: `/api/suggest?q=지마켓` 응답 형식, 빈/초과 쿼리 200 빈 배열, RPC 오류 시 503.
- **컴포넌트**: 드롭다운 표시/숨김, ↓↑ 탐색, Enter(조합 중 무시 vs 조합 후 이동/제출) 분기, 표시명 직접일치 하이라이트-별칭 매칭 시 하이라이트 없음, ESC-바깥 클릭-mousedown 선택, 디바운스 호출 억제. 기존 `HeaderSearch.test.tsx`(제출-ESC) 회귀 유지.
- 화이트리스트 대상(초성 함수-RPC-API-핵심 컴포넌트)만 테스트, 커버리지 수치 목표 없음.

## 12. 변경/신규 파일 목록

| 파일 | 유형 | 내용 |
|------|------|------|
| `supabase/migrations/0008_chosung_search.sql` | 신규 | to_chosung, alias_chosung 컬럼+색인, search_fonts 재정의, notify pgrst, 롤백 주석 |
| `apps/web/lib/db/search.ts` | 수정 | searchSuggestions 추가, RPCSearchRow.foundry |
| `apps/web/lib/db/types.ts` | 수정 | SearchResult.foundry |
| `apps/web/app/api/suggest/route.ts` | 신규 | 얇은 Route Handler(200/503 분리) |
| `apps/web/hooks/useDebouncedSuggestions.ts` | 신규 | 디바운스+취소+시퀀스 훅 |
| `apps/web/components/SearchSuggestions.tsx` | 신규 | 드롭다운+하이라이트+ARIA |
| `apps/web/components/HeaderSearch.tsx` | 수정 | 드롭다운 연동, 키보드, IME, mousedown |
| 각 `*.test.tsx` / SQL 테스트 | 신규/수정 | 11장 범위 |

## 13. 브랜치-마이그레이션 운영

- 현재 `feat/slice3-click-tracking`은 클릭 트래킹 전용 → 이 기능은 새 브랜치 `feat/search-autocomplete`에서 진행.
- **전진 배포 순서**: DB 마이그레이션(dev 먼저 검증 → prod) → `notify pgrst` 확인 → 웹 배포. 웹이 2-인자 호출을 하기 전 DB에 새 함수가 있어야 한다.
- **롤백 순서(역순)**: 웹을 이전(1-인자 호출) 버전으로 먼저 되돌린 뒤 DB 마이그레이션 롤백. DB를 먼저 되돌리면 배포된 웹의 2-인자 호출이 깨진다.

## 14. 확인 완료-미해결

- **확인 완료**: `alias_norm`은 일반 저장 컬럼(0001) → 생성 컬럼 가능. dev 스키마 `fontagit`. 상세 라우트 `/fonts/[slug]` 실재. F-17 실패어 로그 미구현.
- **미해결(구현 중 조정)**: 초성 점수 등급(45 예시)과 정확/부분일치 정렬 우선순위 실데이터 미세조정. IME U+1100 계열 자모 변환은 후속(현재 U+3131 계열만 지원). `/api/suggest` 캐시 정책(no-store vs 짧은 s-maxage) 트래픽 후 재검토.
