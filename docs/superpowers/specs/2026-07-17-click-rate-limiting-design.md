# 클릭 rate limiting 설계 (슬라이스3 후속)

- 작성일: 2026-07-17
- 대상 기능: 공식 링크 '이동' 클릭 집계(F-03, 슬라이스3)의 어뷰징 방어
- 선행: 마이그레이션 0007(`font_clicks`/`record_click`/`get_top_fonts`) 완료-머지(PR #17)
- 상태: 구현 완료, PR #18 리뷰 반영(try advisory lock으로 리소스 보호 강화 — S2)

## 1. 목적과 위협 모델

`record_click` RPC는 anon 공개 fire-and-forget이라 누구나 무제한 호출 가능하다. 방어 목표는 **둘 다**:

- **랭킹 조작 방지**: 특정 폰트 클릭을 대량 삽입해 홈/트렌드 TOP10 순위를 왜곡하는 행위 차단.
- **리소스 보호**: 자동화 봇이 `font_clicks` 테이블을 폭증시켜 자체호스팅 OCI VM 저장소-비용을 소모하는 것 차단.

## 2. 확정 전제(브레인스토밍 결정)

| 항목 | 결정 | 근거 |
|------|------|------|
| IP 사용 | DB에 저장하지 않고 게이트웨이의 순간 rate 판단에만 사용 허용 | 익명 원칙(영구 저장 금지)과 양립. 출처 구분 없이는 랭킹 조작 방어 불가 |
| 배포 형태 | Next 앱은 `output: "export"` 정적 SSG → Next 서버 없음 | `next.config.ts` 확인. 서버 프록시(C안) 탈락 |
| 클릭 경로 | 브라우저 → 자체호스팅 Supabase 직접(`OfficialLinkCta` onClick → `supabaseClient.rpc`) | IP를 볼 수 있는 지점은 Supabase 앞단 Kong뿐 |
| 방어 지점 | A(Kong IP 제한) + B(DB 함수 최후방어) 계층 | 위협 모델 '둘 다'에 부합 |
| 마이그레이션 번호 | rate limit = **0008**, 등록 신청 = **0009**로 재배치 | 순번 연속성 유지. 0007은 dev 적용 완료라 수정 금지, 신규 파일로 |

## 3. 아키텍처 (2계층 방어)

```
브라우저(onClick) ──POST /rest/v1/rpc/record_click──▶ [Kong 게이트웨이] ──▶ [PostgREST] ──▶ record_click()
                                                        │                                     │
                                                    1차: IP당 분당 30건 초과 → 429      2차: 폰트별 10초 20건 초과 → 조용히 무시
                                                    (정밀 방어, 출처 구분)              (안전밸브, dev/Kong우회 대비)
```

- **1차(A, Kong)**: 출처(IP)를 구분해 정밀 차단. DB에 닿기 전에 막아 리소스 보호에 최적. prod 전용(dev는 Kong 없는 클라우드).
- **2차(B, DB 함수)**: IP를 못 쓰므로 **폰트별 전역** 상한. Kong이 없는 dev, Kong 우회, 임계값 이하 저속 조작에 대한 최후방어. dev/prod 동일 적용.

두 계층은 독립적이며 한쪽이 뚫려도 나머지가 받친다.

## 4. B안 상세 — DB 함수 최후방어 (이 세션 구현)

### 4.1 동작

`record_click`을 `create or replace`로 교체. insert 직전에 폰트별 슬라이딩 윈도우 상한 검사를 추가한다.

- **규칙**: 같은 `font_id`가 **최근 10초에 20건 이상** 이미 기록됐으면 이번 클릭을 **무시**(insert 스킵).
- **동시성 방어(race 제거) + 리소스 보호(S2)**: `count(*)` 후 `insert`는 원자적이지 않아, 동시 요청이 같은 스냅샷을 읽고 모두 통과하는 TOCTOU(Time-Of-Check-To-Time-Of-Use) 결함이 있다. font_id 확정 직후 `pg_try_advisory_xact_lock(hashtext('fontagit.record_click'), hashtext(p_slug))`으로 **같은 폰트 요청을 직렬화**하되, 대기(blocking)가 아니라 **획득 실패 시 조용히 무시**한다 → 봇 폭주 시 락 대기로 DB/PostgREST 연결이 점유되는 것을 막는다. 경합 시 일부 요청이 카운트 없이 무시되지만 rate limit 목적(과다 기록 차단)엔 안전하고 fire-and-forget과 일치. 2-key namespace로 타 기능 락과 충돌 방지, 다른 폰트는 다른 키라 병렬 유지. (리뷰 M1+S2)
- **fire-and-forget 계약 유지**: 초과 시에도 오류를 던지지 않고 `return`(클라이언트는 성공/실패를 구분하지 않음).
- **인덱스 재사용**: 0007의 `idx_font_clicks_font_time (font_id, clicked_at)`를 그대로 활용 → count 쿼리 저비용.

### 4.2 임계값 근거

폰트당 10초 20건은 정상 사용자가 도달 불가능한 값이다(한 사람이 같은 폰트 공식링크를 10초에 20번 누를 일 없음). 정상 클릭은 절대 안 걸리고 봇 연타만 차단하는 "넉넉한 안전밸브"로 설정. 값은 함수 상단 `declare` 상수로 명명해 추후 조정 용이하게 한다(하드코딩 매직넘버 회피).

### 4.3 마이그레이션 0008 골격

```sql
-- 0008: record_click 폰트별 rate limit (슬라이스3 후속, 2차 최후방어)
create or replace function fontagit.record_click(p_slug text)
returns void
language plpgsql
security definer
set search_path = fontagit, pg_temp
as $$
declare
  v_font_id uuid;
  c_window  constant interval := interval '10 seconds';  -- 슬라이딩 윈도우
  c_max     constant int      := 20;                     -- 윈도우 내 폰트별 상한
  v_recent  int;
begin
  if p_slug is null or p_slug = '' or char_length(p_slug) > 200 then
    return;
  end if;

  select id into v_font_id
  from fonts
  where slug = p_slug and status = 'published';

  if v_font_id is null then
    return;
  end if;

  -- race 제거(M1) + 리소스 보호(S2): 같은 폰트 동시 요청을 직렬화하되 대기 대신 try 방식으로
  -- 획득 실패 시 조용히 무시(blocking 연결 점유 회피). 2-key namespace로 타 기능 락과 충돌 방지.
  if not pg_try_advisory_xact_lock(hashtext('fontagit.record_click'), hashtext(p_slug)) then
    return;
  end if;

  -- 2차 안전밸브: 폰트별 최근 윈도우 삽입량이 상한 이상이면 조용히 무시
  select count(*) into v_recent
  from font_clicks
  where font_id = v_font_id
    and clicked_at >= now() - c_window;

  if v_recent >= c_max then
    return;
  end if;

  insert into font_clicks (font_id) values (v_font_id);
end;
$$;
```

권한/코멘트는 0007과 동일 유지(`revoke ... from public; grant execute ... to anon;`). `create or replace`라 기존 grant는 보존되지만, 마이그레이션 재현성을 위해 grant 문을 함께 기술한다.

> 락 주의: `pg_advisory_xact_lock`은 함수를 감싼 트랜잭션이 끝날 때 자동 해제된다. `record_click`은 단일 문 호출이라 문 종료 시 즉시 풀린다. 대기 시간은 같은 폰트에 동시 요청이 몰릴 때만 발생하고 fire-and-forget 계약상 허용 범위다.

### 4.4 알려진 한계

- 폰트별 전역이라 서로 다른 폰트로 분산된 폭증은 B 단독으로 못 막는다 → 그건 A(IP)가 담당.
- 임계값 바로 아래로 저속 조작하면 통과 → 그것도 A(IP)가 담당. B는 극단 폭주 차단용.

## 5. A안 상세 — Kong IP 제한 (문서-설정으로 인계)

이 세션은 **prod 쓰기 금지 + dev는 Kong 없는 클라우드**라 실측 불가. 아래를 인계하고 실제 적용은 사용자가 prod 배포 트랙에서 수행한다.

### 5.1 개념

자체호스팅 Supabase의 관문 Kong에 `rate-limiting` 플러그인을 `record_click` 경로 전용 라우트에 적용. IP당 분당 30건 초과 시 429 반환.

### 5.2 kong.yml 스니펫(개념 예시 — 실물 확인 후 매칭 필요)

```yaml
# record_click 전용 라우트에 rate-limiting. 기존 rest-v1 라우트보다 경로가 구체적이라 우선 매칭됨.
services:
  - name: rest-rpc-record-click
    url: http://rest:3000/rpc/record_click   # 업스트림 주소는 prod kong.yml의 rest 서비스 정의에서 확인
    routes:
      - name: rpc-record-click
        paths: [/rest/v1/rpc/record_click]
        methods: [POST]
        strip_path: false
    plugins:
      - name: rate-limiting
        config:
          minute: 30           # IP당 분당 상한
          policy: local        # 단일 VM 인메모리 카운터(외부 Redis 불필요, 예산 0 부합)
          limit_by: ip
          fault_tolerant: true # 카운터 장애 시 요청 통과(fire-and-forget 계약 보존)
```

> 경고(M3 — 그대로 붙여넣기 금지): 위처럼 **새 service/route를 추가하면 기존 `/rest/v1` route의 플러그인(apikey 인증, CORS 등)을 상속하지 않는다.** 그대로 적용하면 `record_click` 경로가 apikey 검증을 우회하는 인증 우회가 생길 수 있다. 권장 순서:
> 1. **가능하면 기존 rest route에 `rate-limiting` 플러그인만 추가**(별도 route 신설 없이). 기존 auth/CORS가 그대로 유지된다.
> 2. 전용 route가 꼭 필요하면 기존 route에 걸린 **필수 플러그인(apikey 인증, CORS)을 전용 route에도 복제**한 뒤 rate-limiting을 얹는다.
> 어느 쪽이든 prod `kong.yml` 실물의 route/plugin 구성을 먼저 확인하고 맞춘다.

### 5.3 적용 절차(사용자 수행)

1. prod `kong.yml`에서 실제 rest 서비스 업스트림 주소-기존 라우트 구조 확인.
2. 위 스니펫을 prod 값에 맞춰 조정(업스트림 url, 경로 우선순위).
3. Kong 재기동(declarative config 리로드).
4. 검증(S2 — 429만이 아니라 실제 방어까지 확인):
   - `for i in $(seq 1 40); do curl -s -o /dev/null -w "%{http_code}\n" -X POST "$SUPABASE_URL/rest/v1/rpc/record_click" -H "apikey: $ANON_KEY" -H "Content-Type: application/json" -d '{"p_slug":"noto-sans-kr"}'; done` → 30건 근처부터 429 확인.
   - 429 발생 후 60초 경과 시 제한 해제(다시 200) 확인.
   - 같은 시간대에 다른 RPC(`get_top_fonts` 등)는 영향 없이 정상 응답하는지 확인.
   - 실제 `font_clicks` insert 수가 제한된 만큼만 늘었는지(429는 DB에 안 들어감) 대조 확인.

### 5.4 미확인 사항(적용 전 확인 필요)

- **실제 클라이언트 IP 전달(M2 — 최우선 확인)**: prod가 프록시/로드밸런서/CDN(OCI 로드밸런서, Cloudflare 등) 뒤에 있으면 Kong은 모든 요청을 **같은 IP(프록시 IP)로 볼 수 있다.** 그러면 `limit_by: ip`가 (1) 전체 사용자를 한 IP로 묶어 정상 사용자까지 429를 맞거나 (2) 반대로 제한이 무력화된다. 앞단 프록시 유무를 확인하고, 있으면 Kong이 `X-Forwarded-For`의 실제 클라이언트 IP를 신뢰하도록 real IP 설정(신뢰 프록시 화이트리스트 포함)을 맞춰야 한다. 미설정 시 `limit_by: ip`는 오작동한다.
- prod Kong 버전과 `rate-limiting` 플러그인 활성화 여부.
- Supabase 관리 요청(대시보드/스토리지 등)이 같은 경로를 공유하지 않는지(record_click 전용 경로라 영향 없을 것으로 예상하나 실물 확인).

## 6. 테스트 계획

### 6.1 B안 SQL 테스트 (`supabase/tests/click_rate_limit_test.sql` 신규)

- 경계: 같은 폰트 19건 삽입 후 20번째 → 기록됨(총 20). 21번째 호출 → 무시(총 20 유지).
- 시간창 리셋: 윈도우 밖(10초 초과 과거) 데이터는 카운트에 미포함(테스트에서 `clicked_at` 조작으로 검증).
- 미공개/미존재 slug는 여전히 무시(0007 동작 회귀 없음).
- 다른 폰트는 독립 카운트(폰트 A 상한 도달이 폰트 B 기록을 막지 않음).
- 동시성(S1): "동시 50회 호출 후에도 폰트별 상한(20)이 유지"를 검증. **한계**: 순수 SQL 테스트는 단일 세션이라 진짜 병렬을 재현하지 못한다. 따라서 (1) 함수에 `pg_advisory_xact_lock` 호출이 존재하는지 정적 확인(함수 정의 grep/pg_get_functiondef)하고, (2) 실제 동시성은 dev에서 병렬 클라이언트(예: xargs/`&`로 curl 동시 실행)로 "총 insert가 상한을 넘지 않음"을 실측한다(dev 접근 블로커 해소 후).

### 6.2 dev 실측

dev에 0008 적용 후 위 시나리오 재현. **선행 블로커**: `supabase-dev` MCP self-signed 인증서 에러로 현재 dev 접근 불가 → 로컬 psql 또는 MCP 설정 정상화 후 진행.

### 6.3 A안 검증

5.3의 curl 반복 호출로 429 확인(사용자, prod 적용 시).

## 7. 산출물 범위

| 구분 | 이 세션 | 인계(사용자/후속) |
|------|---------|-------------------|
| B DB 함수 | 마이그레이션 0008 + SQL 테스트 작성, dev 적용-실측 | — |
| A Kong | 설계-스니펫-적용 가이드 문서(본 문서 5장) | prod kong.yml 적용-재기동-429 검증 |
| 마이그레이션 재배치 | 등록폼 번호 0009 예약으로 문서 갱신 | 등록폼 구현 시 0009 사용 |

## 8. 리스크

- **dev MCP 접근 블로커**: 인증서 에러 미해결 시 dev 실측 불가 → 마이그레이션 코드 리뷰 + 로컬 검증으로 대체하거나 블로커 우선 해소.
- **A/B 방어 비대칭**: dev엔 Kong이 없어 A 미적용. dev는 B만으로 방어(설계상 수용 — dev는 실트래픽 없음).
- **임계값 오탐**: 제안값은 넉넉하나, 향후 실제 트래픽이 커지면 인기 폰트가 B 상한에 근접할 수 있음 → 상수라 조정 용이. 재검토 트리거: 특정 폰트 정상 클릭이 10초 20건에 근접하는 시점.
- **prod 미적용 상태의 배포**: prod 0007 자체가 미적용. rate limit은 0007 배포와 함께 나가야 의미. 본 설계는 배포 트랙(prod 0007 + rate limit)의 선행 준비물.

## 9. 롤백 절차 (S3 — 오탐 시 즉시 복구)

임계값 오탐으로 정상 클릭이 막히거나 Kong 설정이 다른 요청에 영향을 줄 때 되돌리는 절차.

- **B(DB 함수)**: 0008을 **0007의 `record_click` 정의로 `create or replace` 복원**하면 rate limit 이전 동작으로 즉시 되돌아간다. `create or replace` 방식이라 테이블/데이터 손실 없이 함수 본문만 교체된다. 롤백용 SQL은 0007 함수 본문을 그대로 사용(별도 down 마이그레이션 파일 또는 수동 실행). advisory lock/윈도우 체크가 사라져 방어는 없어지지만 정상 동작은 보장된다.
- **A(Kong)**: `kong.yml`에서 `rate-limiting` 플러그인 블록을 제거(또는 `enabled: false`)한 뒤 Kong 재기동(declarative config 리로드). 전용 route를 신설한 경우 route도 함께 제거해 원상 복구.
- **완화(롤백 대신)**: 오탐이 임계값 문제면 롤백 전에 상수(`c_max`/`c_window`, Kong `minute`)만 넉넉히 올리는 조정으로 먼저 대응한다.
