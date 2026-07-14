create schema if not exists fontagit;
grant usage on schema fontagit to anon, authenticated, service_role;

create table fontagit.fonts (
  id                 uuid primary key default gen_random_uuid(),
  slug               text not null unique,
  name_en            text not null,
  name_ko            text,
  foundry            text,
  source_tier        text not null default 'A',
  category_ko        text not null,
  category_google    text,
  subsets            text[] not null default '{}',
  variants           text[] not null default '{}',
  weights            int[]  not null default '{}',
  is_commercial_free boolean not null default false,
  license_type       text,
  license_verified   boolean not null default false,
  official_url       text not null,
  status             text not null default 'draft',
  version            text,
  last_modified      text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  constraint fonts_status_chk check (status in ('draft','published','archived')),
  constraint fonts_tier_chk   check (source_tier in ('A','B','C')),
  constraint fonts_cat_chk    check (category_ko in ('고딕','명조','손글씨','장식')),
  constraint fonts_license_verify_chk check (license_type is null or license_verified = true)
);
create index idx_fonts_status on fontagit.fonts(status);

create table fontagit.aliases (
  id         uuid primary key default gen_random_uuid(),
  font_id    uuid not null references fontagit.fonts(id) on delete cascade,
  alias      text not null,
  alias_norm text not null,
  unique (font_id, alias_norm)
);
create index idx_aliases_font on fontagit.aliases(font_id);

create table fontagit.collections (
  id         uuid primary key default gen_random_uuid(),
  slug       text not null unique,
  title      text not null,
  intro      text not null,
  status     text not null default 'draft' check (status in ('draft','published','archived')),
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);
create table fontagit.collection_items (
  collection_id uuid not null references fontagit.collections(id) on delete cascade,
  font_id       uuid not null references fontagit.fonts(id) on delete cascade,
  comment       text,
  sort_order    int not null default 0,
  primary key (collection_id, font_id)
);

grant select on all tables in schema fontagit to anon, authenticated;

alter table fontagit.fonts enable row level security;
alter table fontagit.aliases enable row level security;
alter table fontagit.collections enable row level security;
alter table fontagit.collection_items enable row level security;

create policy anon_read_published_fonts on fontagit.fonts
  for select to anon using (status = 'published');
create policy anon_read_aliases on fontagit.aliases
  for select to anon using (exists (
    select 1 from fontagit.fonts f where f.id = font_id and f.status = 'published'));
create policy anon_read_published_collections on fontagit.collections
  for select to anon using (status = 'published');
create policy anon_read_collection_items on fontagit.collection_items
  for select to anon using (exists (
    select 1 from fontagit.collections c where c.id = collection_id and c.status = 'published'));
