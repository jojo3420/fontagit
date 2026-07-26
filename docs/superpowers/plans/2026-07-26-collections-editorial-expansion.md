# 컬렉션 에디토리얼 10종 확장 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 운영 컬렉션을 수동 큐레이션 10종으로 늘리고, 각 컬렉션에 발행 폰트를 5종 이상 안전하게 연결한다.

**Architecture:** 스키마와 웹 코드는 바꾸지 않는다. 신규 SQL 마이그레이션 하나가 대상 폰트와 기존 컬렉션을 먼저 검증한 뒤, 한 트랜잭션 안에서 신규 컬렉션 7종을 추가하고 대상 10종의 연결만 확정 목록으로 교체한다. dev DB와 정적 웹 빌드에서 검증한 뒤 PR과 GitHub 이슈를 갱신한다.

**Tech Stack:** PostgreSQL 17 / Supabase SQL / Next.js 16 정적 생성 / pnpm / GitHub Issues

## 작업 경계

- 기준 브랜치: `origin/develop`의 `444a8d7`
- 작업 브랜치: `feature/collections-editorial-expansion`
- 대표 이슈: `#56 컬렉션 10개 시드 + 내부 링크 허브 고도화`
- 최상위 로드맵: `#62 fontagit 전체 이슈 트래킹`
- `#107`은 폰트 상세 굵기·이탤릭 개선이다. 이번 작업과 무관하므로 수정하지 않는다.
- 이번 단계는 #56의 **데이터 시드**만 처리한다. 내부 링크 화면 개선은 데이터 시드 완료 후 별도 설계한다.
- #104의 Tier B 1,110종 metadata 전체 처리는 이번 단계 뒤에 별도 계획으로 진행한다.
- 운영 DB 적용, PR 병합, 배포는 각각 별도 상태로 기록한다. 하나를 했다고 나머지도 끝났다고 표시하지 않는다.
- 단순 시드·조회 UI용 단위 테스트는 만들지 않는다. SQL 불변식과 정적 빌드만 검증한다.

## 확인된 기준값

- 운영 발행 폰트: 1,240종
- 운영 발행 컬렉션: 3종
- 선택한 고유 폰트: 40종
- 선택한 40종은 모두 `published`, `license_verified=true`, `license_type='OFL'`
- 기존 3종은 제목과 소개를 유지한다.
- 기존 `origin/develop`에는 두 가지 선행 문제가 있다.
  - `pnpm install --frozen-lockfile`: `pnpm-lock.yaml`과 `apps/web/package.json` 불일치
  - 파이프라인 테스트: `6 failed, 271 passed, 4 skipped`
- 위 문제는 이번 컬렉션 변경이 만든 회귀가 아니다. 컬렉션 커밋에 lockfile이나 파이프라인 테스트 수정을 섞지 않는다.

---

### Task 1: 안전한 컬렉션 시드 마이그레이션 작성

**Files:**

- Create: `supabase/migrations/0020_expand_editorial_collections.sql`
- Reference: `supabase/migrations/0001_fontagit_schema.sql`
- Reference: `supabase/migrations/0003_seed_collections.sql`
- Reference: `docs/superpowers/specs/2026-07-26-collections-editorial-expansion-design.md`

- [ ] **Step 1: 트랜잭션과 임시 시드 테이블 작성**

마이그레이션 전체를 `begin; ... commit;`으로 감싼다. 임시 테이블은 실제 스키마에 남지 않아야 한다.

```sql
begin;

create temporary table _collection_defs (
  slug text primary key,
  title text not null,
  intro text not null,
  collection_sort int not null unique,
  preserve_existing_copy boolean not null
) on commit drop;

create temporary table _collection_seed (
  collection_slug text not null references _collection_defs(slug),
  font_slug text not null,
  comment text not null check (length(trim(comment)) > 0),
  item_sort int not null,
  primary key (collection_slug, font_slug),
  unique (collection_slug, item_sort)
) on commit drop;
```

중복 컬렉션 slug, 같은 컬렉션 안의 중복 폰트, 중복 정렬 번호가 있으면 임시 테이블 제약으로 즉시 실패해야 한다.

- [ ] **Step 2: 컬렉션 10종 정의 입력**

기존 3종은 `preserve_existing_copy=true`로 넣는다. 이 3종의 `title`, `intro` 값은 검사와 문서화를 위한 기준값이며 실제 DB 문구를 덮어쓰지 않는다.

| 순서 | slug | 제목 | 소개 | 기존 문구 유지 |
|---:|---|---|---|:---:|
| 0 | `dawn-serif` | 새벽 감성 명조 모음 | 긴 글에 어울리는, 획이 차분한 명조들을 모았어요. 에세이-브랜드 소개문-전자책 본문에 특히 잘 맞습니다. | 예 |
| 1 | `brand-gothic` | 브랜드 첫인상 고딕 | 로고와 헤드라인에서 또렷하게 읽히는 고딕을 모았어요. 포스터-배너-앱 UI에 두루 쓰기 좋습니다. | 예 |
| 2 | `playful-hand` | 손끝의 온기 손글씨 | 사람 손으로 쓴 듯한 따뜻함을 담은 서체 모음이에요. 카드-굿즈-SNS 문구에 잘 어울립니다. | 예 |
| 3 | `ui-korean-sans` | 화면에 또렷한 한글 고딕 | 작은 화면부터 큰 제목까지 폭넓게 쓸 수 있는 한글 고딕을 모았어요. 서비스 화면과 정보 전달용 문서에 활용하기 좋습니다. | 아니요 |
| 4 | `wide-weight-korean` | 굵기를 자유롭게 고르는 한글 폰트 | 여러 굵기를 지원해 한 가족 안에서 정보의 강약을 나누기 좋은 폰트예요. 제목과 본문을 같은 인상으로 맞출 때 유용합니다. | 아니요 |
| 5 | `korean-display` | 한눈에 꽂히는 한글 디스플레이 | 형태가 뚜렷해 짧은 문구에 힘을 주는 한글 폰트를 모았어요. 포스터와 배너의 큰 제목에 먼저 살펴보세요. | 아니요 |
| 6 | `latin-sans-essentials` | 영문 산세리프 기본 컬렉션 | 영문 제목과 본문에 두루 쓰기 쉬운 산세리프를 모았어요. 화면과 브랜드 문구의 기본 후보로 비교해 보세요. | 아니요 |
| 7 | `latin-serif-editorial` | 영문 에디토리얼 세리프 | 긴 글과 인용문에 차분한 인상을 주는 영문 세리프를 모았어요. 매거진과 소개 페이지의 제목·본문 조합을 살펴보세요. | 아니요 |
| 8 | `developer-monospace` | 코드와 숫자를 위한 모노스페이스 | 글자 폭이 일정한 모노스페이스를 모았어요. 코드 예시와 숫자가 많은 표에서 모양을 비교하기 좋습니다. | 아니요 |
| 9 | `verified-ofl-picks` | OFL 라이선스 확인 추천 | FontAgit에서 OFL 확인이 끝난 폰트 중 서로 다른 인상의 후보를 모았어요. 사용 전에는 상세 화면의 최신 라이선스 근거도 함께 확인하세요. | 아니요 |

- [ ] **Step 3: 폰트 연결 56개와 실제 한 줄 설명 입력**

아래 문구를 그대로 `_collection_seed`에 넣는다. 한 컬렉션 안의 `item_sort`는 0부터 끊김 없이 증가시킨다.

| 컬렉션 | 폰트 | 한 줄 설명 |
|---|---|---|
| dawn-serif | gowun-batang | 공기 같은 가벼움. 본문 15px에서 눈이 편해요. |
| dawn-serif | nanum-myeongjo | 묵직한 제목용. 굵기 대비가 또렷합니다. |
| dawn-serif | song-myung | 고전적인 인상. 표지-인용구에 잘 어울려요. |
| dawn-serif | noto-serif-kr | 여러 굵기로 제목과 본문의 강약을 맞추기 좋아요. |
| dawn-serif | hahmlet | 가는 굵기부터 굵은 제목까지 한 가족으로 고를 수 있어요. |
| brand-gothic | black-han-sans | 굵고 강한 임팩트. 큰 제목에서 빛납니다. |
| brand-gothic | do-hyeon | 둥근 획의 친근함. 캐주얼한 브랜드에 잘 맞아요. |
| brand-gothic | gasoek-one | 좁고 힘 있는 형태가 짧은 제목을 또렷하게 만들어요. |
| brand-gothic | bagel-fat-one | 둥글고 두꺼운 형태로 밝은 첫인상을 만들기 좋아요. |
| brand-gothic | gugi | 손으로 그린 듯한 획이 개성 있는 제목에 어울려요. |
| playful-hand | gaegu | 삐뚤빼뚤 정겨움. 짧은 문구에 특히 좋아요. |
| playful-hand | kirang-haerang | 붓끝의 여운. 감성적인 인용구에 어울립니다. |
| playful-hand | jua | 동글동글 명랑함. 이벤트 배너에 활기를 더해요. |
| playful-hand | nanum-brush-script | 붓글씨 느낌을 살린 짧은 인사말에 어울려요. |
| playful-hand | nanum-pen-script | 펜으로 쓴 듯한 가벼운 문구에 자연스럽게 어울려요. |
| ui-korean-sans | noto-sans-kr | 아홉 굵기를 지원해 화면 정보의 강약을 나누기 좋아요. |
| ui-korean-sans | ibm-plex-sans-kr | 여러 굵기로 제목과 본문을 한 인상으로 맞출 수 있어요. |
| ui-korean-sans | gothic-a1 | 아홉 굵기 중 화면 크기에 맞는 굵기를 고르기 좋아요. |
| ui-korean-sans | nanum-gothic | 익숙하고 단정한 형태로 긴 화면 문구에 쓰기 쉬워요. |
| ui-korean-sans | asta-sans | 얇은 굵기부터 굵은 굵기까지 단계가 고르게 준비돼 있어요. |
| ui-korean-sans | gowun-dodum | 부드러운 인상의 고딕으로 짧은 안내 문구에 어울려요. |
| wide-weight-korean | gothic-a1 | 100부터 900까지 아홉 굵기를 골라 쓸 수 있어요. |
| wide-weight-korean | hahmlet | 100부터 900까지 제목과 본문 굵기를 세밀하게 나눌 수 있어요. |
| wide-weight-korean | noto-sans-kr | 아홉 굵기로 화면의 정보 단계를 한 가족 안에서 표현해요. |
| wide-weight-korean | noto-serif-kr | 여러 굵기의 명조 조합으로 긴 글의 위계를 만들기 좋아요. |
| wide-weight-korean | ibm-plex-sans-kr | 일곱 굵기를 지원해 본문과 강조 문구를 함께 구성하기 좋아요. |
| wide-weight-korean | asta-sans | 여섯 굵기를 지원해 다양한 크기의 한글 조판에 대응해요. |
| korean-display | bagel-fat-one | 둥글고 두꺼운 형태가 짧은 제목에 밝은 힘을 더해요. |
| korean-display | gugi | 굵은 손그림 느낌으로 한두 줄 제목에 개성을 더해요. |
| korean-display | moirai-one | 장식적인 획이 큰 크기의 짧은 영문·한글 문구에 어울려요. |
| korean-display | dokdo | 거친 붓글씨 느낌이 강한 한글 제목을 만들어요. |
| korean-display | cute-font | 작고 둥근 인상이 가벼운 카드와 배너 문구에 어울려요. |
| korean-display | gasoek-one | 압축된 굵은 형태로 좁은 제목 공간에 힘을 줘요. |
| latin-sans-essentials | inter | 여러 굵기를 지원해 영문 화면의 제목과 본문을 맞추기 좋아요. |
| latin-sans-essentials | source-sans-3 | 여러 굵기를 지원해 영문 화면의 제목과 본문을 맞추기 좋아요. |
| latin-sans-essentials | dm-sans | 둥근 인상의 영문 산세리프로 짧은 본문에 쓰기 좋아요. |
| latin-sans-essentials | montserrat | 넓고 또렷한 대문자 형태가 영문 제목에 잘 드러나요. |
| latin-sans-essentials | figtree | 여러 굵기를 지원해 영문 UI의 강약을 나누기 좋아요. |
| latin-serif-editorial | lora | 부드러운 곡선과 세리프가 영문 본문과 인용문에 어울려요. |
| latin-serif-editorial | merriweather | 여러 굵기의 영문 세리프로 긴 문단의 위계를 나누기 좋아요. |
| latin-serif-editorial | eb-garamond | 고전적인 세리프 형태가 책과 매거진 느낌의 글에 어울려요. |
| latin-serif-editorial | libre-baskerville | 또렷한 세리프와 넉넉한 형태로 영문 본문에 쓰기 좋아요. |
| latin-serif-editorial | playfair-display | 굵기 대비가 큰 형태로 영문 큰 제목에 힘을 줘요. |
| latin-serif-editorial | bitter | 단단한 세리프 형태가 화면 속 영문 본문에 또렷하게 보여요. |
| developer-monospace | inconsolata | 글자 폭이 일정해 짧은 코드와 숫자를 맞춰 보기 좋아요. |
| developer-monospace | jetbrains-mono | 다양한 굵기의 고정폭 글자로 코드의 강약을 나누기 좋아요. |
| developer-monospace | roboto-mono | 여러 굵기를 지원해 코드와 표의 숫자를 정렬하기 좋아요. |
| developer-monospace | source-code-pro | 고정폭 영문 글자가 긴 코드 줄에서도 일정하게 이어져요. |
| developer-monospace | nanum-gothic-coding | 한글과 영문을 함께 쓰는 코드 설명에서 폭을 맞추기 좋아요. |
| verified-ofl-picks | noto-sans-kr | OFL 확인이 끝난 아홉 굵기의 한글 고딕이에요. |
| verified-ofl-picks | noto-serif-kr | OFL 확인이 끝난 여러 굵기의 한글 명조예요. |
| verified-ofl-picks | ibm-plex-sans-kr | OFL 확인이 끝난 여러 굵기의 한글 산세리프예요. |
| verified-ofl-picks | inter | OFL 확인이 끝난 다굵기 영문 산세리프예요. |
| verified-ofl-picks | lora | OFL 확인이 끝난 영문 세리프 가족이에요. |
| verified-ofl-picks | jetbrains-mono | OFL 확인이 끝난 다굵기 영문 모노스페이스예요. |
| verified-ofl-picks | bagel-fat-one | OFL 확인이 끝난 한 굵기의 한글 디스플레이 폰트예요. |

- [ ] **Step 4: 변경 전에 모든 전제조건 검사**

`DO` 블록에서 아래를 검사한다. 하나라도 실패하면 `raise exception`으로 전체 마이그레이션을 중단한다.

```sql
do $$
declare
  v_missing_or_unpublished text[];
  v_unverified_license text[];
begin
  if (select count(*) from _collection_defs) <> 10 then
    raise exception 'expected 10 collection definitions';
  end if;

  if exists (
    select 1
    from _collection_defs d
    left join fontagit.collections c on c.slug = d.slug
    where d.preserve_existing_copy and c.id is null
  ) then
    raise exception 'one or more existing collections are missing';
  end if;

  if exists (
    select 1
    from _collection_seed
    group by collection_slug
    having count(*) < 5
  ) then
    raise exception 'every target collection must contain at least 5 fonts';
  end if;

  select array_agg(s.font_slug order by s.font_slug)
  into v_missing_or_unpublished
  from (select distinct font_slug from _collection_seed) s
  left join fontagit.fonts f
    on f.slug = s.font_slug
   and f.status = 'published'
  where f.id is null;

  if v_missing_or_unpublished is not null then
    raise exception 'missing or unpublished fonts: %', v_missing_or_unpublished;
  end if;

  select array_agg(s.font_slug order by s.font_slug)
  into v_unverified_license
  from (select distinct font_slug from _collection_seed) s
  join fontagit.fonts f on f.slug = s.font_slug
  where f.license_verified is not true
     or f.license_type <> 'OFL';

  if v_unverified_license is not null then
    raise exception 'license is not verified OFL: %', v_unverified_license;
  end if;
end
$$;
```

라이선스 검사는 `verified-ofl-picks`의 제목이 거짓이 되지 않게 하는 강한 안전장치다.

- [ ] **Step 5: 신규 7종 upsert, 기존 3종 정렬, 대상 연결 교체**

```sql
insert into fontagit.collections (slug, title, intro, status, sort_order)
select slug, title, intro, 'published', collection_sort
from _collection_defs
where not preserve_existing_copy
on conflict (slug) do update
set title = excluded.title,
    intro = excluded.intro,
    status = excluded.status,
    sort_order = excluded.sort_order;

update fontagit.collections c
set sort_order = d.collection_sort
from _collection_defs d
where c.slug = d.slug
  and d.preserve_existing_copy;

delete from fontagit.collection_items ci
using fontagit.collections c, _collection_defs d
where ci.collection_id = c.id
  and c.slug = d.slug;

insert into fontagit.collection_items (
  collection_id, font_id, comment, sort_order
)
select c.id, f.id, s.comment, s.item_sort
from _collection_seed s
join fontagit.collections c on c.slug = s.collection_slug
join fontagit.fonts f on f.slug = s.font_slug
order by c.sort_order, s.item_sort;
```

기존 3종 외의 컬렉션과 연결은 삭제하거나 수정하지 않는다.

- [ ] **Step 6: 커밋 직전 사후조건 검사**

```sql
do $$
begin
  if (
    select count(*)
    from fontagit.collections c
    join _collection_defs d on d.slug = c.slug
    where c.status = 'published'
  ) <> 10 then
    raise exception 'all 10 target collections must be published';
  end if;

  if exists (
    select 1
    from _collection_defs d
    left join fontagit.collections c on c.slug = d.slug
    left join fontagit.collection_items ci on ci.collection_id = c.id
    left join fontagit.fonts f
      on f.id = ci.font_id
     and f.status = 'published'
    group by d.slug
    having count(f.id) < 5
  ) then
    raise exception 'every target collection must have at least 5 published fonts';
  end if;

  if (
    select count(*)
    from fontagit.collection_items ci
    join fontagit.collections c on c.id = ci.collection_id
    join _collection_defs d on d.slug = c.slug
  ) <> 56 then
    raise exception 'expected exactly 56 target collection items';
  end if;
end
$$;

commit;
```

- [ ] **Step 7: 정적 검토**

```bash
rg -n "begin;|create temporary table|raise exception|on conflict|delete from fontagit.collection_items|expected exactly 56|commit;" \
  supabase/migrations/0020_expand_editorial_collections.sql
git diff --check
```

Expected: 필수 안전장치가 모두 검색되고 `git diff --check`가 출력 없이 종료한다.

- [ ] **Step 8: 마이그레이션만 단독 커밋**

```bash
git add supabase/migrations/0020_expand_editorial_collections.sql
git commit -m "feat: 컬렉션 에디토리얼 시드 10종 확장"
```

---

### Task 2: dev DB 적용과 데이터 불변식 검증

**Files:**

- Consume: `supabase/migrations/0020_expand_editorial_collections.sql`
- Do not commit: DB 연결 정보, 적용 전 스냅샷

- [ ] **Step 1: dev 연결과 적용 전 스냅샷 확인**

운영 DB가 아닌 dev 프로젝트 `zgxtfcpiokhkcrywlxmc`인지 먼저 확인한다. 비밀번호나 토큰은 출력하지 않는다.

```sql
select current_database(), current_user;

select jsonb_build_object(
  'collections',
  coalesce(jsonb_agg(to_jsonb(c) order by c.sort_order), '[]'::jsonb)
)
from fontagit.collections c
where c.slug in ('dawn-serif', 'brand-gothic', 'playful-hand');

select jsonb_agg(to_jsonb(x) order by x.collection_slug, x.item_sort)
from (
  select c.slug as collection_slug, f.slug as font_slug,
         ci.comment, ci.sort_order as item_sort
  from fontagit.collection_items ci
  join fontagit.collections c on c.id = ci.collection_id
  join fontagit.fonts f on f.id = ci.font_id
  where c.slug in ('dawn-serif', 'brand-gothic', 'playful-hand')
) x;
```

결과는 저장소 밖의 임시 파일에만 저장한다. 운영 롤백의 기준은 기존 3종과 기존 8개 연결이다.

- [ ] **Step 2: dev에 0020 적용**

기존 psql pooler 경로를 사용한다. worktree에는 비밀 파일을 복사하지 않고 원래 작업공간의 dev 환경 파일을 읽는다. 프로젝트 ID가 다르거나 DB 비밀번호가 비어 있으면 즉시 중단한다.

```bash
set -a
source /Users/joel.silver/Workspace/gitroom/python/fontagit/apps/web/.env.local
set +a

if [[ "$SUPABASE_DEV_PROJECT_ID" != "zgxtfcpiokhkcrywlxmc" ]]; then
  echo "잘못된 dev 프로젝트입니다."
  exit 1
fi

fontagit_dev_db_password="${SUPABASE_DEV_DB_PASSWORD:-${NEXT_PUBLIC_SUPABASE_PASWORD:-}}"
if [[ -z "$fontagit_dev_db_password" ]]; then
  echo "dev DB 비밀번호가 없습니다."
  exit 1
fi

fontagit_dev_host="aws-0-${SUPABASE_DEV_PROJECT_REGION}.pooler.supabase.com"
fontagit_dev_conn="host=${fontagit_dev_host} port=5432 dbname=postgres user=postgres.${SUPABASE_DEV_PROJECT_ID} sslmode=require connect_timeout=10"

PGPASSWORD="$fontagit_dev_db_password" psql -X "$fontagit_dev_conn" \
  -v ON_ERROR_STOP=1 \
  -f supabase/migrations/0020_expand_editorial_collections.sql
```

`NEXT_PUBLIC_SUPABASE_PASWORD`는 기존 로컬 파일의 과거 변수명만 읽는 호환 경로다. 값을 출력하거나 저장소에 추가하지 않는다.

- [ ] **Step 3: dev 결과 전수 검증**

```sql
select c.sort_order, c.slug, c.title, count(ci.font_id) as font_count
from fontagit.collections c
left join fontagit.collection_items ci on ci.collection_id = c.id
where c.slug in (
  'dawn-serif', 'brand-gothic', 'playful-hand',
  'ui-korean-sans', 'wide-weight-korean', 'korean-display',
  'latin-sans-essentials', 'latin-serif-editorial',
  'developer-monospace', 'verified-ofl-picks'
)
group by c.id
order by c.sort_order;
```

Expected:

- 10행
- `sort_order` 0~9
- 폰트 수 `5, 5, 5, 6, 6, 6, 5, 6, 5, 7`

```sql
select count(*) as invalid_items
from fontagit.collection_items ci
join fontagit.collections c on c.id = ci.collection_id
join fontagit.fonts f on f.id = ci.font_id
where c.slug in (
  'dawn-serif', 'brand-gothic', 'playful-hand',
  'ui-korean-sans', 'wide-weight-korean', 'korean-display',
  'latin-sans-essentials', 'latin-serif-editorial',
  'developer-monospace', 'verified-ofl-picks'
)
and (
  f.status <> 'published'
  or f.license_verified is not true
  or f.license_type <> 'OFL'
);
```

Expected: `0`

- [ ] **Step 4: 멱등성 확인**

같은 마이그레이션을 dev에 한 번 더 실행하고 Step 3을 반복한다.

Expected: 두 번째 실행도 성공하고 컬렉션 10종, 연결 56개, 중복 0건이 유지된다.

- [ ] **Step 5: 누락 폰트 실패 경로 확인**

마이그레이션 파일을 고치지 않는다. 별도 트랜잭션에서 `_collection_seed`와 같은 검증 조건에 존재하지 않는 slug를 넣어 `missing or unpublished fonts` 예외가 발생하는지 확인하고 `rollback`한다. dev의 실제 컬렉션 데이터가 바뀌면 실패다.

---

### Task 3: 웹 정적 생성과 실제 화면 확인

**Files:**

- No source change expected
- Verify: `apps/web/app/collections/page.tsx`
- Verify: `apps/web/app/collections/[slug]/page.tsx`
- Verify: `apps/web/scripts/verify-seo-output.mjs`

- [ ] **Step 1: 의존성 설치 문제를 기능 변경과 분리**

먼저 기준 명령을 재실행한다.

```bash
pnpm install --frozen-lockfile
```

현재 확인된 예상 결과는 lockfile 불일치 실패다. 이 실패가 계속되면:

- 컬렉션 커밋에서 `pnpm-lock.yaml`을 수정하지 않는다.
- 로컬 화면 확인만 위해 `pnpm install --no-frozen-lockfile --lockfile=false`를 사용한다.
- 최종 PR에는 기준 브랜치의 선행 문제라고 분명히 기록한다.
- `--frozen-lockfile`이 통과하도록 기준 브랜치가 고쳐지기 전에는 배포 준비 완료라고 말하지 않는다.

- [ ] **Step 2: dev DB를 사용한 production-mode 정적 빌드와 SEO 검증**

```bash
set -a
source /Users/joel.silver/Workspace/gitroom/python/fontagit/apps/web/.env.local
set +a

if [[ "$SUPABASE_DEV_PROJECT_ID" != "zgxtfcpiokhkcrywlxmc" ]]; then
  echo "잘못된 dev 프로젝트입니다."
  exit 1
fi

pnpm --filter web lint
pnpm --filter web build
pnpm --filter web verify:seo
```

Expected:

- lint 새 오류 0건
- build 성공
- 빌드가 dev DB의 컬렉션 10종을 읽음
- 컬렉션 10종의 정적 경로 생성
- canonical과 sitemap에 컬렉션 상세 URL 10개 포함

- [ ] **Step 3: 실제 화면 확인**

로컬 production 서버를 실행해 브라우저로 확인한다.

```bash
pnpm --filter web start
```

확인 항목:

- `/collections/`에 10개 카드가 순서대로 표시된다.
- 10개 상세 URL이 모두 열린다.
- 각 상세의 폰트 링크가 열린다.
- 모바일 폭에서 가로 넘침과 겹침이 없다.
- 데스크톱에서 기존 3종과 신규 7종의 카드 높이가 비정상적으로 무너지지 않는다.

소스 변경이 없더라도 실제 DB 데이터를 읽는 정적 빌드 결과로 확인한다.

---

### Task 4: 적대적 재검토, 문서, GitHub 동기화

**Files:**

- Modify: `docs/progress/progress.md`
- Verify: `docs/superpowers/specs/2026-07-26-collections-editorial-expansion-design.md`
- Verify: `docs/superpowers/plans/2026-07-26-collections-editorial-expansion.md`

- [ ] **Step 1: 자체 적대적 리뷰**

다음 반대 관점으로 diff와 dev 결과를 다시 본다.

1. 10개처럼 보이지만 실제 연결이 56개가 아닌가?
2. `verified-ofl-picks`에 OFL 미확인 폰트가 섞였는가?
3. 기존 3종의 제목·소개가 덮어써졌는가?
4. 이번 대상이 아닌 컬렉션이나 연결을 삭제했는가?
5. 한 폰트가 같은 컬렉션에 중복됐거나 정렬 번호가 겹쳤는가?
6. 문구가 실제 데이터보다 강한 보장이나 라이선스 단정을 하는가?
7. 두 번째 실행 결과가 첫 번째와 달라졌는가?
8. dev 적용을 운영 적용 또는 배포 완료로 잘못 보고했는가?
9. #107을 이번 컬렉션 작업으로 잘못 갱신했는가?
10. `origin/develop`의 기존 lockfile·파이프라인 실패를 새 회귀로 잘못 단정했는가?

하나라도 걸리면 GitHub 갱신 전에 수정하고 Task 2~3의 관련 검증을 다시 실행한다.

- [ ] **Step 2: 진행 문서 한 줄 기록**

기존 형식을 유지해 아래 사실만 짧게 기록한다.

- 컬렉션 시드 10종·연결 56개
- migration `0020`
- dev 멱등성·불변식 결과
- 웹 build/SEO/실화면 결과
- 기준 브랜치의 선행 실패가 남았다면 별도 표시

- [ ] **Step 3: 검증 후 문서 커밋**

```bash
git add docs/progress/progress.md
git commit -m "docs: 컬렉션 10종 dev 검증 결과 기록"
```

- [ ] **Step 4: #56만 최신화**

#56의 체크 상태는 실제 증거에 맞춰 갱신한다.

- dev만 적용했으면 `운영 DB에 발행 컬렉션 10종 이상`은 체크하지 않는다.
- 데이터 시드 항목은 dev·빌드 검증이 끝난 범위만 체크한다.
- 내부 링크 허브 화면 개선 항목은 이번 단계에서 체크하지 않는다.
- 댓글에 브랜치, 커밋, migration, 검증 결과, 남은 운영 적용·화면 개선을 기록한다.
- #107은 수정하지 않는다.

- [ ] **Step 5: #62 자동 추적 확인**

#56이 GitHub Sub-issue로 #62에 연결돼 있는지 확인한다. 연결돼 있으면 수동 체크박스를 추가하지 않는다. #56을 닫거나 다시 열 때 #62 진행률이 자동 변경되는지만 확인한다.

이번 단계에서는 #56 전체 범위 중 내부 링크 허브와 운영 배포가 남으므로 #56을 닫지 않는다.

---

### Task 5: PR과 운영 적용 게이트

- [ ] **Step 1: 최종 품질 게이트**

```bash
git status --short
git diff origin/develop...HEAD --check
git log --oneline origin/develop..HEAD
```

Expected:

- 의도하지 않은 파일 0개
- 공백 오류 0개
- 설계, 계획, migration, 진행 기록만 포함

- [ ] **Step 2: 브랜치 push와 PR**

PR base는 반드시 `develop`로 지정한다. PR 본문에 아래 상태를 분리한다.

- 코드 작성
- dev DB 적용·검증
- 정적 빌드·SEO
- 운영 DB 적용
- 운영 배포·실제 URL 확인
- 기준 브랜치의 lockfile·파이프라인 선행 실패

- [ ] **Step 3: PR 병합 후 운영 적용 전 스냅샷**

운영 DB에 쓰기 전에 기존 3종과 8개 연결을 JSON 또는 SQL 결과로 저장한다. dev에서 사용한 것과 같은 프로젝트 ID를 쓰지 않았는지 확인한다.

- [ ] **Step 4: 운영 DB에 0020 적용**

운영 연결 문자열을 명시적으로 확인한 뒤 `ON_ERROR_STOP=1`로 마이그레이션을 적용한다. 적용 후 Task 2 Step 3의 두 검증 쿼리를 운영 DB에서 다시 실행한다.

- [ ] **Step 5: 배포와 실제 URL 확인**

운영 DB에 0020을 적용한 뒤 운영 환경으로 정적 빌드를 다시 실행한다. `develop → main → deploy`가 끝난 뒤 운영 `/collections/`와 10개 상세 URL을 직접 확인한다. 이 단계까지 성공해야 #56의 운영 완료 조건을 체크할 수 있다.

## 롤백

운영에서 문제가 생기면 새 7종만 삭제하고 기존 3종의 연결을 적용 전 8개로 복구한다.

```sql
begin;

delete from fontagit.collections
where slug in (
  'ui-korean-sans', 'wide-weight-korean', 'korean-display',
  'latin-sans-essentials', 'latin-serif-editorial',
  'developer-monospace', 'verified-ofl-picks'
);

delete from fontagit.collection_items ci
using fontagit.collections c
where ci.collection_id = c.id
  and c.slug in ('dawn-serif', 'brand-gothic', 'playful-hand');

-- 적용 전 저장한 기존 8개 연결을 여기서 복원한다.
-- 고정 UUID를 쓰지 말고 collection slug와 font slug로 다시 조인한다.

commit;
```

롤백 SQL은 스냅샷의 8개 행을 실제로 채운 뒤 별도 검토하고 실행한다. 주석 상태로 실행하거나 기억에 의존해 복원하지 않는다.
