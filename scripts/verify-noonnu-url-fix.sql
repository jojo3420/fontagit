-- 눈누 official_url 오염 정정 검증 (#150)
--
-- dev와 prod에서 동일하게 실행한다. :run_id는 적재 run의 UUID로 치환한다
-- (MCP로 실행할 때는 문자열을 직접 넣는다: '...'::uuid).
--
-- 컬럼 실존 확인: 2026-07-30, dev information_schema 조회로 아래 전부 확인함
--   font_audit_findings(run_id, font_id, field_name, before_value, proposed_value,
--                       evidence_id, confidence, auto_applicable, review_reason, status)
--
-- 적용 전 dev 기준값(2026-07-30 실측): contaminated_remaining=173, corrected=0
--   173 중 1건(신촌랩소디체)은 눈누 소스가 없는 별개 오염이라 이번 정정 대상이 아니다.
--   prod는 172건이다.

-- (1) 오염 잔존: 적용 후에는 사람 검수 대기분만 남아야 한다
select count(*) as contaminated_remaining
from fontagit.fonts
where official_url = 'https://www.instagram.com/noonnu_official/'
   or license_source_url = 'https://www.instagram.com/noonnu_official/';

-- (2) 정정 반영 건수: 기대 175
--     auto_fix_safe 174 + google-sans-flex의 license_source_url 1
--     (google-sans-flex는 official_url 대체값이 없어 그 필드만 사람 검수로 남는다)
select count(*) as corrected
from fontagit.fonts f
join fontagit.font_sources s on s.font_id = f.id and s.provider = 'noonnu'
where f.license_source_url like 'https://noonnu.cc/font_page/%';

-- (3) 사람 검수 대기: 미승인 상태로 남아야 한다
--     기대: manual_review 10종분 + google-sans-flex의 official_url 1건
select count(*) as pending_review
from fontagit.font_audit_findings
where run_id = :run_id
  and auto_applicable = false
  and status <> 'approved';

-- (4) 적재 정합성: finding 수가 대상 폰트 수의 2배 근방인지
--     google-sans-flex 때문에 정확히 2배는 아닐 수 있다. 차이를 설명할 수 있어야 한다.
select
  count(*) as findings,
  count(distinct font_id) as fonts,
  count(distinct evidence_id) as evidences
from fontagit.font_audit_findings
where run_id = :run_id;

-- (5) 필드별 분포: 승인 전 --dry-run 건수와 대조한다
--     기대: official_url 174, license_source_url 175
select field_name, auto_applicable, count(*) as cnt
from fontagit.font_audit_findings
where run_id = :run_id
group by field_name, auto_applicable
order by field_name, auto_applicable;
