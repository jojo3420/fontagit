do $$
begin
  if not exists (
    select 1
    from pg_attribute a
    join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
    where a.attrelid = 'fontagit.fonts'::regclass
      and a.attname = 'subsets'
      and format_type(a.atttypid, a.atttypmod) = 'text[]'
      and a.attnotnull
      and pg_get_expr(d.adbin, d.adrelid) = '''{}''::text[]'
  ) then
    raise exception 'fonts.subsets schema mismatch';
  end if;
  if (
    select count(*) from pg_constraint
    where conname in (
      'fonts_allow_embedding_chk',
      'fonts_allow_redistribute_chk',
      'fonts_allow_modify_chk'
    )
  ) <> 3 then
    raise exception 'license permission CHECK missing';
  end if;
  if to_regclass('fontagit.font_sources') is null then
    raise exception 'font_sources missing';
  end if;
  if to_regclass('fontagit.font_audit_runs') is null then
    raise exception 'font_audit_runs missing';
  end if;
  if to_regclass('fontagit.font_source_snapshots') is null then
    raise exception 'font_source_snapshots missing';
  end if;
  if to_regclass('fontagit.font_link_observations') is null then
    raise exception 'font_link_observations missing';
  end if;
  if to_regclass('fontagit.font_audit_findings') is null then
    raise exception 'font_audit_findings missing';
  end if;
  if (
    select count(*)
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'fontagit'
      and c.relname in (
        'font_sources',
        'font_audit_runs',
        'font_source_snapshots',
        'font_link_observations',
        'font_audit_findings'
      )
      and c.relrowsecurity
  ) <> 5 then
    raise exception 'font audit RLS missing';
  end if;
  if (
    select count(*) from pg_constraint
    where conname in (
      'fonts_download_evidence_id_fkey',
      'fonts_license_evidence_id_fkey',
      'fonts_script_evidence_id_fkey'
    )
  ) <> 3 then
    raise exception 'font evidence FK missing';
  end if;
end $$;

select 'ALL PASS' as result;
