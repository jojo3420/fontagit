-- archive 출처 등급 지원: fonts 테이블의 download_source_kind 검증 확장
-- 기존: official, public만 허용
-- 변경 후: official, public, archive 허용
-- 주의: license_source_kind는 변경하지 않음 (archive로 license 자동 승인 금지)

begin;

alter table fontagit.fonts
  drop constraint fonts_download_source_kind_chk;

alter table fontagit.fonts
  add constraint fonts_download_source_kind_chk
    check (download_source_kind is null or download_source_kind in ('official', 'public', 'archive'));

commit;
