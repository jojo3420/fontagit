-- ollidam 실DB 드리프트 교정: collections/collection_items의 anon SELECT 권한 복구.
-- 증상: anon이 fonts는 읽지만 collections는 0건 → SSG 빌드(output:export) 실패.
-- 원인 추정: 0001의 collections 관련 grant/policy가 ollidam에 미적용.
-- 멱등: grant는 반복 안전, policy는 drop if exists 후 재생성.

grant usage on schema fontagit to anon;
grant select on fontagit.collections to anon;
grant select on fontagit.collection_items to anon;

alter table fontagit.collections enable row level security;
alter table fontagit.collection_items enable row level security;

drop policy if exists anon_read_published_collections on fontagit.collections;
create policy anon_read_published_collections on fontagit.collections
  for select to anon using (status = 'published');

drop policy if exists anon_read_collection_items on fontagit.collection_items;
create policy anon_read_collection_items on fontagit.collection_items
  for select to anon using (exists (
    select 1 from fontagit.collections c
    where c.id = collection_id and c.status = 'published'));
