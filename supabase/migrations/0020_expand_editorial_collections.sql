-- 수동 큐레이션 컬렉션을 3종에서 10종으로 확장한다.
-- 대상 폰트와 기존 컬렉션을 먼저 검증하고, 대상 10종의 연결만 멱등 교체한다.

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
  item_sort int not null check (item_sort >= 0),
  primary key (collection_slug, font_slug),
  unique (collection_slug, item_sort)
) on commit drop;

insert into _collection_defs (
  slug, title, intro, collection_sort, preserve_existing_copy
)
values
  (
    'dawn-serif',
    '새벽 감성 명조 모음',
    '긴 글에 어울리는, 획이 차분한 명조들을 모았어요. 에세이-브랜드 소개문-전자책 본문에 특히 잘 맞습니다.',
    0,
    true
  ),
  (
    'brand-gothic',
    '브랜드 첫인상 고딕',
    '로고와 헤드라인에서 또렷하게 읽히는 고딕을 모았어요. 포스터-배너-앱 UI에 두루 쓰기 좋습니다.',
    1,
    true
  ),
  (
    'playful-hand',
    '손끝의 온기 손글씨',
    '사람 손으로 쓴 듯한 따뜻함을 담은 서체 모음이에요. 카드-굿즈-SNS 문구에 잘 어울립니다.',
    2,
    true
  ),
  (
    'ui-korean-sans',
    '화면에 또렷한 한글 고딕',
    '작은 화면부터 큰 제목까지 폭넓게 쓸 수 있는 한글 고딕을 모았어요. 서비스 화면과 정보 전달용 문서에 활용하기 좋습니다.',
    3,
    false
  ),
  (
    'wide-weight-korean',
    '굵기를 자유롭게 고르는 한글 폰트',
    '여러 굵기를 지원해 한 가족 안에서 정보의 강약을 나누기 좋은 폰트예요. 제목과 본문을 같은 인상으로 맞출 때 유용합니다.',
    4,
    false
  ),
  (
    'korean-display',
    '한눈에 꽂히는 한글 디스플레이',
    '형태가 뚜렷해 짧은 문구에 힘을 주는 한글 폰트를 모았어요. 포스터와 배너의 큰 제목에 먼저 살펴보세요.',
    5,
    false
  ),
  (
    'latin-sans-essentials',
    '영문 산세리프 기본 컬렉션',
    '영문 제목과 본문에 두루 쓰기 쉬운 산세리프를 모았어요. 화면과 브랜드 문구의 기본 후보로 비교해 보세요.',
    6,
    false
  ),
  (
    'latin-serif-editorial',
    '영문 에디토리얼 세리프',
    '긴 글과 인용문에 차분한 인상을 주는 영문 세리프를 모았어요. 매거진과 소개 페이지의 제목·본문 조합을 살펴보세요.',
    7,
    false
  ),
  (
    'developer-monospace',
    '코드와 숫자를 위한 모노스페이스',
    '글자 폭이 일정한 모노스페이스를 모았어요. 코드 예시와 숫자가 많은 표에서 모양을 비교하기 좋습니다.',
    8,
    false
  ),
  (
    'verified-ofl-picks',
    'OFL 라이선스 확인 추천',
    'FontAgit에서 OFL 확인이 끝난 폰트 중 서로 다른 인상의 후보를 모았어요. 사용 전에는 상세 화면의 최신 라이선스 근거도 함께 확인하세요.',
    9,
    false
  );

insert into _collection_seed (
  collection_slug, font_slug, comment, item_sort
)
values
  ('dawn-serif', 'gowun-batang', '공기 같은 가벼움. 본문 15px에서 눈이 편해요.', 0),
  ('dawn-serif', 'nanum-myeongjo', '묵직한 제목용. 굵기 대비가 또렷합니다.', 1),
  ('dawn-serif', 'song-myung', '고전적인 인상. 표지-인용구에 잘 어울려요.', 2),
  ('dawn-serif', 'noto-serif-kr', '여러 굵기로 제목과 본문의 강약을 맞추기 좋아요.', 3),
  ('dawn-serif', 'hahmlet', '가는 굵기부터 굵은 제목까지 한 가족으로 고를 수 있어요.', 4),

  ('brand-gothic', 'black-han-sans', '굵고 강한 임팩트. 큰 제목에서 빛납니다.', 0),
  ('brand-gothic', 'do-hyeon', '둥근 획의 친근함. 캐주얼한 브랜드에 잘 맞아요.', 1),
  ('brand-gothic', 'gasoek-one', '좁고 힘 있는 형태가 짧은 제목을 또렷하게 만들어요.', 2),
  ('brand-gothic', 'bagel-fat-one', '둥글고 두꺼운 형태로 밝은 첫인상을 만들기 좋아요.', 3),
  ('brand-gothic', 'gugi', '손으로 그린 듯한 획이 개성 있는 제목에 어울려요.', 4),

  ('playful-hand', 'gaegu', '삐뚤빼뚤 정겨움. 짧은 문구에 특히 좋아요.', 0),
  ('playful-hand', 'kirang-haerang', '붓끝의 여운. 감성적인 인용구에 어울립니다.', 1),
  ('playful-hand', 'jua', '동글동글 명랑함. 이벤트 배너에 활기를 더해요.', 2),
  ('playful-hand', 'nanum-brush-script', '붓글씨 느낌을 살린 짧은 인사말에 어울려요.', 3),
  ('playful-hand', 'nanum-pen-script', '펜으로 쓴 듯한 가벼운 문구에 자연스럽게 어울려요.', 4),

  ('ui-korean-sans', 'noto-sans-kr', '아홉 굵기를 지원해 화면 정보의 강약을 나누기 좋아요.', 0),
  ('ui-korean-sans', 'ibm-plex-sans-kr', '여러 굵기로 제목과 본문을 한 인상으로 맞출 수 있어요.', 1),
  ('ui-korean-sans', 'gothic-a1', '아홉 굵기 중 화면 크기에 맞는 굵기를 고르기 좋아요.', 2),
  ('ui-korean-sans', 'nanum-gothic', '익숙하고 단정한 형태로 긴 화면 문구에 쓰기 쉬워요.', 3),
  ('ui-korean-sans', 'asta-sans', '얇은 굵기부터 굵은 굵기까지 단계가 고르게 준비돼 있어요.', 4),
  ('ui-korean-sans', 'gowun-dodum', '부드러운 인상의 고딕으로 짧은 안내 문구에 어울려요.', 5),

  ('wide-weight-korean', 'gothic-a1', '100부터 900까지 아홉 굵기를 골라 쓸 수 있어요.', 0),
  ('wide-weight-korean', 'hahmlet', '100부터 900까지 제목과 본문 굵기를 세밀하게 나눌 수 있어요.', 1),
  ('wide-weight-korean', 'noto-sans-kr', '아홉 굵기로 화면의 정보 단계를 한 가족 안에서 표현해요.', 2),
  ('wide-weight-korean', 'noto-serif-kr', '여러 굵기의 명조 조합으로 긴 글의 위계를 만들기 좋아요.', 3),
  ('wide-weight-korean', 'ibm-plex-sans-kr', '일곱 굵기를 지원해 본문과 강조 문구를 함께 구성하기 좋아요.', 4),
  ('wide-weight-korean', 'asta-sans', '여섯 굵기를 지원해 다양한 크기의 한글 조판에 대응해요.', 5),

  ('korean-display', 'bagel-fat-one', '둥글고 두꺼운 형태가 짧은 제목에 밝은 힘을 더해요.', 0),
  ('korean-display', 'gugi', '굵은 손그림 느낌으로 한두 줄 제목에 개성을 더해요.', 1),
  ('korean-display', 'moirai-one', '장식적인 획이 큰 크기의 짧은 영문·한글 문구에 어울려요.', 2),
  ('korean-display', 'dokdo', '거친 붓글씨 느낌이 강한 한글 제목을 만들어요.', 3),
  ('korean-display', 'cute-font', '작고 둥근 인상이 가벼운 카드와 배너 문구에 어울려요.', 4),
  ('korean-display', 'gasoek-one', '압축된 굵은 형태로 좁은 제목 공간에 힘을 줘요.', 5),

  ('latin-sans-essentials', 'inter', '여러 굵기를 지원해 영문 화면의 제목과 본문을 맞추기 좋아요.', 0),
  ('latin-sans-essentials', 'source-sans-3', '여러 굵기를 지원해 영문 화면의 제목과 본문을 맞추기 좋아요.', 1),
  ('latin-sans-essentials', 'dm-sans', '둥근 인상의 영문 산세리프로 짧은 본문에 쓰기 좋아요.', 2),
  ('latin-sans-essentials', 'montserrat', '넓고 또렷한 대문자 형태가 영문 제목에 잘 드러나요.', 3),
  ('latin-sans-essentials', 'figtree', '여러 굵기를 지원해 영문 UI의 강약을 나누기 좋아요.', 4),

  ('latin-serif-editorial', 'lora', '부드러운 곡선과 세리프가 영문 본문과 인용문에 어울려요.', 0),
  ('latin-serif-editorial', 'merriweather', '여러 굵기의 영문 세리프로 긴 문단의 위계를 나누기 좋아요.', 1),
  ('latin-serif-editorial', 'eb-garamond', '고전적인 세리프 형태가 책과 매거진 느낌의 글에 어울려요.', 2),
  ('latin-serif-editorial', 'libre-baskerville', '또렷한 세리프와 넉넉한 형태로 영문 본문에 쓰기 좋아요.', 3),
  ('latin-serif-editorial', 'playfair-display', '굵기 대비가 큰 형태로 영문 큰 제목에 힘을 줘요.', 4),
  ('latin-serif-editorial', 'bitter', '단단한 세리프 형태가 화면 속 영문 본문에 또렷하게 보여요.', 5),

  ('developer-monospace', 'inconsolata', '글자 폭이 일정해 짧은 코드와 숫자를 맞춰 보기 좋아요.', 0),
  ('developer-monospace', 'jetbrains-mono', '다양한 굵기의 고정폭 글자로 코드의 강약을 나누기 좋아요.', 1),
  ('developer-monospace', 'roboto-mono', '여러 굵기를 지원해 코드와 표의 숫자를 정렬하기 좋아요.', 2),
  ('developer-monospace', 'source-code-pro', '고정폭 영문 글자가 긴 코드 줄에서도 일정하게 이어져요.', 3),
  ('developer-monospace', 'nanum-gothic-coding', '한글과 영문을 함께 쓰는 코드 설명에서 폭을 맞추기 좋아요.', 4),

  ('verified-ofl-picks', 'noto-sans-kr', 'OFL 확인이 끝난 아홉 굵기의 한글 고딕이에요.', 0),
  ('verified-ofl-picks', 'noto-serif-kr', 'OFL 확인이 끝난 여러 굵기의 한글 명조예요.', 1),
  ('verified-ofl-picks', 'ibm-plex-sans-kr', 'OFL 확인이 끝난 여러 굵기의 한글 산세리프예요.', 2),
  ('verified-ofl-picks', 'inter', 'OFL 확인이 끝난 다굵기 영문 산세리프예요.', 3),
  ('verified-ofl-picks', 'lora', 'OFL 확인이 끝난 영문 세리프 가족이에요.', 4),
  ('verified-ofl-picks', 'jetbrains-mono', 'OFL 확인이 끝난 다굵기 영문 모노스페이스예요.', 5),
  ('verified-ofl-picks', 'bagel-fat-one', 'OFL 확인이 끝난 한 굵기의 한글 디스플레이 폰트예요.', 6);

do $$
declare
  v_missing_existing_collections text[];
  v_missing_or_unpublished text[];
  v_unverified_license text[];
begin
  if (select count(*) from _collection_defs) <> 10 then
    raise exception 'expected 10 collection definitions';
  end if;

  if (select count(*) from _collection_seed) <> 56 then
    raise exception 'expected 56 collection seed items';
  end if;

  if exists (
    select 1
    from _collection_seed
    group by collection_slug
    having count(*) < 5
       or min(item_sort) <> 0
       or max(item_sort) <> count(*) - 1
  ) then
    raise exception 'every target collection must have 5+ fonts and contiguous sort order';
  end if;

  select array_agg(d.slug order by d.slug)
  into v_missing_existing_collections
  from _collection_defs d
  left join fontagit.collections c on c.slug = d.slug
  where d.preserve_existing_copy
    and c.id is null;

  if v_missing_existing_collections is not null then
    raise exception 'existing collections are missing: %', v_missing_existing_collections;
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
     or f.license_type is distinct from 'OFL';

  if v_unverified_license is not null then
    raise exception 'license is not verified OFL: %', v_unverified_license;
  end if;
end
$$;

-- 검증과 변경 사이에 대상 행이 달라지지 않도록 잠근다.
do $$
begin
  perform f.id
  from fontagit.fonts f
  where exists (
    select 1
    from _collection_seed s
    where s.font_slug = f.slug
  )
  for share;

  perform c.id
  from fontagit.collections c
  join _collection_defs d on d.slug = c.slug
  for update;
end
$$;

create temporary table _preserved_collections
on commit drop
as
select c.slug, c.title, c.intro
from fontagit.collections c
join _collection_defs d on d.slug = c.slug
where d.preserve_existing_copy;

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

  if exists (
    select 1
    from fontagit.collection_items ci
    join fontagit.collections c on c.id = ci.collection_id
    join _collection_defs d on d.slug = c.slug
    join fontagit.fonts f on f.id = ci.font_id
    where f.status <> 'published'
       or f.license_verified is not true
       or f.license_type is distinct from 'OFL'
  ) then
    raise exception 'target collection contains an invalid font';
  end if;

  if exists (
    select 1
    from _preserved_collections p
    join fontagit.collections c on c.slug = p.slug
    where c.title is distinct from p.title
       or c.intro is distinct from p.intro
  ) then
    raise exception 'existing collection copy changed unexpectedly';
  end if;
end
$$;

commit;
