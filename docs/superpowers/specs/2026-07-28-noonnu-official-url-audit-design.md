# 눈누 official_url 오염 전수 검증 및 정정 설계

- 작성일: 2026-07-28
- 대상 이슈: #150(1순위), #141 + #142(2순위)
- 선행 완료: PR #149(추출 로직 수정, 커밋 `0dd2548`)
- 로드맵: #62

## 배경

#148에서 "효남 늘 화이팅" 폰트의 출처가 눈누 인스타그램으로 연결된다는 신고가 들어왔다. 조사 결과 1종이 아니라 172종 규모의 시스템적 오류였다.

원인은 `noonnu_seed.py`의 공식 URL 추출이 페이지 전체 `<a>` 태그를 훑어 조건에 맞는 첫 링크를 그대로 채택한 것이다. 필터가 `.com` 포함처럼 느슨해서, 페이지 어디에나 있는 눈누 자체 홍보 계정 링크가 제작사 링크보다 먼저 나오면 그것이 공식 출처로 굳었다.

추출 로직은 PR #149가 본문 컨테이너 한정 + 눈누 도메인 차단으로 고쳤다. **이미 저장된 데이터는 그대로다.** 이 문서는 그 데이터를 다룬다.

## 확정 사실 (prod 실측)

```
발행 폰트 1,240종 중 official_url 호스트 1위 = www.instagram.com 172종
172종 전원: source_tier=B / license_type=custom-free / license_verified=true / foundry=NULL
official_url = license_source_url = https://www.instagram.com/noonnu_official/
font_sources: provider=noonnu, source_role=reference, 172건 전부 눈누 상세 URL 보유
```

`license_source_url`은 라이선스 판정 근거로 쓰인다. 즉 172종이 **눈누 홍보 계정을 라이선스 근거로 삼아 verified 처리**된 상태다.

## 범위와 순서

| 순위 | 이슈 | 내용 | 의존 |
|---|---|---|---|
| 1 | #150 | Tier B 1,110종 전수 대조 + 오염 정정 | 없음 |
| 2 | #141 + #142 | `audit_http` 결함 5종 + 체크포인트 결함 | #142 -> #141 |

**#150은 #141/#142와 독립이다.** 코드 경로가 다르기 때문이다.

```
noonnu_seed.py:139   httpx + FontAgitSeedBot UA + robots.txt + _REQUEST_DELAY   <- #150 경로
audit_http.py        curl 기반                                                  <- #141 대상
audit_runner.py      체크포인트는 여기에만 존재                                  <- #142 대상
```

이에 따라 브라우저 User-Agent 적용 결정은 `audit_http.py`(#141)에만 해당한다. 눈누 수집기는 이미 정직한 봇 UA와 robots.txt 준수, 요청 간 지연을 갖추고 있어 변경하지 않는다.

## 설계 (#150)

### 컴포넌트 1: 대조 스캐너 (읽기 전용)

Tier B 1,110종 전부를 재수집해 PR #149의 수정된 추출기를 돌리고, 결과를 현재 DB 값과 대조한다.

938종만 표본 검증하지 않는 이유는 세 가지다. 172종도 어차피 재수집이 필요하고, 대조 코드가 하나로 끝나며, "우연히 맞았던 건"까지 같은 기준으로 걸러진다. 요청 간 1초 지연 기준 약 20분이면 끝난다.

폰트별로 네 갈래 판정을 낸다.

- `match`: 재추출 값과 DB 값이 같음
- `mismatch`: 값이 다름 (오염 후보)
- `no_container`: 본문 컨테이너를 찾지 못함 (PR #149의 fail-closed로 빈 값이 됨)
- `no_link`: 본문에 외부 제작사 링크가 없음

`mismatch`는 오염 유형을 함께 분류한다. 눈누 자체 SNS / 본문 내 무관한 외부 링크 / 다른 폰트 상세 링크 / 단축 URL.

**판정과 조치 권고를 분리한다.** 재추출 값이 DB 값과 다르다는 사실이 새 값을 정답으로 만들지 않기 때문이다. PR #149의 추출기도 본문 안에서는 여전히 첫 링크를 택하므로, 잘못된 값을 또 다른 잘못된 값으로 바꿀 수 있다. 그래서 판정과 별개로 `recommended_action`을 네 갈래로 매긴다.

| 값 | 조건 | 적용 |
|---|---|---|
| `auto_fix_safe` | 새 값이 눈누 외부 도메인이고, 제작사명(`maker`)과 도메인이 매칭되거나 앵커 텍스트가 다운로드-공식 계열 | 자동 정정 |
| `manual_review` | 새 값이 있으나 위 근거가 약함 | 사람 확인 후 결정 |
| `nullify` | `no_link` 또는 새 값이 여전히 애그리게이터-SNS 계열 | 빈 값 후보 |
| `keep` | `match`, 또는 `no_container`처럼 판단 근거 자체가 없음 | 변경 없음 |

**자동 정정은 `auto_fix_safe`에만 적용한다.** 나머지는 리포트에 남기고 사람이 판단한다.

산출물은 JSON 리포트 한 개이며 폰트별 레코드 형식을 고정한다. 구현자가 필드를 임의로 정하지 않게 하기 위해서다.

```
font_id, slug, source_url(눈누 상세),
db_official_url, db_license_source_url, db_license_verified,
new_official_url, new_maker,
classification(match|mismatch|no_container|no_link),
contamination_type(nullable), recommended_action, evidence(앵커 텍스트-매칭 근거)
```

이 단계는 DB를 건드리지 않는다.

**중단과 재개.** 1,110회 요청이 20분 이상 이어지므로 중단 대비가 필요하다. 리포트와 같은 디렉터리에 진행 상태 파일을 두고 폰트 1건 처리마다 append 방식으로 기록한다. 재시작 시 이미 기록된 `font_id`를 건너뛴다. 배치 단위가 아니라 건 단위로 기록하는 이유는 #142가 드러낸 것과 같은 누락을 반복하지 않기 위해서다.

**요청 예의.** 기존 `_REQUEST_DELAY`를 유지하되 고정 간격이 패턴으로 읽히지 않도록 지터를 섞는다. 429나 403을 받으면 대기를 늘리고, 연속으로 받으면 안전하게 중단해 상태 파일을 남긴다.

배치 위치는 기존 패턴을 따라 `__main__.py`의 서브커맨드로 붙인다(`seed`, `enrich`, `manifest build` 등과 같은 층).

**추출은 `audit_noonnu.py`에 붙인다.** 눈누 페이지 파서가 두 벌 있는데, `noonnu_seed.py`는 시드 수집용이고 `audit_noonnu.py`가 감사용이다. 후자를 택하는 이유는 세 가지다.

- 정정을 manifest로 하려면 증거(snapshot)와 검수 후보(finding)가 필요한데, 감사 파서만 `evidence_locations`와 `_selector_path`로 근거 위치를 남긴다
- `NoonnuFontSnapshot`에 `global_social_links` 필드가 이미 선언돼 있다. 다만 채우는 코드가 없어 항상 빈 리스트다. 눈누 전역 SNS를 분리하려던 자리가 비어 있었고, 그것이 이번 오염을 걸러내지 못한 이유이기도 하다
- 감사 파서에는 `official_url` 개념 자체가 없어, 추가하면 두 파서의 역할이 겹치지 않고 나뉜다

PR #149가 검증한 접근(본문 컨테이너 한정 + 눈누 도메인 차단)을 감사 파서의 `_detail_root`를 써서 구현한다. 로직을 베끼는 것이 아니라 같은 원칙을 감사 파서 구조에 맞춰 적용하는 것이다. 대조와 판정은 별도 모듈로 새로 만든다.

### 컴포넌트 2: manifest 허용 필드 확장

`official_url`은 현재 manifest RPC로 변경할 수 없다.

```
0025_manifest_null_value_compare.sql:27-35  v_allowed
  license_source_url  포함
  official_url        없음
```

`audit_store.py`가 "그 변경은 이후 manifest RPC 한 곳에서만 수행한다"고 규정한 구조이므로, 직접 UPDATE로 우회하지 않고 마이그레이션 `0026`으로 `official_url`을 `v_allowed`에 추가한다. 감사 추적(before/after, 되돌리기)을 그대로 얻기 위해서다.

주의할 점이 있다. `official_url`은 `v_allowed` 밖에서도 세 곳에 등장한다.

```
0018:266  perform ... array['slug','name_en','name_ko','foundry','source_tier','official_url','status'], 'entry.current'
0018:291  or to_jsonb(v_existing.official_url) is distinct from v_entry#>'{current,official_url}'
0018:493  ... array['foundry','name_en','name_ko','official_url','slug','source_tier','updated_at']
```

같은 필드가 낙관적 잠금(변경 전 값 대조)의 기준이자 변경 대상이 된다. 따라서 **`0026`의 범위는 `v_allowed`에 한 줄 추가하는 것으로 끝나지 않을 수 있다.** 위 세 지점이 변경 후 값과 충돌하지 않는지 먼저 확인하고, 필요하면 함께 손본다. 이 확인이 끝나기 전에는 마이그레이션을 작성하지 않는다.

`license_source_url`과 `license_verified`는 확인 결과 이미 `v_allowed`에 있다(`0025:28`, `0025:32`). 추가가 필요한 것은 `official_url` 하나다.

적용 순서는 `0021 -> 0022 -> 0023 -> 0024 -> 0025 -> 0026`이다. `0025`가 `0024`의 함수를 다시 만들므로 순서를 건너뛰면 실패한다(#134 기록).

### 컴포넌트 3: 정정 적용

정정 대상 필드는 **`official_url`과 `license_source_url` 둘 다**이다. 172종은 두 필드가 같은 오염된 값을 갖고 있으므로 한쪽만 고치면 라이선스 근거가 잘못된 채로 남는다.

`recommended_action`이 `auto_fix_safe`인 폰트에 대해 manifest를 만들어 dev에 먼저 적용하고, 쓰기 후 재조회로 실측을 남긴다. 되돌리기용 역방향 manifest를 함께 만들어 보관한다.

**`license_verified` 정책표.** 라이선스 근거 URL이 잘못된 상태로 verified였으므로 일괄 유지는 불가하다. 새 근거의 성격에 따라 나눈다.

| 새 `license_source_url` | `license_verified` |
|---|---|
| 제작사 공식 도메인이고 라이선스 문구 확인됨 | `true` 유지 |
| 제작사 공식 도메인이나 라이선스 문구 미확인 | `false` (근거 부족) |
| 확보 실패(`nullify`, `no_link`) | `false` |
| `manual_review` | 변경하지 않고 사람 판단까지 보류 |

**prod 승인 패키지.** prod 적용 전에 쿼리 전문만 보여주지 않고 아래를 한 묶음으로 제시한 뒤 승인받는다. 172종 이상의 발행 데이터를 바꾸기 때문이다.

- 변경 건수 총계와 필드별 건수 (`official_url` / `license_source_url` / `license_verified`)
- 변경 전후 샘플 10건
- 영향받는 전체 slug 목록
- 역방향 manifest 경로
- 적용 후 실행할 검증 쿼리

이 패키지는 dev 적용과 실측이 끝난 뒤에 만든다.

### 대조 리포트 이후로 미루는 결정

두 가지는 지금 정하지 않는다. 지금 정하면 표본 1건 근거가 되기 때문이다(#150이 지적한 문제).

- 본문에 제작사 링크가 아예 없는 폰트의 `official_url`을 NULL로 둘지
- 다중 링크 선택 정책을 "본문 첫 링크"에서 앵커 텍스트 근접 매칭이나 제작사명-도메인 매칭으로 바꿀지

두 결정 모두 대조 리포트의 실제 분포(`no_link`, `mismatch` 건수와 유형)를 본 뒤 내린다.

### #150 완료 기준

아래를 모두 충족하면 #150을 닫는다.

- Tier B 1,110종 전부에 대해 판정과 `recommended_action`이 기록된 리포트가 있다
- `official_url`이 눈누 도메인이나 눈누 SNS를 가리키는 발행 폰트가 prod에 0종이다 (검증 쿼리로 실측)
- `license_verified=true`이면서 `license_source_url`이 애그리게이터를 가리키는 폰트가 0종이다
- `manual_review`로 남은 건수와 사유가 이슈에 기록됐다
- 역방향 manifest가 보관돼 있다

`no_container` 비율이 전체의 5%를 넘으면 눈누 페이지 구조 가정이 틀린 것이므로, 정정을 진행하지 않고 폴백 선택자 설계를 먼저 다시 본다.

## 설계 (#141 + #142)

이 둘은 #150과 **별도 PR로 분리한다.** #150은 데이터 정정이고 #141/#142는 감사 파이프라인 수정이라, 함께 묶으면 리뷰와 되돌리기 단위가 엉킨다.

### #142 체크포인트

`audit_runner.py:2042-2043`이 배치 전체를 완료로 기록한다.

```python
for target in batch:
    completed_font_ids.add(target.font_id)
```

실패 정보는 `errors` 리스트에 `"{slug}: {예외명}"` 문자열로만 남아 font_id로 되돌릴 수 없다. 재개 시 `remaining` 계산에서 실패 폰트가 걸러져 영구 누락된다.

문자열을 파싱하는 대신 `AuditReport`에 `failed_font_ids` 필드를 추가해 실패를 구조화해 올려보내고, 체크포인트는 `batch - failed`만 완료로 기록한다. slug에 콜론이 섞이면 파싱이 깨지므로 문자열 방식은 택하지 않는다.

### #141 fetcher

`audit_http.py`의 결함 5종을 수정한다. 브라우저 User-Agent(사용자 승인), `--compressed` 추가, curl exit 56 매핑, DNS 응답 중 공개 주소만 골라 쓰고 전부 비공개일 때만 거부, URL 퍼센트 인코딩.

브라우저 UA는 봇 게이트 우회에 해당하므로 robots.txt 확인과 요청 간격 제한을 함께 넣어 부하와 차단 위험을 낮춘다. 다만 `audit_http.py`는 curl을 subprocess로 부르는 구조라 이 둘을 curl 자체로는 처리할 수 없다. **호출하는 파이썬 쪽에 호스트 단위로 붙인다.** robots.txt는 호스트별로 한 번 받아 캐시해 판정하고, 요청 간격도 호스트별로 관리한다. 구현 위치와 캐시 수명은 계획 단계에서 확정한다.

여기에 **본문 sanity 게이트**를 더한다. `_scheduled_status`(`audit_runner.py:1169-1179`)가 HTTP 200이면 verified를 주기 때문에, 200으로 내려오는 오류 페이지도 통과한다. 172종이 verified가 된 경로와 같은 뿌리다.

판정 기준은 최소한으로 둔다. 과하게 잡으면 정상 페이지를 떨어뜨린다.

- `Content-Type`이 HTML 계열인가
- 본문 길이가 최소치 이상인가
- 최종 URL의 호스트가 요청 호스트와 같은 계열인가 (오류 페이지로 튕겨나갔는지)
- 제목이나 본문에 오류 문구(찾을 수 없음, 404, Not Found 계열)가 있는가

하나라도 걸리면 verified를 주지 않고 `needs_review`로 내린다.

### 순서

#142를 먼저 고친다. #141의 수정 효과를 22종 재크롤로 검증하려면 실패 항목이 재개 대상에 남아야 하기 때문이다.

## 테스트

- #150 스캐너: 판정 네 갈래 픽스처 케이스. 눈누 자체 SNS가 본문에 있는 경우와 푸터에 있는 경우를 구분하는지. `recommended_action`이 근거 강도에 따라 `auto_fix_safe`와 `manual_review`로 갈리는지
- #150 재개: 중간에 끊긴 상태 파일로 다시 시작했을 때 이미 처리한 폰트를 다시 요청하지 않는지
- `0026` 마이그레이션: `official_url` 변경이 통과하는 케이스, `entry.current` 대조가 변경 전 값을 보는지 확인하는 pgTAP
- #142: 배치 중 일부가 실패했을 때 실패 폰트만 재개 대상에 남는지
- #141: 결함 5종별 최소 케이스. 본문 sanity 게이트는 200 오류 페이지를 거르는지와 정상 페이지를 떨어뜨리지 않는지 양방향으로 확인 (172종 오염과 같은 뿌리라 축소하지 않는다)

데이터 변경은 쓰기 후 재조회 실측을 보고에 남긴다.

## 리스크

- **재추출 값도 정답이 아닐 수 있다**: 이 설계의 가장 약한 고리다. PR #149의 추출기는 본문 범위를 좁혔을 뿐 그 안에서는 여전히 첫 링크를 택한다. `recommended_action`으로 자동 정정 범위를 좁혀 대응하지만, `auto_fix_safe` 판정 자체가 틀릴 여지는 남는다. dev 적용 후 샘플 육안 확인을 거친다.
- **눈누 페이지 구조 가정**: `div.noon-page-content`가 모든 폰트 페이지에 있다는 근거는 아직 표본 1건이다. 전수 스캔의 `no_container` 건수가 이 가정을 실측으로 검증한다. 5%를 넘으면 정정을 멈추고 폴백 선택자 설계를 다시 본다.
- **1,110회 요청 부하**: 지터를 섞은 지연과 동시 요청 금지, 429/403 백오프와 안전 중단. 진행 상태는 건 단위로 파일에 남긴다.
- **`official_url` 이중 역할**: 대조 키이자 변경 대상이 되는 구조. `0018`의 세 지점 확인과 pgTAP 검증 전에는 마이그레이션을 쓰지도, prod에 적용하지도 않는다.
- **prod 쓰기**: 172종 이상의 발행 데이터를 바꾼다. 승인 패키지 제시와 역방향 manifest 보관을 전제로만 진행한다.

## 리뷰 이력

- 2026-07-28 듀얼 리뷰(Codex gpt-5.5 xhigh + agy Gemini 3.5 Flash High): 두 모델 모두 8/10. Must 7건을 이 문서에 반영했다. 리포트: `docs/review/review-result-dual-20260728-230206.md`
- 반려한 지적 2건: `license_source_url`과 `license_verified`를 `v_allowed`에 추가하라는 agy 지적은 코드 확인 결과 이미 포함돼 있어 반영하지 않았다(`0025:28`, `0025:32`).
