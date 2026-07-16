# Slice 2: 알리아스 검색(F-04) Implementation Plan

**For**: Agentic workers (구현 전담) | **Goal**: 한/영/띄어쓰기 별칭 검색 백엔드+UI 완성  
**Status**: Implementation Ready | **Date**: 2026-07-16 | **Version**: 1.2

> v1.1 (2026-07-16): 슬라이스 0.5 완료 반영 — SQL 버그 B(trgm 점수 상수화)/C(유사도 대상을 alias_norm으로) 수정, normalize_search에 NFC 반영(결정 #3), 테스트 예시를 실데이터(본고딕/노토산스/나눔고딕)로 교체. 부분일치도 원문 이름 ILIKE 대신 alias_norm LIKE로 통일(공백 포함 이름과 정규화 쿼리 미스매치 해소).

> v1.2 (2026-07-16): PR #15 이연 반영 — RPC 오류 시 빈 배열 → throw로 계약 변경(오류 상태 UI 구분), URL q 동기화(replace), aria-live.

---

## Context

- **Spec**: `docs/superpowers/specs/2026-07-15-web-data-integration-design.md` (Slice 2 섹션, 6장 검색설계)
- **Master Plan**: `docs/fontagit-master-plan-v3.0.md` (6장 검색설계, 14-15장 운영정책)
- **Schema**: `supabase/migrations/0001_fontagit_schema.sql` (fontagit.fonts, fontagit.aliases)
- **RPC Pattern**: `supabase/migrations/0002_upsert_font_rpc.sql` (SECURITY DEFINER, set search_path)
- **Normalize Rule**: `apps/pipeline/src/fontagit_pipeline/uploader.py` L33-35: `normalize_alias = re.sub(r"\s+", "", alias.lower())`

### Key Decisions

1. **Normalization SSoT**: DB 정규화 함수(normalize_search)는 파이프라인 규칙과 동일 — **NFC → 공백제거 → 소문자** (0.5 스펙 4.3, 결정 #3)
2. **아키텍처**: 검색은 런타임 동적(output:export 환경에서 클라이언트가 anon key로 Supabase RPC 호출)
3. **UI 위치**: Header 검색 버튼(현재 미연결) → `/search` 라우트로 연결
4. **검색 결과**: published 폰트만, slug로 정적 상세 페이지 링크
5. **점수화**: 정확일치(별칭 정규화 완전 매칭) > 부분일치(ILIKE) > trgm 유사도

---

## Global Constraints

- ✅ **output:export 정적 유지**: 검색은 런타임 클라이언트→Supabase RPC 직접 호출
- ✅ **lib/db/ 계층화**: lib/db/search.ts 신설 (client.ts 재사용, mappers 준용)
- ✅ **정규화 SSoT**: DB normalize_search(text) = `LOWER(REGEXP_REPLACE(NORMALIZE(q, NFC), '\s+', '', 'g'))` — NFC → 공백제거 → lower 순서(파이프라인 normalize_alias와 동일)
- ✅ **마이그레이션 번호**: 0006 (0001~0004 기존, 0005 Tier A stale 폰트 동기화)
- ✅ **보안**: RPC SECURITY DEFINER, anon에게 execute 권한, 파라미터 바인딩으로 SQL 인젝션 차단
- ✅ **테스트**: 모킹(네트워크 없음) + pnpm test 단독 실행 가능
- ✅ **타입**: 100% Type Hints, 하드코딩 금지(Enum/Constants)

---

## Architecture

```
┌─────────────────┐
│ Header 검색버튼  │ → /search?q=...
└────────┬────────┘
         │
    ┌────▼───────────────────┐
    │  app/search/page.tsx    │  (Client Component)
    │  - input (debounce)     │
    │  - searchFonts() 호출    │
    │  - 상태: 입력/로딩/0건/결과
    └────┬───────────────────┘
         │
    ┌────▼──────────────────┐
    │ lib/db/search.ts       │  (Data Layer)
    │ - searchFonts(q)       │
    │ - client.rpc() 호출    │
    │ - 결과 매핑             │
    └────┬──────────────────┘
         │
    ┌────▼────────────────────────────┐
    │ Supabase RPC: search_fonts(q)    │  (Backend)
    │ - 정규화: q → normalize_search() │
    │ - 점수: 정확 > 부분 > trgm      │
    │ - 최대 20건, published만        │
    └────┬────────────────────────────┘
         │
    ┌────▼─────────────────────────┐
    │ DB: fontagit.aliases + index  │  (GIN trgm)
    │      fontagit.fonts           │  (published=true)
    └───────────────────────────────┘
```

### API Contract (search_fonts RPC)

**Input**:
```json
{
  "q": "본고딕"  // raw query (정규화는 DB 내부)
}
```

**Output** (최대 20건):
```json
[
  {
    "slug": "noto-sans-kr",
    "name_ko": "노토 산스 KR",
    "name_en": "Noto Sans KR",
    "tier": "free",
    "category_ko": "고딕",
    "score": 100
  }
]
```
웹 데이터 계층(search.ts)이 category_ko를 category로 매핑한다.

**Contract**:
- 점수: 정확 일치=100, 부분 일치=50, trgm 유사도=0~50
- 정렬: 점수 DESC, 동점 → name_ko ASC
- 빈/공백 q → 빈 배열 `[]`

---

## Global Constraints (Enforced)

| 제약 | 명시 방법 | 검증 |
|------|---------|------|
| 정규화 일관성 | DB normalize_search = 파이프라인 normalize_alias 동일 규칙 | test: 입력 동일 → 동일 결과 |
| 보안 경계 | RPC SECURITY DEFINER, set search_path=fontagit, anon execute only | code: grep "search_path", "grant execute" |
| 선택적 결과 | published 폰트만 | code: "status = 'published'" in RPC |
| 정적 export | 클라이언트→RPC 직접, 서버 라우트/ISR 금지 | code: "use client", client.rpc() |
| 타입 완전성 | SearchResult 인터페이스 정의, 매핑 로직 일치 | test: 타입 체크, tsc --noEmit |

---

## Task Breakdown

### Task 0: Pre-Flight Gate (코드 없음, 확인만)

**확인 사항**:
- [ ] dev Supabase pg_trgm 미설치가 정상(0006이 설치 예정), 설치 가능 여부 확인
- [ ] fontagit.aliases 데이터 존재 (슬라이스 0.5 완료: 폰트 137종/공개 130, 한글 별칭 보유 32종, name_ko 31종)
- [ ] Header.tsx 검색 버튼 UI 위치 (현 상태: aria-label="검색", 미연결)
- [ ] 검색 라우트 현황 (/search 없음, 신설 필요)

**검증 방법**: SQL Editor (dev Supabase)에서 2개 쿼리 실행
```sql
-- 1. pg_trgm 확장 확인
select extname from pg_extension where extname = 'pg_trgm';

-- 2. aliases 데이터 확인
select count(*) from fontagit.aliases;
```

**실패 시**: 계획 중단, "Task 0 실패 — pg_trgm 미설치 또는 aliases 데이터 부재" 보고

---

### Task 1: Migration 0006 (검색 백엔드)

**Files**:
- **Create**: `supabase/migrations/0006_search_fonts.sql`

**Interfaces**:
- **Produces**:
  - `fontagit.normalize_search(text) → text` — 정규화 함수
  - `fontagit.search_fonts(q text) → table(slug, name_ko, name_en, tier, category, score)` — RPC

**Steps**:

1. **실패 테스트**: SQL Editor에서 `select search_fonts('본고딕');` 실행 → 함수 없음 오류 확인
   
2. **pg_trgm 확장 설치**:
   ```sql
   create extension if not exists pg_trgm;
   ```

3. **정규화 함수 생성** (SSoT: 파이프라인 규칙 동일, 순서 NFC → 공백제거 → lower):
   ```sql
   create or replace function fontagit.normalize_search(q text) returns text
   language sql immutable
   as $$
     select lower(regexp_replace(normalize(q, NFC), '\s+', '', 'g'))
   $$;
   
   comment on function fontagit.normalize_search(text) is
     '별칭 검색 정규화: NFC → 공백제거 → 소문자. 파이프라인 uploader.py normalize_alias와 동일 규칙-순서.';
   ```
   (PostgreSQL `normalize()`는 PG13+ 내장. NFD 자모 분리형 입력도 NFC 완성형으로 통일 — 0.5 스펙 4.3)

4. **aliases.alias_norm 인덱스 추가** (trgm 유사도 검색용):
   ```sql
   create index if not exists idx_aliases_norm_trgm
     on fontagit.aliases using gin (alias_norm gin_trgm_ops);
   ```

5. **search_fonts RPC 생성** (핵심 로직 — 매칭은 전부 정규화된 `aliases.alias_norm` 기준):
   ```sql
   create or replace function fontagit.search_fonts(q text)
   returns table (
     slug text,
     name_ko text,
     name_en text,
     tier text,
     category_ko text,
     score int
   )
   language plpgsql
   security definer
   set search_path = fontagit, pg_temp
   as $$
   declare
     v_normalized text := normalize_search(q);
   begin
     if v_normalized = '' then
       return;
     end if;

     return query
     select
       f.slug,
       f.name_ko,
       f.name_en,
       case when f.is_commercial_free then 'free'::text else 'paid'::text end as tier,
       f.category_ko,
       case
         when exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm = v_normalized)
           then 100
         when exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm like '%' || v_normalized || '%')
           then 50
         else coalesce((
           select (max(public.similarity(a.alias_norm, v_normalized)) * 50)::int
           from aliases a where a.font_id = f.id
         ), 0)
       end as score
     from fonts f
     where f.status = 'published'
       and (
         exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm = v_normalized)
         or exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm like '%' || v_normalized || '%')
         or exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm operator(public.%) v_normalized)
       )
     order by score desc, f.name_ko asc nulls last
     limit 20;
   end;
   $$;
   ```
   **v1.1 교정 근거**:
   - 버그 B 수정: `similarity * 0`(항상 50 고정) → `max(similarity(...)) * 50`으로 실제 유사도 반영(0~50).
   - 버그 C 수정: 유사도 대상을 `fonts.name_en` → `aliases.alias_norm`(GIN trgm 인덱스 대상과 일치). 유사도 필터는 `%` 연산자(기본 임계 0.3, 인덱스 활용) 사용 — `similarity() > 0.3` 형태는 인덱스를 못 탄다.
   - 부분일치도 `alias_norm LIKE`로 통일: 원문 이름(공백 포함)과 정규화 쿼리(공백 제거)는 ILIKE 미스매치("노토산스" vs "노토 산스 KR"). alias_norm에는 이름 정규화형이 이미 적재돼 있고 gin_trgm_ops가 LIKE도 가속.
   - `name_ko asc nulls last`: 라틴 폰트 name_ko=null이 앞에 오지 않도록.
   ```sql

   revoke execute on function fontagit.search_fonts(text) from public;
   grant execute on function fontagit.search_fonts(text) to anon;
   
   comment on function fontagit.search_fonts(text) is
     'Slice 2 알리아스 검색. 입력을 정규화하고 별칭 정확일치(100점)→별칭 부분일치(50점)→trgm 유사도(0~50점) 순 점수화. published 폰트만, 최대 20건.';
   ```

6. **통과 테스트**: SQL Editor에서 4가지 케이스 실행 (실데이터 기준 — 슬라이스 0.5 적재분)
   ```sql
   -- 정확일치 (noto-sans-kr 통용 별칭 '본고딕' → 100점)
   select * from search_fonts('본고딕');
   -- 부분일치 (나눔고딕/나눔명조 등 다수 → 50점)
   select * from search_fonts('나눔');
   -- trgm 유사도 (오타 '본고딩' → 0~50점)
   select * from search_fonts('본고딩');
   -- 공백 별칭 정규화 ('본 고딕' → '본고딕' 정확일치)
   select * from search_fonts('본 고딕');
   ```
   → 각각 1건 이상 반환, score 내림차순 정렬 확인

7. **커밋**: `feat: 마이그레이션 0006 (검색 백엔드 — search_fonts RPC + pg_trgm)`

---

### Task 2: lib/db/search.ts (데이터 계층)

**Files**:
- **Create**: `apps/web/lib/db/search.ts`

**Interfaces**:
- **Consumes**:
  - `supabaseClient` (client.ts)
  - `SearchResult` 타입 (types.ts에서 export)
- **Produces**:
  - `searchFonts(q: string): Promise<SearchResult[]>`
  - `SearchResult` 인터페이스

**Steps**:

1. **types.ts에 SearchResult 추가** (기존 FontRow 아래):
   ```typescript
   export interface SearchResult {
     slug: string;
     nameKo: string | null;
     nameEn: string;
     tier: 'free' | 'paid';
     category: string;
   }
   ```

2. **search.ts 파일 생성** — RPC 호출 + 매핑:
   ```typescript
   import { supabaseClient } from './client';
   import type { SearchResult } from './types';

   /**
    * 별칭 검색을 Supabase search_fonts RPC로 실행하고 결과를 앱 타입으로 매핑한다.
    * 빈/공백 쿼리는 네트워크 요청 없이 빈 배열을 반환한다.
    */
   export async function searchFonts(q: string): Promise<SearchResult[]> {
     // 방어: 빈 검색어
     const normalized = q.trim();
     if (!normalized) {
       return [];
     }

     const { data, error } = await supabaseClient.rpc('search_fonts', {
       q: normalized,
     });

     if (error) {
       console.error('[search] RPC error:', error);
       return [];
     }

     if (!data || !Array.isArray(data)) {
       return [];
     }

     // 매핑: DB 행 → SearchResult
     return data.map((row: any) => ({
       slug: row.slug,
       nameKo: row.name_ko,
       nameEn: row.name_en,
       tier: row.tier as 'free' | 'paid',
       category: row.category_ko,
     }));
   }
   ```

3. **단위 테스트** (`search.test.ts` 신설):
   ```typescript
   import { describe, it, expect, vi } from 'vitest';
   import { searchFonts } from './search';
   import { supabaseClient } from './client';

   vi.mock('./client', () => ({
     supabaseClient: {
       rpc: vi.fn(),
     },
   }));

   describe('searchFonts', () => {
     it('빈 쿼리 → 빈 배열 (네트워크 요청 없음)', async () => {
       const result = await searchFonts('');
       expect(result).toEqual([]);
       expect(supabaseClient.rpc).not.toHaveBeenCalled();
     });

     it('공백만 쿼리 → 빈 배열', async () => {
       const result = await searchFonts('   ');
       expect(result).toEqual([]);
     });

     it('정상 RPC 응답 → SearchResult 배열로 매핑', async () => {
       const mockData = [
         {
           slug: 'noto-sans-kr',
           name_ko: '노토 산스 KR',
           name_en: 'Noto Sans KR',
           tier: 'free',
           category_ko: '고딕',
           score: 100,
         },
       ];
       vi.mocked(supabaseClient.rpc).mockResolvedValueOnce({
         data: mockData,
         error: null,
       });

       const result = await searchFonts('본고딕');

       expect(result).toEqual([
         {
           slug: 'noto-sans-kr',
           nameKo: '노토 산스 KR',
           nameEn: 'Noto Sans KR',
           tier: 'free',
           category: '고딕',
         },
       ]);
     });

     it('RPC 오류 → 빈 배열 + 에러 로깅', async () => {
       const mockError = new Error('RPC failed');
       vi.mocked(supabaseClient.rpc).mockResolvedValueOnce({
         data: null,
         error: mockError,
       });

       const result = await searchFonts('test');

       expect(result).toEqual([]);
       expect(supabaseClient.rpc).toHaveBeenCalledWith('search_fonts', { q: 'test' });
     });
   });
   ```

4. **통과 테스트**: `pnpm test lib/db/search.test.ts` → 모두 통과
5. **타입 체크**: `pnpm exec tsc --noEmit` → 0 에러
6. **커밋**: `feat: lib/db/search.ts (검색 데이터 계층)`

---

### Task 3: 검색 UI (app/search/page.tsx + Header 연결)

**Files**:
- **Create**: `apps/web/app/search/page.tsx`
- **Create**: `apps/web/components/SearchResult.tsx` (선택사항, 재사용 아이템)
- **Modify**: `apps/web/components/Header.tsx` (검색 버튼 → /search 연결)

**Interfaces**:
- **Consumes**:
  - `searchFonts()` from lib/db/search
  - `SearchResult` type
  - Header 검색 버튼 클릭
- **Produces**:
  - `/search?q=...` 페이지 (클라이언트 컴포넌트)
  - 4가지 상태 UI: 입력, 로딩, 0건, 결과 리스트

**Steps**:

1. **실패 테스트**: `/search` 페이지 접속 → 404 확인

2. **Header.tsx 수정** — 검색 버튼을 /search로 연결:
   ```typescript
   // 기존:
   // <button type="button" className={styles.iconBtn} aria-label="검색">
   //   <svg.../>
   // </button>

   // 변경:
   import Link from "next/link";
   
   <Link href="/search" className={styles.iconBtn} aria-label="검색">
     <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
       <circle cx="11" cy="11" r="7" />
       <path d="m21 21-4.3-4.3" />
     </svg>
   </Link>
   ```

3. **검색 페이지 생성** (`app/search/page.tsx`):
   ```typescript
   'use client';

   import { useState, useEffect, Suspense } from 'react';
   import { useSearchParams } from 'next/navigation';
   import Link from 'next/link';
   import { searchFonts } from '@/lib/db/search';
   import type { SearchResult } from '@/lib/db/types';
   import styles from './page.module.css';

   function SearchContent() {
     const searchParams = useSearchParams();
     const q = searchParams.get('q') || '';
     
     const [query, setQuery] = useState(q);
     const [results, setResults] = useState<SearchResult[]>([]);
     const [loading, setLoading] = useState(false);
     const [searched, setSearched] = useState(false);

     useEffect(() => {
       const timer = setTimeout(() => {
         if (query.trim()) {
           setLoading(true);
           setSearched(true);
           searchFonts(query).then((data) => {
             setResults(data);
             setLoading(false);
           });
         } else {
           setResults([]);
           setSearched(false);
         }
       }, 250); // debounce

       return () => clearTimeout(timer);
     }, [query]);

     return (
       <main className={styles.main}>
         <div className={styles.header}>
           <h1>폰트 검색</h1>
           <input
             type="text"
             placeholder="폰트명, 영문명, 별칭으로 검색..."
             value={query}
             onChange={(e) => setQuery(e.target.value)}
             className={styles.input}
             autoFocus
           />
         </div>

         <div className={styles.results}>
           {loading && <div className={styles.loading}>검색 중...</div>}
           {!loading && searched && results.length === 0 && (
             <div className={styles.empty}>검색 결과가 없습니다.</div>
           )}
           {!loading && results.length > 0 && (
             <ul className={styles.list}>
               {results.map((item) => (
                 <li key={item.slug} className={styles.item}>
                   <Link href={`/fonts/${item.slug}`}>
                     <div className={styles.name}>
                       {item.nameKo || item.nameEn}
                     </div>
                     <div className={styles.meta}>
                       <span className={styles.tier}>{item.tier === 'free' ? '무료' : '유료'}</span>
                       <span className={styles.category}>{item.category}</span>
                     </div>
                   </Link>
                 </li>
               ))}
             </ul>
           )}
           {!searched && <div className={styles.prompt}>검색어를 입력하세요.</div>}
         </div>
       </main>
     );
   }

   export default function SearchPage() {
     return (
       <Suspense fallback={<div>로딩...</div>}>
         <SearchContent />
       </Suspense>
     );
   }
   ```

4. **스타일시트** (`app/search/page.module.css`):
   ```css
   .main {
     max-width: 800px;
     margin: 0 auto;
     padding: 2rem 1rem;
   }

   .header {
     margin-bottom: 2rem;
   }

   .header h1 {
     font-size: 1.75rem;
     font-weight: 600;
     margin-bottom: 1rem;
   }

   .input {
     width: 100%;
     padding: 0.75rem 1rem;
     font-size: 1rem;
     border: 1px solid var(--color-border);
     border-radius: 0.5rem;
     font-family: inherit;
   }

   .results {
     min-height: 200px;
   }

   .loading, .empty, .prompt {
     text-align: center;
     color: var(--color-text-secondary);
     padding: 2rem 0;
   }

   .list {
     list-style: none;
     padding: 0;
     display: grid;
     gap: 0.75rem;
   }

   .item {
     border: 1px solid var(--color-border);
     border-radius: 0.5rem;
     padding: 1rem;
     transition: all 0.2s;
   }

   .item a {
     text-decoration: none;
     color: inherit;
   }

   .item:hover {
     border-color: var(--color-primary);
     background-color: var(--color-bg-secondary);
   }

   .name {
     font-weight: 500;
     margin-bottom: 0.5rem;
   }

   .meta {
     display: flex;
     gap: 0.75rem;
     font-size: 0.875rem;
     color: var(--color-text-secondary);
   }

   .tier, .category {
     background-color: var(--color-bg-secondary);
     padding: 0.25rem 0.5rem;
     border-radius: 0.25rem;
   }
   ```

5. **통과 테스트**: `/search?q=본고딕` 접속 → 입력창 + 로딩 상태 표시, 결과 렌더 확인
6. **커밋**: `feat: 검색 페이지 + Header 연결`

---

### Task 4: 계약 & 엣지 케이스

**Files**:
- **Modify**: `apps/web/lib/db/search.ts` (이미 Task 2에서 처리)

**Interfaces**:
- **Enforces**:
  - 입력 길이 제한 (100자)
  - 특수문자 필터 또는 허용
  - XSS 방지 (결과 텍스트 렌더)
  - 정규화 규칙 일관성

**Steps**:

1. **입력 검증** (search.ts에 추가):
   ```typescript
   export async function searchFonts(q: string): Promise<SearchResult[]> {
     // 기존 길이 체크
     if (!q || q.trim().length === 0) return [];
     
     // 추가: 길이 제한 (100자)
     if (q.length > 100) {
       return [];
     }

     // 기존 normalize → RPC 호출
   }
   ```

2. **UI 상태 완전성** (page.tsx — Task 3에서 이미 4가지 상태 포함):
   - ✅ 입력 대기: "검색어를 입력하세요"
   - ✅ 로딩: "검색 중..."
   - ✅ 0건: "검색 결과가 없습니다"
   - ✅ 결과: 리스트 렌더

3. **debounce 검증** (Task 3에서 250ms):
   ```typescript
   useEffect(() => {
     const timer = setTimeout(() => {
       // 검색 실행
     }, 250);
     return () => clearTimeout(timer);
   }, [query]);
   ```

4. **XSS 방지** (React 텍스트 렌더 사용, sanitize 불필요):
   ```typescript
   // ✅ 안전: JSX 텍스트 바인딩
   <div className={styles.name}>{item.nameKo}</div>

   // ❌ 위험: dangerouslySetInnerHTML 사용 금지
   ```

5. **SQL 인젝션 방지** (RPC 파라미터 바인딩, Task 1에서 이미 구현):
   ```sql
   -- ✅ 안전: 파라미터 바인딩
   select ... where alias_norm = v_normalized;

   -- ❌ 위험: 문자열 연결
   ```

6. **테스트**: search.test.ts에 케이스 추가
   ```typescript
   it('100자 초과 쿼리 → 빈 배열', async () => {
     const result = await searchFonts('a'.repeat(101));
     expect(result).toEqual([]);
   });
   ```

7. **커밋**: `refactor: 검색 입력 검증 강화`

---

### Task 5: 테스트 + 전체 검증

**Files**:
- **Modify**: `apps/web/lib/db/search.test.ts` (Task 2에서 생성)
- **Create**: `apps/web/app/search/page.test.tsx` (선택사항)

**Steps**:

1. **검색 데이터 계층 테스트** (Task 2에서 이미 정의):
   ```bash
   pnpm test lib/db/search.test.ts
   ```
   → 모든 케이스 통과 ✅

2. **정규화 규칙 일관성 테스트** (search.test.ts에 추가):
   ```typescript
   describe('정규화 일관성 (파이프라인 동일: NFC → 공백제거 → lower)', () => {
     // 클라이언트에는 정규화 함수가 없음(SSoT는 DB normalize_search).
     // 실검증은 Task 1/Task 5의 SQL Editor 케이스로 수행:
     //   normalize_search('  본 고 딕  ') = '본고딕'
     //   normalize_search(NFD 자모분리 '본고딕') = NFC '본고딕'  (0.5 스펙 4.3 교차 검증)
   });
   ```

3. **검색 페이지 통합 테스트** (page.test.tsx):
   ```typescript
   import { render, screen, fireEvent, waitFor } from '@testing-library/react';
   import userEvent from '@testing-library/user-event';
   import SearchPage from './page';
   import { searchFonts } from '@/lib/db/search';

   vi.mock('@/lib/db/search');

   describe('SearchPage', () => {
     it('초기 상태: "검색어를 입력하세요" 표시', async () => {
       render(<SearchContent />); // Suspense 필요하면 wrapper 추가
       expect(screen.getByText('검색어를 입력하세요')).toBeInTheDocument();
     });

     it('입력 후 debounce 250ms → searchFonts 호출 (1회)', async () => {
       vi.mocked(searchFonts).mockResolvedValueOnce([
         {
           slug: 'test',
           nameKo: '테스트',
           nameEn: 'Test',
           tier: 'free',
           category: '고딕',
         },
       ]);

       render(<SearchContent />);
       const input = screen.getByPlaceholderText(/폰트명/);
       
       await userEvent.type(input, '테스트');
       
       await waitFor(
         () => expect(screen.getByText('테스트')).toBeInTheDocument(),
         { timeout: 500 }
       );
     });

     it('검색 결과 0건 → "검색 결과가 없습니다" 표시', async () => {
       vi.mocked(searchFonts).mockResolvedValueOnce([]);

       render(<SearchContent />);
       await userEvent.type(screen.getByPlaceholderText(/폰트명/), '없는폰트');

       await waitFor(
         () =>
           expect(screen.getByText('검색 결과가 없습니다')).toBeInTheDocument(),
         { timeout: 500 }
       );
     });

     it('결과 클릭 → /fonts/[slug] 링크', async () => {
       vi.mocked(searchFonts).mockResolvedValueOnce([
         {
           slug: 'noto-sans-kr',
           nameKo: '노토 산스 KR',
           nameEn: 'Noto Sans KR',
           tier: 'free',
           category: '고딕',
         },
       ]);

       render(<SearchContent />);
       await userEvent.type(screen.getByPlaceholderText(/폰트명/), '본고딕');

       await waitFor(() => {
         const link = screen.getByRole('link', { name: /노토 산스 KR/ });
         expect(link).toHaveAttribute('href', '/fonts/noto-sans-kr');
       });
     });
   });
   ```

4. **전체 빌드 테스트**:
   ```bash
   pnpm test                    # 모두 통과
   pnpm exec tsc --noEmit      # 0 에러
   pnpm build                  # SSG 성공 (검색은 런타임이라 static page로 생성)
   ```

5. **정규화 SSoT 검증** (SQL Editor에서 수동):
   ```sql
   -- 파이프라인이 이미 normalize_alias(NFC → 공백제거 → lower)로 저장한 데이터 활용
   -- DB normalize_search 함수가 동일 규칙-순서인지 확인
   
   select normalize_search('  본 고 딕  ');                      -- "본고딕"
   select normalize_search(convert_from('\xe18487e185a9e186abe18480e185a9e18483e185b5e186a8'::bytea, 'UTF8'));
   -- NFD 자모분리 "본고딕" 입력 → NFC "본고딕" 반환 (0.5 스펙 4.3 교차 검증)
   ```

6. **커밋**: `test: 검색 페이지 + 정규화 일관성 테스트`

---

## File Summary

| 파일 | 타입 | 변경 | 목적 |
|------|------|------|------|
| `supabase/migrations/0006_search_fonts.sql` | Create | SQL | pg_trgm + normalize_search + search_fonts RPC |
| `apps/web/lib/db/search.ts` | Create | TS | searchFonts() 데이터 계층 |
| `apps/web/lib/db/search.test.ts` | Create | TS | search.ts 단위 테스트 |
| `apps/web/lib/db/types.ts` | Modify | TS | SearchResult 인터페이스 추가 |
| `apps/web/app/search/page.tsx` | Create | TSX | 검색 페이지 (클라이언트) |
| `apps/web/app/search/page.module.css` | Create | CSS | 검색 페이지 스타일 |
| `apps/web/app/search/page.test.tsx` | Create | TSX | 검색 페이지 통합 테스트 |
| `apps/web/components/Header.tsx` | Modify | TSX | 검색 버튼 → /search 연결 |

---

## Validation Checklist

### Before Merge

- [ ] Task 0: pg_trgm 설치 확인, aliases 데이터 존재 확인
- [ ] Task 1: SQL 마이그레이션 dev에 적용, 3가지 케이스 쿼리 동작 확인
- [ ] Task 2: `pnpm test lib/db/search.test.ts` 모두 통과
- [ ] Task 3: `/search?q=테스트` 페이지 4가지 상태 동작 (입력/로딩/0건/결과)
- [ ] Task 4: 입력 검증, XSS/SQL 인젝션 방지 확인
- [ ] Task 5:
  - `pnpm test` 모두 통과
  - `pnpm exec tsc --noEmit` 0 에러
  - `pnpm build` 성공 (SSG)
  - 사이트맵 생성 확인 (build/sitemap.xml 존재)

### Spec Coverage

- ✅ 정규화: NFC → 공백제거 → 소문자 (파이프라인과 동일 순서)
- ✅ 점수화: 정확(100) > 부분(50) > trgm(0~50, 실제 유사도 반영)
- ✅ 최대 20건, published만
- ✅ RPC SECURITY DEFINER, anon execute only
- ✅ 클라이언트 컴포넌트 (런타임 동적)
- ✅ 정적 상세 페이지 링크 (slug)

### Placeholder Scan

- ❌ 없음 (구체적 코드 제시)

### Type Consistency

- ✅ SearchResult 정의
- ✅ RPC 응답 매핑
- ✅ tsc --noEmit 0 에러

---

## Execution Handoff

**추천 Agent**: default-worker (Sonnet)

**이유**:
- 코드 생성/수정 5개 파일+
- 테스트 작성 (검색.test, 페이지.test)
- 통합 검증 (build, tsc)
- 구현 완료 후 테스트 실행 + 로그 첨부 필수

**입력**:
1. 이 계획 문서 전체
2. 참조 파일 경로 (스펙, 마스터 플랜, 스키마, 코드 샘플)
3. 실행 명령어: "Task 0 → Task 5 순차 실행. 각 Task 독립 테스트. 최종 `pnpm build && pnpm test` 성공 보고."

**검증 시점**:
- Task 0: SQL Editor 수동 확인 (사용자 확인 후 진행)
- Task 1~5: worker 자동 테스트 + 로그

---

## Timeline

| 작업 | 예상 시간 |
|------|---------|
| Task 0 (게이트) | 5분 |
| Task 1 (SQL 마이그레이션) | 20분 |
| Task 2 (search.ts + 테스트) | 15분 |
| Task 3 (검색 페이지 + UI) | 20분 |
| Task 4 (검증 강화) | 10분 |
| Task 5 (전체 테스트) | 15분 |
| **합계** | **약 85분** |

---

## Risks & Mitigations

| 리스크 | 완화 방법 |
|-------|---------|
| pg_trgm 미설치 | Task 0 게이트에서 중단. 사용자가 SQL Editor에서 create extension 실행 |
| RPC 권한 오류 | grant execute 명시 (Task 1). SQL Editor에서 \dp search_fonts 확인 |
| 정규화 규칙 불일치 | 파이프라인 uploader.py normalize_alias 코드 복사하여 DB 함수로 변환. 테스트로 입력 동일 → 결과 동일 검증 |
| 클라이언트 빌드 실패 | tsc --noEmit 조기 실행. 타입 수정. SearchResult 매핑 정확성 확인 |
| SSG 빌드 지연 | 검색은 동적이므로 정적 페이지 shell만 생성. 성능 영향 없음 |

---

## References

- 스펙: `docs/superpowers/specs/2026-07-15-web-data-integration-design.md`
- 마스터 기획: `docs/fontagit-master-plan-v3.0.md`
- 스키마: `supabase/migrations/0001_fontagit_schema.sql`
- 파이프라인: `apps/pipeline/src/fontagit_pipeline/uploader.py` (normalize_alias)
- 데이터 계층: `apps/web/lib/db/client.ts`, `fonts.ts`, `mappers.ts`

---

**Plan Version**: 1.1 | **Status**: Ready for Implementation | **Date**: 2026-07-16
