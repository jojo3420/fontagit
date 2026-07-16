-- 컬렉션 시드: 목업 기반 3종. slug 조인으로 실DB font_id 참조(UUID 하드코딩 회피).
-- brand-gothic은 실DB에 없는 pretendard 제외(2종). 멱등: on conflict do nothing.

insert into fontagit.collections (slug, title, intro, status, sort_order)
values
  ('dawn-serif', '새벽 감성 명조 모음',
   '긴 글에 어울리는, 획이 차분한 명조들을 모았어요. 에세이-브랜드 소개문-전자책 본문에 특히 잘 맞습니다.',
   'published', 0),
  ('brand-gothic', '브랜드 첫인상 고딕',
   '로고와 헤드라인에서 또렷하게 읽히는 고딕을 모았어요. 포스터-배너-앱 UI에 두루 쓰기 좋습니다.',
   'published', 1),
  ('playful-hand', '손끝의 온기 손글씨',
   '사람 손으로 쓴 듯한 따뜻함을 담은 서체 모음이에요. 카드-굿즈-SNS 문구에 잘 어울립니다.',
   'published', 2)
on conflict (slug) do nothing;

insert into fontagit.collection_items (collection_id, font_id, comment, sort_order)
select c.id, f.id, v.comment, v.sort_order
from (values
  ('dawn-serif',   'gowun-batang',   '공기 같은 가벼움. 본문 15px에서 눈이 편해요.',   0),
  ('dawn-serif',   'nanum-myeongjo', '묵직한 제목용. 굵기 대비가 또렷합니다.',         1),
  ('dawn-serif',   'song-myung',     '고전적인 인상. 표지-인용구에 잘 어울려요.',       2),
  ('brand-gothic', 'black-han-sans', '굵고 강한 임팩트. 큰 제목에서 빛납니다.',         0),
  ('brand-gothic', 'do-hyeon',       '둥근 획의 친근함. 캐주얼한 브랜드에 잘 맞아요.',   1),
  ('playful-hand', 'gaegu',          '삐뚤빼뚤 정겨움. 짧은 문구에 특히 좋아요.',       0),
  ('playful-hand', 'kirang-haerang', '붓끝의 여운. 감성적인 인용구에 어울립니다.',       1),
  ('playful-hand', 'jua',            '동글동글 명랑함. 이벤트 배너에 활기를 더해요.',    2)
) as v(col_slug, font_slug, comment, sort_order)
join fontagit.collections c on c.slug = v.col_slug
join fontagit.fonts f on f.slug = v.font_slug
on conflict (collection_id, font_id) do nothing;
