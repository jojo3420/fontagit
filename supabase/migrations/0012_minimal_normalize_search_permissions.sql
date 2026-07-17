-- =============================================================================
-- 0012_minimal_normalize_search_permissions.sql
-- normalize_search 최소권한 회수
-- =============================================================================
-- 현황: normalize_search(text)는 0006에서 PUBLIC(기본) 권한으로 생성됨.
-- 용도: 검색어 정규화(소문자 + 공백제거 + NFC) 헬퍼 함수
-- 사용처: 0009의 search_fonts(q text, lim int)가 SECURITY DEFINER로 내부 호출
--
-- 검증:
-- - search_fonts는 SECURITY DEFINER (0009:60 확인)
-- - anon은 search_fonts로만 검색 가능 (RPC 간접 호출)
-- - normalize_search 직접 호출 경로 없음 (0006, 0009 grep 확인)
--
-- 조치: PUBLIC 및 anon EXECUTE 회수 (owner 및 superuser는 유지)
-- =============================================================================

revoke execute on function fontagit.normalize_search(text) from public;
revoke execute on function fontagit.normalize_search(text) from anon;

comment on function fontagit.normalize_search(text) is
  '별칭 검색 정규화 헬퍼(내부용). search_fonts(SECURITY DEFINER)가 소유자 권한으로만 호출.';
