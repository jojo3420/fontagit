# Slice 1: 실데이터 연동 Implementation Plan

> **For agentic workers**
> 이 계획은 Supabase 기반 PostgreSQL 실데이터로 Next.js 정적 사이트를 완전히 전환하는 작업입니다.  
> 각 Task는 독립 실행 가능하게 설계했고, 테스트 커버리지는 task-slicer(TDD 진단)를 따릅니다.  
> 모든 커밋은 한국어 컨벤셔널 형식(`feat/fix/refactor/test: 설명`) 어트리뷰션 없음.

---

## Goal

목록/상세/컬렉션 페이지를 Supabase fontagit 스키마의 실데이터로 구동하되, 정적 내보내기(SSG, output:"export") 유지.  
폰트 견본은 시스템 폴백 대응, 트렌드는 클릭집계 완료 시까지 "최신 등록" 임시 랭킹으로 표시.

---

## Architecture

### 데이터 계층 신설: `lib/db/`
- **client.ts**: Supabase 클라이언트 (커스텀 스키마 `fontagit`)
- **types.ts**: DB row 타입 (FontRow, AliasRow, CollectionRow, CollectionItemRow)
- **mappers.ts**: row → Domain 객체 (rowToFont, rowToCollection)
- **fonts.ts**: fonts 조회 (getAllFonts, getFontBySlug, getAllSlugs, resolveFreeAlternatives)
- **collections.ts**: collections 조회 (getAllCollectionSlugs, getCollectionBySlug)

### 기존 계층 변경
- **lib/data.ts**: 파사드 — lib/db/* async 함수 위임, 목업 `checkIntegrity/assertDataIntegrity` 제거
- **lib/fonts.ts**: 폴백 헬퍼 추가 (familyOf: fontKey null → 시스템폰트)
- **data/fonts.ts, data/collections.ts, data/trends.ts**: 빌드타임 의존 해제 (목업 유지 → 다음 세션 제거)

### 페이지 패턴
- generateStaticParams: `await getAllSlugs()` async
- 페이지 함수: `async` + `await getFontBySlug()` 등
- 컴포넌트: fontKey null 폴백 처리 (familyOf 사용)

---

## Tech Stack

- **Supabase JS SDK**: `@supabase/supabase-js@^2`
- **빌드**: Next.js 16.2.10, output:"export", trailingSlash:true
- **테스트**: Vitest (TDD 부분 매핑)
- **환경**: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY

---

## Global Constraints

⚠️ **다음 주의는 모든 Task에 적용됩니다:**

1. **정적 내보내기 유지**: `next.config.ts`의 `output:"export"` 변경 금지.
   서버 컴포넌트는 빌드타임(generateStaticParams, generateMetadata) 데이터 fetch만.
   API route, 서버 상주 로직, 동적 렌더링 금지.

2. **계층 준수**: Supabase 접근은 **반드시** `lib/db/` 경유.
   페이지/컴포넌트에서 createClient 직접 호출 금지.

3. **fontKey Null 대응**: 실 DB에 fontKey 컬럼 없음 → Font.fontKey = `FontKey | null` (필드 변경).
   견본 렌더 시 null → familyOf() 헬퍼로 시스템폰트("Pretendard Variable", sans-serif) 폴백.

4. **슬라이스1 범위**: 
   - 읽기만 (fonts, collections, aliases).
   - 비교(CompareBoard), 캔버스(PlaygroundCanvas) 제외 (슬라이스3, 구글폰트 실서체 병행).
   - 쓰기(등록/검색/클릭) 제외 (슬라이스2~3).
   - data/fonts.ts, data/trends.ts 목업은 유지(다음 세션 제거 예정).

5. **Supabase 커스텀 스키마**: 
   ```typescript
   createClient(url, key, {
     db: { schema: 'fontagit' }
   })
   ```

6. **Next.js 주의 (AGENTS.md P0)**: 
   > "This is NOT the Next.js you know" — 버전 16.2.10은 최신 breaking 버전.
   > 코드 작성 전 `node_modules/next/dist/docs/` 확인 필수. 
   > generateStaticParams async, dynamic params 동작 검증.

7. **DB 스키마 사실 정정**:
   - fonts: `is_commercial_free` (boolean) → tier 매핑 ("free" if true, "paid" if false)
   - license.verifiedAt: DB에 `verified_at` 컬럼 없음 → **임시로 `last_modified` 사용**, 후속 스키마 추가 필요 ⚠️
   - weights: [] → [400] 기본값 (단일 굵기)
   - name_ko null → name_en 폴백

---

## Task 0 — 사전 확인 게이트 (코드 없음, 확인만)

**목표**: 구현 가능 여부 판정. 하나라도 실패 시 중단 신호.

### Interfaces
- Consumes: .env.local, Supabase 관리 UI, 실 DB
- Produces: 확인 결과 보고(OK/FAIL)

### Steps

- [ ] **.env.local 키 존재 확인**
  ```bash
  grep -E "NEXT_PUBLIC_SUPABASE_URL|NEXT_PUBLIC_SUPABASE_ANON_KEY" apps/web/.env.local
  ```
  판정: 두 키 모두 있고 값이 비어있지 않으면 ✅ (값 노출 금지, 마스킹만 확인)

- [ ] **Supabase fontagit 스키마 노출 확인**
  Supabase 대시보드 → "Database" → "Schemas" → `fontagit` 에 "Expose to PostgREST" 토글 ON 상태 확인.
  또는 터미널에서 anon key로 조회 시뮬:
  ```bash
  # 실제 요청 금지, UI 확인만
  # Supabase 대시보드의 SQL Editor에서 "SELECT 1 FROM fontagit.fonts LIMIT 1" 실행 후 anon 정책 검증
  ```
  판정: RLS 정책(anon_read_published_fonts) 존재 ✅

- [ ] **실 DB fonts 게시 데이터 확인**
  ```bash
  # 개발자가 직접 확인 (자동화 불가, anon 권한 제한)
  # Supabase 대시보드 SQL Editor: SELECT COUNT(*) FROM fontagit.fonts WHERE status='published'
  ```
  판정: published 폰트 1건 이상 있으면 ✅ (0이면 파이프라인 작업 필요, 구현 보류)

- [ ] **collections 시드 확인**
  ```bash
  # Supabase SQL Editor: SELECT COUNT(*) FROM fontagit.collections WHERE status='published'
  ```
  판정: 0개여도 ✅(빈 상태 정상, UI 처리), 1개 이상이면 더 좋음.

- [ ] **aliases 시드 확인**
  ```bash
  # Supabase SQL Editor: SELECT COUNT(*) FROM fontagit.aliases
  ```
  판정: 0개여도 ✅(alias 검색은 슬라이스2), 1개 이상이면 더 좋음.

**판정 기준**:
- Task 0 통과: 위 5개 중 1, 2, 3번이 모두 ✅ → Task 1 진행
- 실패 시: 사용자에게 보고 후 구현 중단

---

## Task 1 — supabase-js 설치 + client.ts

**목표**: Supabase 클라이언트 생성, 환경변수 검증.

### Files
- **Create**: `apps/web/lib/db/client.ts`
- **Modify**: `apps/web/package.json` (dependency 추가는 pnpm이 관리)

### Interfaces

**Consumes**:
- env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`

**Produces**:
- export const supabaseClient: SupabaseClient
- throws: clear error if env vars missing

### Steps

- [ ] **supabase-js 설치**
  ```bash
  cd apps/web && pnpm add @supabase/supabase-js
  ```
  확인: `package.json` dependencies에 `@supabase/supabase-js` 추가됨

- [ ] **client.ts 작성 (env 검증)**
  
  Create `apps/web/lib/db/client.ts`:
  ```typescript
  import { createClient } from '@supabase/supabase-js';
  
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  
  if (!url) throw new Error('NEXT_PUBLIC_SUPABASE_URL is required');
  if (!anonKey) throw new Error('NEXT_PUBLIC_SUPABASE_ANON_KEY is required');
  
  export const supabaseClient = createClient(url, anonKey, {
    db: { schema: 'fontagit' },
  });
  ```
  
  ✓ 확인: 파일 생성, env 누락 시 명확한 에러 메시지

- [ ] **빌드 검증 (타입 체크)**
  ```bash
  cd apps/web && pnpm tsc --noEmit
  ```
  확인: 타입 에러 없음

- [ ] **커밋**
  ```bash
  git add apps/web/package.json apps/web/pnpm-lock.yaml apps/web/lib/db/client.ts
  git commit -m "feat: Supabase 클라이언트 초기화 (fontagit 스키마)"
  ```

---

## Task 2 — 타입 조정 + mappers.ts (TDD)

**목표**: Font.fontKey를 nullable로 변경, DB row 매핑 규칙 정의.

### Files
- **Modify**: `apps/web/types/font.ts`
- **Create**: `apps/web/lib/db/types.ts`
- **Create**: `apps/web/lib/db/mappers.ts`
- **Create**: `apps/web/__tests__/mappers.test.ts`

### Interfaces

**Consumes**:
- db rows: FontRow, AliasRow, CollectionRow, CollectionItemRow
- specs: font.ts Font interface

**Produces**:
- Font (fontKey: FontKey | null)
- rowToFont(row: FontRow, aliases: string[]): Font
- rowToCollection(row: CollectionRow, items: CollectionItemRow[]): Collection

### Steps

- [ ] **types/font.ts 수정: fontKey nullable + Collection 타입 확장**
  
  Change line 24 from:
  ```typescript
  fontKey: FontKey;
  ```
  to:
  ```typescript
  fontKey: FontKey | null;
  ```
  
  Add new types before Collection interface (line 45 이전):
  ```typescript
  export interface CollectionFontItem {
    slug: string;
    nameKo: string;
    fontKey: FontKey | null;
    tier: Tier;
    comment: string;
  }
  ```
  
  Change Collection interface from:
  ```typescript
  export interface Collection {
    slug: string; title: string; intro: string;
    items: { fontSlug: string; comment: string }[];
  }
  ```
  to:
  ```typescript
  export interface Collection {
    slug: string;
    title: string;
    intro: string;
    items: CollectionFontItem[];
  }
  ```
  
  Also update TrendItem.font Pick (line 41) at usage site.

- [ ] **lib/db/types.ts 생성: DB row 타입 + CollectionFontItem**
  
  Create `apps/web/lib/db/types.ts`:
  ```typescript
  import type { FontKey, Tier } from '@/types/font';
  
  export interface FontRow {
    id: string;
    slug: string;
    name_en: string;
    name_ko: string | null;
    foundry: string | null;
    source_tier: string;
    category_ko: string;
    category_google: string | null;
    subsets: string[];
    variants: string[];
    weights: number[];
    is_commercial_free: boolean;
    license_type: string | null;
    license_verified: boolean;
    official_url: string;
    status: 'draft' | 'published' | 'archived';
    version: string | null;
    last_modified: string | null;
    created_at: string;
    updated_at: string;
  }
  
  export interface AliasRow {
    id: string;
    font_id: string;
    alias: string;
    alias_norm: string;
  }
  
  export interface CollectionRow {
    id: string;
    slug: string;
    title: string;
    intro: string;
    status: 'draft' | 'published' | 'archived';
    sort_order: number;
    created_at: string;
  }
  
  export interface CollectionItemRow {
    collection_id: string;
    font_id: string;
    comment: string | null;
    sort_order: number;
  }
  
  // Collection 매핑용: published 폰트 정보 포함
  export interface CollectionFontItemData {
    slug: string;
    nameKo: string;
    fontKey: FontKey | null;
    tier: Tier;
    comment: string;
  }
  ```

- [ ] **lib/db/mappers.ts 구현: rowToFont, rowToCollection**
  
  Create `apps/web/lib/db/mappers.ts`:
  ```typescript
  import type { Font, Collection } from '@/types/font';
  import type { FontRow, CollectionRow, CollectionItemRow } from './types';
  
  export function rowToFont(row: FontRow, aliases: string[]): Font {
    return {
      slug: row.slug,
      nameKo: row.name_ko ?? row.name_en,
      nameEn: row.name_en,
      fontKey: null, // 실 DB에 fontKey 컬럼 없음
      tier: row.is_commercial_free ? 'free' : 'paid',
      category: row.category_ko as any, // Category 타입
      foundry: row.foundry ?? '',
      availableWeights: row.weights.length > 0 ? row.weights : [400],
      moves: 0, // 슬라이스3에서 clicks 집계로 대체
      license: {
        commercial: row.is_commercial_free ? 'yes' : 'no',
        verifiedAt: row.last_modified ?? '', // ⚠️ 임시, 후속 verified_at 스키마 추가
        type: row.license_type ?? '',
        webfont: 'included', // Tier A(OFL/Apache-2.0/UFL) 웹폰트 임베딩 허용
        redistribution: 'yes', // 동 라이선스 재배포 허용
      },
      officialUrl: row.official_url,
      aliases,
      freeAlternatives: undefined, // 슬라이스3 구글폰트 병합 시 추가
      priceFrom: undefined,
    };
  }
  
  export function rowToCollection(
    row: CollectionRow,
    items: CollectionFontItemData[]
  ): Collection {
    return {
      slug: row.slug,
      title: row.title,
      intro: row.intro,
      items,
    };
  }
  ```

- [ ] **테스트: mappers 변환 로직 (RED → GREEN)**
  
  Create `apps/web/__tests__/mappers.test.ts`:
  ```typescript
  import { describe, it, expect } from 'vitest';
  import { rowToFont } from '@/lib/db/mappers';
  import type { FontRow } from '@/lib/db/types';
  
  const mockFontRow: FontRow = {
    id: '1',
    slug: 'pretendard',
    name_en: 'Pretendard',
    name_ko: '프리텐다드',
    foundry: 'Orioncactus',
    source_tier: 'A',
    category_ko: '고딕',
    category_google: 'Sans Serif',
    subsets: ['latin'],
    variants: ['normal'],
    weights: [400, 500, 700],
    is_commercial_free: true,
    license_type: 'SIL OFL',
    license_verified: true,
    official_url: 'https://github.com/orioncactus/pretendard',
    status: 'published',
    version: '1.3.9',
    last_modified: '2026-07-12T00:00:00Z',
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-12T00:00:00Z',
  };
  
  describe('rowToFont', () => {
    it('should map free font tier correctly', () => {
      const result = rowToFont(mockFontRow, ['프리텐다드']);
      expect(result.tier).toBe('free');
      expect(result.fontKey).toBeNull();
    });
  
    it('should use name_en as fallback for name_ko', () => {
      const rowWithoutKo = { ...mockFontRow, name_ko: null };
      const result = rowToFont(rowWithoutKo, []);
      expect(result.nameKo).toBe('Pretendard');
    });
  
    it('should default weights to [400] if empty', () => {
      const rowWithoutWeights = { ...mockFontRow, weights: [] };
      const result = rowToFont(rowWithoutWeights, []);
      expect(result.availableWeights).toEqual([400]);
    });
  
    it('should map paid font tier correctly', () => {
      const rowPaid = { ...mockFontRow, is_commercial_free: false };
      const result = rowToFont(rowPaid, []);
      expect(result.tier).toBe('paid');
      expect(result.license.commercial).toBe('no');
    });
  });
  ```

- [ ] **테스트 실행**
  ```bash
  cd apps/web && pnpm test __tests__/mappers.test.ts
  ```
  확인: 모든 케이스 GREEN

- [ ] **타입 체크**
  ```bash
  cd apps/web && pnpm tsc --noEmit
  ```

- [ ] **커밋**
  ```bash
  git add apps/web/types/font.ts apps/web/lib/db/types.ts apps/web/lib/db/mappers.ts apps/web/__tests__/mappers.test.ts
  git commit -m "feat: 타입 정의 및 매퍼 (fontKey nullable, DB row → Domain)"
  ```

---

## Task 3 — lib/db/fonts.ts (async 쿼리 + 테스트)

**목표**: Supabase에서 폰트 조회, aliases 조인.

### Files
- **Create**: `apps/web/lib/db/fonts.ts`
- **Create**: `apps/web/__tests__/lib-db-fonts.test.ts` (선택, 모킹 기반)

### Interfaces

**Consumes**:
- supabaseClient (client.ts)
- rowToFont (mappers.ts)

**Produces**:
- async getAllFonts(): Promise<Font[]>
- async getFontBySlug(slug: string): Promise<Font | null>
- async getAllSlugs(): Promise<string[]>
- async resolveFreeAlternatives(font: Font): Promise<Font[]>

### Steps

- [ ] **lib/db/fonts.ts 구현**
  
  Create `apps/web/lib/db/fonts.ts`:
  ```typescript
  import { supabaseClient } from './client';
  import type { FontRow, AliasRow } from './types';
  import { rowToFont } from './mappers';
  import type { Font } from '@/types/font';
  
  async function getFontAliases(fontId: string): Promise<string[]> {
    const { data, error } = await supabaseClient
      .from('aliases')
      .select('alias')
      .eq('font_id', fontId);
    
    if (error) throw error;
    return data?.map((row: AliasRow) => row.alias) ?? [];
  }
  
  export async function getAllFonts(): Promise<Font[]> {
    const { data, error } = await supabaseClient
      .from('fonts')
      .select('*')
      .eq('status', 'published')
      .order('created_at', { ascending: false });
    
    if (error) throw error;
    
    const fonts: Font[] = [];
    for (const row of data as FontRow[]) {
      const aliases = await getFontAliases(row.id);
      fonts.push(rowToFont(row, aliases));
    }
    return fonts;
  }
  
  export async function getFontBySlug(slug: string): Promise<Font | null> {
    const { data, error } = await supabaseClient
      .from('fonts')
      .select('*')
      .eq('slug', slug)
      .eq('status', 'published')
      .single();
    
    if (error) {
      if (error.code === 'PGRST116') return null; // not found
      throw error;
    }
    
    if (!data) return null;
    
    const aliases = await getFontAliases(data.id);
    return rowToFont(data as FontRow, aliases);
  }
  
  export async function getAllSlugs(): Promise<string[]> {
    const { data, error } = await supabaseClient
      .from('fonts')
      .select('slug')
      .eq('status', 'published');
    
    if (error) throw error;
    return data?.map((row) => row.slug) ?? [];
  }
  
  export async function resolveFreeAlternatives(font: Font): Promise<Font[]> {
    // 슬라이스1: 실 DB에 대안 테이블 없음 → 빈 배열
    // 슬라이스3에서 구글폰트 매칭 추가
    return [];
  }
  ```

- [ ] **모킹 테스트 (선택)**
  
  Create `apps/web/__tests__/lib-db-fonts.test.ts`:
  ```typescript
  import { describe, it, expect, vi, beforeEach } from 'vitest';
  import { getAllFonts, getFontBySlug, getAllSlugs } from '@/lib/db/fonts';
  import * as client from '@/lib/db/client';
  import type { FontRow } from '@/lib/db/types';
  
  const mockFontRow: FontRow = {
    id: '1',
    slug: 'pretendard',
    name_en: 'Pretendard',
    name_ko: '프리텐다드',
    foundry: 'Orioncactus',
    source_tier: 'A',
    category_ko: '고딕',
    category_google: null,
    subsets: ['latin'],
    variants: ['normal'],
    weights: [400, 500, 700],
    is_commercial_free: true,
    license_type: 'SIL OFL',
    license_verified: true,
    official_url: 'https://github.com/orioncactus/pretendard',
    status: 'published',
    version: '1.3.9',
    last_modified: '2026-07-12T00:00:00Z',
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-12T00:00:00Z',
  };
  
  describe('fonts.ts (mocked client)', () => {
    beforeEach(() => {
      vi.clearAllMocks();
    });
  
    it('getAllFonts should return Font[] with aliases', async () => {
      const mockSelect = vi.fn().mockReturnThis();
      const mockEq = vi.fn().mockReturnThis();
      const mockOrder = vi.fn().mockResolvedValue({
        data: [mockFontRow],
        error: null,
      });
      
      vi.spyOn(client.supabaseClient, 'from').mockReturnValue({
        select: mockSelect,
      } as any);
      mockSelect.mockReturnThis();
      mockEq.mockReturnThis();
      mockOrder.mockResolvedValue({ data: [mockFontRow], error: null });
      
      // Note: full mock is complex; integration test preferred
    });
  });
  ```
  
  (모킹의 복잡성으로 인해 통합 테스트(실 DB 스모크)로 대체 권장)

- [ ] **타입 검증**
  ```bash
  cd apps/web && pnpm tsc --noEmit
  ```

- [ ] **커밋**
  ```bash
  git add apps/web/lib/db/fonts.ts
  git commit -m "feat: 폰트 조회 async (Supabase + aliases 조인)"
  ```

---

## Task 4 — lib/db/collections.ts (async 쿼리 + 테스트)

**목표**: Supabase에서 컬렉션/아이템 조회.

### Files
- **Create**: `apps/web/lib/db/collections.ts`

### Interfaces

**Consumes**:
- supabaseClient (client.ts)
- rowToCollection (mappers.ts)

**Produces**:
- async getAllCollectionSlugs(): Promise<string[]>
- async getCollectionBySlug(slug: string): Promise<Collection | null>

### Steps

- [ ] **lib/db/collections.ts 구현 (published 폰트 조인)**
  
  Create `apps/web/lib/db/collections.ts`:
  ```typescript
  import { supabaseClient } from './client';
  import type { CollectionRow, CollectionItemRow, FontRow, CollectionFontItemData } from './types';
  import { rowToCollection } from './mappers';
  import { rowToFont } from './mappers';
  import type { Collection } from '@/types/font';
  
  export async function getAllCollectionSlugs(): Promise<string[]> {
    const { data, error } = await supabaseClient
      .from('collections')
      .select('slug')
      .eq('status', 'published');
    
    if (error) throw error;
    return data?.map((row) => row.slug) ?? [];
  }
  
  export async function getCollectionBySlug(slug: string): Promise<Collection | null> {
    const { data: collectionData, error: collectionError } = await supabaseClient
      .from('collections')
      .select('*')
      .eq('slug', slug)
      .eq('status', 'published')
      .single();
    
    if (collectionError) {
      if (collectionError.code === 'PGRST116') return null;
      throw collectionError;
    }
    
    if (!collectionData) return null;
    
    // collection_items 조회
    const { data: itemsData, error: itemsError } = await supabaseClient
      .from('collection_items')
      .select('*')
      .eq('collection_id', collectionData.id)
      .order('sort_order', { ascending: true });
    
    if (itemsError) throw itemsError;
    
    if (!itemsData || itemsData.length === 0) {
      return rowToCollection(collectionData as CollectionRow, []);
    }
    
    // collection_items의 font_id 목록
    const fontIds = (itemsData as CollectionItemRow[]).map((it) => it.font_id);
    
    // published 폰트만 조회 (collection_items의 font_id와 일치)
    const { data: fontsData, error: fontsError } = await supabaseClient
      .from('fonts')
      .select('*')
      .in('id', fontIds)
      .eq('status', 'published');
    
    if (fontsError) throw fontsError;
    
    const fontMap = new Map<string, FontRow>();
    for (const font of (fontsData ?? []) as FontRow[]) {
      fontMap.set(font.id, font);
    }
    
    // collection_items를 순서대로 매핑, published 폰트만 포함
    const collectionItems: CollectionFontItemData[] = [];
    for (const item of itemsData as CollectionItemRow[]) {
      const font = fontMap.get(item.font_id);
      if (!font) continue; // published 폰트 아니면 스킵
      
      // aliases 조회 (사용하지 않음, rowToFont는 aliases 필요하므로 빈 배열)
      collectionItems.push({
        slug: font.slug,
        nameKo: font.name_ko ?? font.name_en,
        fontKey: null, // 실 DB에 fontKey 없음
        tier: font.is_commercial_free ? 'free' : 'paid',
        comment: item.comment ?? '',
      });
    }
    
    return rowToCollection(collectionData as CollectionRow, collectionItems);
  }
  ```

- [ ] **타입 검증**
  ```bash
  cd apps/web && pnpm tsc --noEmit
  ```

- [ ] **커밋**
  ```bash
  git add apps/web/lib/db/collections.ts
  git commit -m "feat: 컬렉션 조회 async (Supabase)"
  ```

---

## Task 5 — lib/data.ts 파사드 교체 (async 위임)

**목표**: 기존 동기 함수를 async로 전환, 목업 검증(checkIntegrity) 제거.

### Files
- **Modify**: `apps/web/lib/data.ts`

### Interfaces

**Consumes**:
- lib/db/fonts.ts (getAllFonts, getFontBySlug, getAllSlugs, resolveFreeAlternatives)
- lib/db/collections.ts (getCollectionBySlug, getAllCollectionSlugs)

**Produces**:
- export async getFontBySlug(slug: string): Promise<Font | null>
- export async getAllSlugs(): Promise<string[]>
- export async resolveFreeAlternatives(font: Font): Promise<Font[]>
- export async getCollectionBySlug(slug: string): Promise<Collection | null>
- export async getAllCollectionSlugs(): Promise<string[]>
- export FONT_KEYS (유지) // 타입 검증용, 값 변경 없음

### Steps

- [ ] **lib/data.ts 재작성: async 위임**
  
  Replace entire `apps/web/lib/data.ts`:
  ```typescript
  import type { Collection, Font, FontKey } from "@/types/font";
  import * as fonts from "./db/fonts";
  import * as collections from "./db/collections";
  
  export const FONT_KEYS: FontKey[] = [
    "pretendard",
    "blackHanSans",
    "jua",
    "doHyeon",
    "gowunBatang",
    "nanumMyeongjo",
    "kirangHaerang",
    "gaegu",
    "songMyung",
  ];
  
  export async function getFontBySlug(slug: string): Promise<Font | null> {
    return fonts.getFontBySlug(slug);
  }
  
  export async function getAllSlugs(): Promise<string[]> {
    return fonts.getAllSlugs();
  }
  
  export async function resolveFreeAlternatives(font: Font): Promise<Font[]> {
    return fonts.resolveFreeAlternatives(font);
  }
  
  export async function getCollectionBySlug(slug: string): Promise<Collection | null> {
    return collections.getCollectionBySlug(slug);
  }
  
  export async function getAllCollectionSlugs(): Promise<string[]> {
    return collections.getAllCollectionSlugs();
  }
  ```
  
  (checkIntegrity, assertDataIntegrity, fonts/collections import 제거)

- [ ] **타입 검증**
  ```bash
  cd apps/web && pnpm tsc --noEmit
  ```

- [ ] **커밋**
  ```bash
  git add apps/web/lib/data.ts
  git commit -m "refactor: lib/data.ts async 파사드 (lib/db 위임)"
  ```

---

## Task 6 — lib/fonts.ts 폴백 헬퍼 + 컴포넌트 교체

**목표**: fontKey null 대응, 시스템폰트 폴백 구현.

### Files
- **Modify**: `apps/web/lib/fonts.ts`
- **Modify**: `apps/web/components/FontCard.tsx`
- **Modify**: `apps/web/components/AlternativesCard.tsx`
- **Modify**: `apps/web/components/TrendRankRow.tsx`
- **Modify**: `apps/web/app/fonts/[slug]/page.tsx`
- **Modify**: `apps/web/app/collections/[slug]/page.tsx`

### Interfaces

**Consumes**:
- Font.fontKey (nullable)
- fontKeyToVar (기존 매핑)

**Produces**:
- export function familyOf(fontKey: FontKey | null): string

### Steps

- [ ] **lib/fonts.ts에 familyOf 추가**
  
  Add to end of `apps/web/lib/fonts.ts` (before last line 92):
  ```typescript
  export function familyOf(fontKey: FontKey | null): string {
    if (fontKey === null) {
      return '"Pretendard Variable", "Pretendard", sans-serif';
    }
    return fontKeyToVar[fontKey];
  }
  ```

- [ ] **FontCard.tsx: fontKey 폴백**
  
  Change line 11 in `apps/web/components/FontCard.tsx` from:
  ```typescript
  <div className={styles.specimen} style={{ fontFamily: fontKeyToVar[font.fontKey] }}>
  ```
  to:
  ```typescript
  <div className={styles.specimen} style={{ fontFamily: familyOf(font.fontKey) }}>
  ```
  
  Add import:
  ```typescript
  import { familyOf } from "@/lib/fonts";
  ```

- [ ] **AlternativesCard.tsx: fontKey 폴백**
  
  Change line 16 in `apps/web/components/AlternativesCard.tsx` from:
  ```typescript
  style={{ fontFamily: fontKeyToVar[f.fontKey] }}
  ```
  to:
  ```typescript
  style={{ fontFamily: familyOf(f.fontKey) }}
  ```
  
  Add import:
  ```typescript
  import { familyOf } from "@/lib/fonts";
  ```

- [ ] **TrendRankRow.tsx: fontKey 폴백**
  
  In `apps/web/components/TrendRankRow.tsx`, find specimen render and change from:
  ```typescript
  style={{ fontFamily: fontKeyToVar[item.font.fontKey] }}
  ```
  to:
  ```typescript
  style={{ fontFamily: familyOf(item.font.fontKey) }}
  ```
  
  Add import:
  ```typescript
  import { familyOf } from "@/lib/fonts";
  ```

- [ ] **fonts/[slug]/page.tsx: family 폴백**
  
  Change line 22 in `apps/web/app/fonts/[slug]/page.tsx` from:
  ```typescript
  const family = fontKeyToVar[font.fontKey];
  ```
  to:
  ```typescript
  const family = familyOf(font.fontKey);
  ```
  
  Add import:
  ```typescript
  import { familyOf } from "@/lib/fonts";
  ```

- [ ] **collections/[slug]/page.tsx: fontKey 폴백**
  
  Change line 33 in `apps/web/app/collections/[slug]/page.tsx` from:
  ```typescript
  style={{ fontFamily: fontKeyToVar[f.fontKey] }}
  ```
  to:
  ```typescript
  style={{ fontFamily: familyOf(f.fontKey) }}
  ```
  
  Add import:
  ```typescript
  import { familyOf } from "@/lib/fonts";
  ```

- [ ] **타입 검증**
  ```bash
  cd apps/web && pnpm tsc --noEmit
  ```

- [ ] **커밋**
  ```bash
  git add apps/web/lib/fonts.ts apps/web/components/FontCard.tsx apps/web/components/AlternativesCard.tsx apps/web/components/TrendRankRow.tsx apps/web/app/fonts/[slug]/page.tsx apps/web/app/collections/[slug]/page.tsx
  git commit -m "feat: fontKey null 폴백 (시스템폰트)"
  ```

---

## Task 7 — 서버 페이지 async 전환

**목표**: 페이지 함수, generateStaticParams를 async로 전환, 실데이터 연동.

### Files
- **Modify**: `apps/web/app/fonts/page.tsx`
- **Modify**: `apps/web/app/fonts/[slug]/page.tsx`
- **Modify**: `apps/web/app/collections/page.tsx`
- **Modify**: `apps/web/app/collections/[slug]/page.tsx`

### Interfaces

**Consumes**:
- lib/data.ts async (getAllFonts, getFontBySlug, getAllSlugs, getCollectionBySlug, getAllCollectionSlugs, resolveFreeAlternatives)

**Produces**:
- async page functions
- async generateStaticParams

### Steps

- [ ] **fonts/page.tsx: async 전환**
  
  Replace entire `apps/web/app/fonts/page.tsx`:
  ```typescript
  import { getAllFonts } from "@/lib/data";
  import { FontFilters } from "@/components/FontFilters";
  import { FontGrid } from "@/components/FontGrid";
  import styles from "./page.module.css";
  
  export default async function FontsPage() {
    const fonts = await getAllFonts();
    
    return (
      <main className={styles.main}>
        <FontFilters />
        <div className={styles.body}>
          <div className={styles.toolbar}>
            <span className={styles.count}>폰트 {fonts.length}종</span>
            <div className={styles.sorts}>
              <button type="button" className={`${styles.sort} ${styles.active}`}>인기순</button>
              <button type="button" className={styles.sort}>최신순</button>
            </div>
          </div>
          <FontGrid fonts={fonts} />
        </div>
      </main>
    );
  }
  ```

- [ ] **fonts/[slug]/page.tsx: async + generateStaticParams 전환**
  
  Replace entire `apps/web/app/fonts/[slug]/page.tsx`:
  ```typescript
  import { notFound } from "next/navigation";
  import { getFontBySlug, getAllSlugs, resolveFreeAlternatives } from "@/lib/data";
  import { familyOf } from "@/lib/fonts";
  import { Breadcrumb } from "@/components/Breadcrumb";
  import { SpecimenBox } from "@/components/SpecimenBox";
  import { LicenseSummaryCard } from "@/components/LicenseSummaryCard";
  import { AlternativesCard } from "@/components/AlternativesCard";
  import { TierChip } from "@/components/TierChip";
  import styles from "./page.module.css";
  
  export const dynamicParams = false;
  
  export async function generateStaticParams() {
    const slugs = await getAllSlugs();
    return slugs.map((slug) => ({ slug }));
  }
  
  export default async function FontDetail({ params }: { params: Promise<{ slug: string }> }) {
    const { slug } = await params;
    const font = await getFontBySlug(slug);
    if (!font) notFound();
  
    const family = familyOf(font.fontKey);
    const isPaid = font.tier === "paid";
    const alternatives = isPaid ? await resolveFreeAlternatives(font) : [];
    const caption = isPaid
      ? "견본은 유사 서체로 대체 표시 — 실제 서체는 공식 페이지에서 확인하세요."
      : undefined;
  
    return (
      <main className={styles.wrap}>
        <Breadcrumb
          items={[
            { label: "폰트", href: "/fonts" },
            { label: font.category, href: `/fonts?category=${encodeURIComponent(font.category)}` },
            { label: font.nameKo },
          ]}
        />
        <div className={styles.grid}>
          <div className={styles.main}>
            <div className={styles.titleRow}>
              <h1 className={styles.title}>{font.nameKo}</h1>
              <TierChip tier={font.tier} />
            </div>
            <p className={styles.meta}>
              {font.foundry} {String.fromCharCode(183)} {font.availableWeights.length}가지 굵기 {String.fromCharCode(183)} 이동 {font.moves.toLocaleString()}회
            </p>
            <SpecimenBox fontFamily={family} editable={!isPaid} caption={caption} />
          </div>
          <div className={styles.side}>
            <LicenseSummaryCard font={font} />
            <AlternativesCard category={font.category} items={alternatives} />
          </div>
        </div>
      </main>
    );
  }
  ```

- [ ] **collections/page.tsx: async 전환**
  
  Replace entire `apps/web/app/collections/page.tsx`:
  ```typescript
  import { getAllCollectionSlugs, getCollectionBySlug } from "@/lib/data";
  import { CollectionCard } from "@/components/CollectionCard";
  import { EmptyState } from "@/components/EmptyState";
  import styles from "./page.module.css";
  
  export const metadata = { title: "컬렉션 - FontAgit" };
  
  export default async function CollectionsPage() {
    const slugs = await getAllCollectionSlugs();
    const collections = await Promise.all(
      slugs.map((slug) => getCollectionBySlug(slug))
    );
    const validCollections = collections.filter((c): c is NonNullable<typeof c> => c !== null);
    
    return (
      <main className={styles.main}>
        <h1 className={styles.h1}>컬렉션</h1>
        <p className={styles.lead}>테마별로 묶은 폰트 모음이에요.</p>
        {validCollections.length === 0 ? (
          <EmptyState
            title="아직 컬렉션이 없어요"
            description="곧 테마별 폰트 모음을 준비할게요. 먼저 폰트를 둘러보시겠어요?"
            actionHref="/fonts"
            actionLabel="폰트 둘러보기"
          />
        ) : (
          <div className={styles.grid}>
            {validCollections.map((c) => (
              <CollectionCard key={c.slug} collection={c} />
            ))}
          </div>
        )}
      </main>
    );
  }
  ```

- [ ] **collections/[slug]/page.tsx: async + generateStaticParams + Collection 폰트 정보 직접 사용**
  
  Replace entire `apps/web/app/collections/[slug]/page.tsx`:
  ```typescript
  import Link from "next/link";
  import { notFound } from "next/navigation";
  import { getCollectionBySlug, getAllCollectionSlugs } from "@/lib/data";
  import { familyOf } from "@/lib/fonts";
  import { TierChip } from "@/components/TierChip";
  import styles from "./page.module.css";
  
  export const dynamicParams = false;
  
  export async function generateStaticParams() {
    const slugs = await getAllCollectionSlugs();
    return slugs.map((slug) => ({ slug }));
  }
  
  export default async function CollectionDetail({ params }: { params: Promise<{ slug: string }> }) {
    const { slug } = await params;
    const collection = await getCollectionBySlug(slug);
  
    if (!collection) {
      notFound();
    }
  
    return (
      <main className={styles.main}>
        <div className={styles.kicker}>컬렉션 - {collection.items.length}종</div>
        <h1 className={styles.title}>{collection.title}</h1>
        <p className={styles.intro}>{collection.intro}</p>
        <div className={styles.list}>
          {collection.items.map((it) => {
            const f = getFontBySlug(it.fontSlug)!; // ⚠️ 동기 호출 후보, 아래 async 전환 필수
            return (
              <div key={it.fontSlug} className={styles.item}>
                <div className={styles.itemHead}>
                  <Link href={`/fonts/${f.slug}`} className={styles.itemName} style={{ fontFamily: familyOf(f.fontKey) }}>{f.nameKo}</Link>
                  <TierChip tier={f.tier} />
                </div>
                <p className={styles.comment}>{it.comment}</p>
              </div>
            );
          })}
        </div>
      </main>
    );
  }
  ```
  
 
  ```typescript
  export default async function CollectionDetail({ params }: { params: Promise<{ slug: string }> }) {
    const { slug } = await params;
    const collection = await getCollectionBySlug(slug);
  
    if (!collection) {
      notFound();
    }
    
  
    return (
      <main className={styles.main}>
        <div className={styles.kicker}>컬렉션 - {collection.items.length}종</div>
        <h1 className={styles.title}>{collection.title}</h1>
        <p className={styles.intro}>{collection.intro}</p>
        <div className={styles.list}>
          {collection.items.map((it) => (
            <div key={it.slug} className={styles.item}>
              <div className={styles.itemHead}>
                <Link href={`/fonts/${it.slug}`} className={styles.itemName} style={{ fontFamily: familyOf(it.fontKey) }}>{it.nameKo}</Link>
                <TierChip tier={it.tier} />
              </div>
              <p className={styles.comment}>{it.comment}</p>
            </div>
          ))}
        </div>
      </main>
    );
  }
  ```

- [ ] **타입 검증**
  ```bash
  cd apps/web && pnpm tsc --noEmit
  ```

- [ ] **커밋**
  ```bash
  git add apps/web/app/fonts/page.tsx apps/web/app/fonts/\[slug\]/page.tsx apps/web/app/collections/page.tsx apps/web/app/collections/\[slug\]/page.tsx
  git commit -m "feat: 페이지 async 전환 (실데이터 연동)"
  ```

---

## Task 8 — 홈/트렌드 임시 실데이터 (슬라이스3 전 폴백)

**목표**: 트렌드 페이지를 실데이터로, "최신 등록" 임시 랭킹 표시.

### Files
- **Modify**: `apps/web/app/page.tsx`
- **Modify**: `apps/web/app/trends/page.tsx`
- **Modify** (선택): `apps/web/data/trends.ts` (주석/문서만, 코드 유지)

### Interfaces

**Consumes**:
- lib/data.ts (getAllFonts)

**Produces**:
- 홈: 최신 폰트 Top 10 (임시)
- 트렌드: 동일 임시 랭킹

### Steps

- [ ] **lib/data.ts에 임시 트렌드 헬퍼 추가**
  
  Add to `apps/web/lib/data.ts`:
  ```typescript
  export async function getTemporaryTrends(): Promise<TrendItem[]> {
    const allFonts = await getAllFonts();
    // 슬라이스3까지 moves 미수집, 기본값 0 + change="new"
    return allFonts.slice(0, 10).map((f, idx) => ({
      rank: idx + 1,
      change: 'new' as const,
      font: {
        slug: f.slug,
        nameKo: f.nameKo,
        fontKey: f.fontKey,
        tier: f.tier,
      },
      moves: 0,
    }));
  }
  ```
  
  (import TrendItem 필요)

- [ ] **app/page.tsx: 임시 트렌드**
  
  Replace entire `apps/web/app/page.tsx`:
  ```typescript
  import { getTemporaryTrends } from "@/lib/data";
  import { Hero } from "@/components/Hero";
  import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
  import { AdSlot } from "@/components/AdSlot";
  import styles from "./page.module.css";
  
  export default async function Home() {
    const weeklyTrends = await getTemporaryTrends();
    
    return (
      <main className={styles.main}>
        <div className={styles.grid}>
          <Hero />
          <WeeklyRankPanel items={weeklyTrends} />
        </div>
        <section className={styles.adSection}>
          <div className={styles.container}>
            <AdSlot />
          </div>
        </section>
      </main>
    );
  }
  ```

- [ ] **app/trends/page.tsx: 임시 트렌드**
  
  Replace entire `apps/web/app/trends/page.tsx`:
  ```typescript
  import { getTemporaryTrends } from "@/lib/data";
  import { FilterChip } from "@/components/FilterChip";
  import { TrendRankRow } from "@/components/TrendRankRow";
  import styles from "./page.module.css";
  
  export default async function TrendsPage() {
    const weeklyTrends = await getTemporaryTrends();
    
    return (
      <main className={styles.main}>
        <div className={styles.head}>
          <h1 className={styles.h1}>이번 주 인기 폰트</h1>
          <p className={styles.lead}>최신 등록 기준입니다 (슬라이스3에서 클릭수 기반으로 전환).</p>
          <div className={styles.filters}>
            <FilterChip active>주간</FilterChip>
            <FilterChip>월간</FilterChip>
          </div>
        </div>
        <ul className={styles.list}>
          {weeklyTrends.map((item) => (
            <li key={item.rank}>
              <TrendRankRow item={item} />
            </li>
          ))}
        </ul>
      </main>
    );
  }
  ```

- [ ] **data/trends.ts 주석 추가 (코드 유지)**
  
  Add comment at top of `apps/web/data/trends.ts`:
  ```typescript
  /**
   * ⚠️ 슬라이스1: 목업 유지 (실데이터 사용 안 함)
   * 슬라이스3에서 실 클릭집계(clicks RPC) 도입 후 제거 예정
   */
  ```

- [ ] **타입 검증**
  ```bash
  cd apps/web && pnpm tsc --noEmit
  ```

- [ ] **커밋**
  ```bash
  git add apps/web/lib/data.ts apps/web/app/page.tsx apps/web/app/trends/page.tsx
  git commit -m "feat: 홈/트렌드 임시 실데이터 (최신 등록 기준, 슬라이스3 전 폴백)"
  ```

---

## Task 9 — SEO (F-09)

**목표**: generateMetadata, sitemap.ts 생성.

### Files
- **Create**: `apps/web/app/sitemap.ts`
- **Modify**: `apps/web/app/fonts/[slug]/page.tsx` (metadata 추가)

### Interfaces

**Consumes**:
- lib/data.ts (getAllSlugs, getAllCollectionSlugs)

**Produces**:
- async generateMetadata(params)
- sitemap.ts with fonts + collections URLs

### Steps

- [ ] **sitemap.ts 생성**
  
  Create `apps/web/app/sitemap.ts`:
  ```typescript
  import { MetadataRoute } from 'next';
  import { getAllSlugs, getAllCollectionSlugs } from '@/lib/data';
  
  const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'https://fontagit.example.com';
  
  export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
    const fontSlugs = await getAllSlugs();
    const collectionSlugs = await getAllCollectionSlugs();
    
    const fontEntries = fontSlugs.map((slug) => ({
      url: `${BASE_URL}/fonts/${slug}/`,
      lastModified: new Date(),
      changeFrequency: 'weekly' as const,
      priority: 0.8,
    }));
    
    const collectionEntries = collectionSlugs.map((slug) => ({
      url: `${BASE_URL}/collections/${slug}/`,
      lastModified: new Date(),
      changeFrequency: 'weekly' as const,
      priority: 0.7,
    }));
    
    return [
      {
        url: `${BASE_URL}/`,
        lastModified: new Date(),
        changeFrequency: 'daily' as const,
        priority: 1.0,
      },
      {
        url: `${BASE_URL}/fonts/`,
        lastModified: new Date(),
        changeFrequency: 'daily' as const,
        priority: 0.9,
      },
      {
        url: `${BASE_URL}/collections/`,
        lastModified: new Date(),
        changeFrequency: 'weekly' as const,
        priority: 0.8,
      },
      {
        url: `${BASE_URL}/trends/`,
        lastModified: new Date(),
        changeFrequency: 'daily' as const,
        priority: 0.8,
      },
      ...fontEntries,
      ...collectionEntries,
    ];
  }
  ```

- [ ] **fonts/[slug]/page.tsx에 generateMetadata 추가**
  
  Add to `apps/web/app/fonts/[slug]/page.tsx` (before default export):
  ```typescript
  export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
    const { slug } = await params;
    const font = await getFontBySlug(slug);
    
    if (!font) {
      return {
        title: 'Not Found',
        description: '폰트를 찾을 수 없습니다.',
      };
    }
    
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://fontagit.example.com';
    
    return {
      title: `${font.nameKo} - FontAgit`,
      description: `${font.foundry} 제작, ${font.category}. ${font.tier === 'free' ? '무료' : '유료'}. ${font.availableWeights.length}가지 굵기.`,
      canonical: `${baseUrl}/fonts/${font.slug}/`,
      openGraph: {
        title: `${font.nameKo} - FontAgit`,
        description: `${font.foundry} 제작 서체`,
        url: `${baseUrl}/fonts/${font.slug}/`,
      },
    };
  }
  ```

- [ ] **타입 검증**
  ```bash
  cd apps/web && pnpm tsc --noEmit
  ```

- [ ] **커밋**
  ```bash
  git add apps/web/app/sitemap.ts apps/web/app/fonts/\[slug\]/page.tsx
  git commit -m "feat: SEO (generateMetadata + sitemap)"
  ```

---

## Task 10 — 기존 테스트 수정 + 전체 검증

**목표**: 기존 테스트 async/mock 수정, 빌드/테스트 성공.

### Files
- **Modify**: `apps/web/__tests__/app/fonts/page.test.tsx`
- **Modify**: `apps/web/__tests__/app/fonts/[slug]/page.test.tsx`
- **Modify**: `apps/web/__tests__/app/trends/page.test.tsx`
- **Modify**: `apps/web/__tests__/components/FontCard.test.tsx`
- **Modify** (선택): 기타 컴포넌트 테스트

### Interfaces

**Consumes**:
- 기존 테스트 (mockery 또는 fixture)

**Produces**:
- Green test suite
- Successful build (out/ with SSG)

### Steps

- [ ] **테스트 파일 목록 확인**
  ```bash
  find apps/web/__tests__ -name "*.test.ts*" -o -name "*.spec.ts*" | head -20
  ```

- [ ] **각 테스트 파일별 수정**
  
  예시 (FontCard.test.tsx):
  ```typescript
  // Before: import { fonts } from '@/data/fonts'
  // After: mock or fixture
  
  import { describe, it, expect } from 'vitest';
  import { render, screen } from '@testing-library/react';
  import { FontCard } from '@/components/FontCard';
  import type { Font } from '@/types/font';
  
  const mockFont: Font = {
    slug: 'pretendard',
    nameKo: '프리텐다드',
    nameEn: 'Pretendard',
    fontKey: null, // null 케이스 테스트
    tier: 'free',
    category: '고딕',
    foundry: 'Orioncactus',
    availableWeights: [400, 500, 700],
    moves: 100,
    license: { commercial: 'yes', verifiedAt: '2026-07-12', type: 'OFL', webfont: 'included', redistribution: 'yes' },
    officialUrl: 'https://github.com/orioncactus/pretendard',
    aliases: ['프리텐다드'],
  };
  
  describe('FontCard', () => {
    it('should render font name', () => {
      render(<FontCard font={mockFont} />);
      expect(screen.getByText('프리텐다드')).toBeInTheDocument();
    });
    
    it('should handle fontKey null (system font fallback)', () => {
      const fontWithoutKey = { ...mockFont, fontKey: null };
      const { container } = render(<FontCard font={fontWithoutKey} />);
      const specimen = container.querySelector('.specimen');
      expect(specimen).toHaveStyle('font-family: "Pretendard Variable", "Pretendard", sans-serif');
    });
  });
  ```

- [ ] **각 테스트 실행**
  ```bash
  cd apps/web && pnpm test __tests__/components/FontCard.test.tsx
  ```
  확인: GREEN

- [ ] **전체 테스트 실행**
  ```bash
  cd apps/web && pnpm test
  ```
  확인: 모든 테스트 GREEN (실패 시 고쳐서 재커밋)

- [ ] **빌드 검증**
  ```bash
  cd apps/web && pnpm build
  ```
  확인: 성공, `out/` 디렉토리 생성, HTML 파일 확인

- [ ] **생성된 정적 사이트 구조 확인**
  ```bash
  ls -la apps/web/out/ | head -20
  ls -la apps/web/out/fonts/ | head -20
  ls -la apps/web/out/collections/ | head -20
  ```
  확인: fonts/*, collections/* 하위 폴더 + index.html, trailingSlash 반영

- [ ] **lint 검증** (선택)
  ```bash
  cd apps/web && pnpm lint
  ```
  확인: 경고/에러 없음 (권장)

- [ ] **최종 커밋**
  ```bash
  git add apps/web/__tests__/
  git commit -m "test: 기존 테스트 async/mock 수정"
  ```

---

## Self-Review

### 스펙 커버리지 검증

| 스펙 항목 | Task | 상태 |
|-----------|------|------|
| F-01 (웹 데이터 통합) | 1~7 | ✅ |
| F-06 (견본 폴백) | 6 | ✅ |
| F-09 (SEO) | 9 | ✅ |
| lib/db 계층 | 1~4 | ✅ |
| async 페이지 | 7 | ✅ |
| fontKey null | 2, 6 | ✅ |
| 슬라이스1 범위 (읽기만) | 1~10 | ✅ |

### 플레이스홀더/TODO 스캔

- ⚠️ Task 2: `last_modified` → `verifiedAt` 임시 매핑 (후속 스키마 `verified_at` 추가 필요)
- ⚠️ Task 3: resolveFreeAlternatives 빈 배열 (슬라이스3에서 구글폰트 매칭 추가)
- ⚠️ Task 8: "최신 등록" 임시 랭킹 (슬라이스3 clicks RPC 도입 후 교체)
- ⚠️ Task 9: NEXT_PUBLIC_BASE_URL env 변수 필요 (기본값 예시 제공)

### 타입 일관성

- ✅ Font.fontKey: FontKey | null (모든 참조 nullable 처리)
- ✅ TrendItem.font: Pick 포함 fontKey nullable
- ✅ lib/db 타입: DB 스키마 정확 매핑
- ✅ async/await: 모든 Supabase 쿼리 async

### 빌드 검증 기준

```bash
pnpm test              # Vitest GREEN
pnpm build            # SSG export, out/ 생성
pnpm lint             # 권장 (에러 0)
```

### 스코프 확인

- ✅ 읽기만 (폰트, 컬렉션, aliases)
- ✅ 쓰기 제외 (클릭, 검색, 등록 → 슬라이스2~3)
- ✅ 비교/캔버스 제외 (→ 슬라이스3)
- ✅ 정적 내보내기 유지 (output:"export")

---

## Execution Handoff

**권장 방식: Subagent-driven (default-worker, Sonnet)**

이 계획은 Task 0~10 총 11개 독립 단위로 분해되었습니다.  
각 Task는:
- 명확한 파일 변경 범위 (3~8개 파일)
- TDD RED→GREEN (Task 2 단위테스트, Task 10 통합테스트)
- 독립 커밋 가능 (스쿼시 불가)
- 실행 순서 의존성 최소 (Task 0 게이트 후 순차, Task 1~4는 병렬 가능)

**실행 모드**:
- **default-worker**: Task 1~10 구현 + 테스트 + 빌드 검증 + 로그 첨부
- **deep-reasoner** (선택): 고부담 결정점만 병렬 판단

**검증 체크**:
- 각 Task 커밋 후: `pnpm tsc --noEmit` + 해당 테스트 GREEN
- Task 10 완료 후: `pnpm build && pnpm test`로 전체 성공 확인
- 최종: `git log --oneline --graph` 커밋 히스토리 11개 확인

**스코프 드리프트 차단**:
- data/fonts.ts, data/trends.ts, data/collections.ts 유지 (제거는 슬라이스3)
- CompareBoard, PlaygroundCanvas 코드 건드리지 않음
- output:"export" 변경 금지

---

**작성일**: 2026-07-15  
**버전**: 1.0 (슬라이스1 확정)  
**다음**: 슬라이스2(검색), 슬라이스3(트렌드+비교) 계획 차례
