-- archive 출처 등급 지원: fonts 테이블의 download_source_kind, license_source_kind 검증 확장
-- 기존: official, public만 허용
-- 변경 후: official, public, archive 허용

begin;

alter table fontagit.fonts
  drop constraint fonts_download_source_kind_chk,
  drop constraint fonts_license_source_kind_chk;

alter table fontagit.fonts
  add constraint fonts_download_source_kind_chk
    check (download_source_kind is null or download_source_kind in ('official', 'public', 'archive')),
  add constraint fonts_license_source_kind_chk
    check (license_source_kind is null or license_source_kind in ('official', 'public', 'archive'));

commit;
