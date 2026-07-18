# prod 폰트 데이터 전수 조사·보정 설계

> 작성일: 2026-07-18
> 상태: 사용자 설계 승인, 자체 적대적 리뷰·Claude 외부 리뷰 보강
> 범위: prod 1,240종 데이터 전수 조사, 적재 파이프라인 재발 방지, 폰트 상세 라이선스 표시 개선

## 1. 목적

prod 폰트 데이터를 두 단계로 전수 조사한다.

1. 다운로드 링크·제작사·라이선스처럼 잘못 안내하면 피해가 큰 정보를 먼저 보정한다.
2. 폰트명·분류·굵기·스타일 등 나머지 정보를 보정한다.

일회성 데이터 수정을 넘어서, 수집 원본과 검증 결과를 분리하고 링크·라이선스를 주기적으로 재검사하는 파이프라인을 만든다.

## 2. 확인된 문제와 원인

2026-07-18 prod 읽기 전용 조사 기준:

- 전체 published 폰트는 1,240종(Tier A 130, Tier B 1,110)이다.
- Tier B 172종의 다운로드 주소와 라이선스 출처가 눈누 공식 인스타그램으로 저장되어 있다.
- `흰꼬리수리`는 눈누에서 제작사 네이버, 다운로드 주소 `clova.ai`로 안내하지만 prod에는 눈누 인스타그램이 저장되어 있다.
- prod 1,240종 모두 `foundry`가 비어 있다.
- 재배포 권한은 DB에서 모두 미확인이지만 웹 변환 코드가 전부 `가능`으로 고정 표시한다.
- 라이선스 원문 또는 사용자용 요약 본문을 저장할 전용 구조가 없다.
- `횡성한우체`의 저장 주소는 눈누와 prod가 동일하지만 현재 4xx 응답으로 접근할 수 없다.

원인은 네 가지다.

1. 눈누 페이지의 모든 외부 링크 중 일부 도메인 문자열과 일치하는 첫 주소를 공식 주소로 선택했다. `clova.ai`는 허용 목록에서 빠지고 하단 SNS는 선택될 수 있었다.
2. 시드의 제작사 값을 임포터가 `fonts.foundry`에 저장하지 않았다.
3. `official_url` 하나에 제작사 홈페이지·다운로드·라이선스 출처 역할을 섞었다.
4. 적재 시점 이후 링크·라이선스를 재검사하는 작업이 없었다.

## 3. 확정된 운영 결정

| 항목 | 결정 |
|---|---|
| 현재 prod | 전수 보정이 끝날 때까지 현 상태 유지 |
| 출처 우선순위 | 제작사 공식 페이지 → 한국저작권위원회·공유마당 등 공공기관 → 눈누 참고 |
| 출처 미확인 | 페이지 유지, 다운로드 버튼 제거, `라이선스 재확인 필요` 표시 |
| 라이선스 공개 | 우리 문장으로 핵심 요약 공개 |
| 라이선스 원문 | 내부 증거로 저장하고 사용자에게 원문 링크 제공 |
| 링크 분리 | 다운로드 페이지와 라이선스 원문 주소 별도 저장 |
| 반영 방식 | 확실한 항목만 dev 자동 보정, 애매한 항목 검수, 사용자 승인 후 prod 일괄 반영 |
| 조사 순서 | 1단계 법적·다운로드 정보, 2단계 일반 메타데이터 |
| 재검사 | 다운로드 링크 매주, 라이선스 분기마다 |

## 4. 범위

### 포함

- prod 1,240종 전체
- 제작사와 출처 식별
- 제작사 공식 페이지, 다운로드 페이지, 라이선스 원문 페이지
- 라이선스 6개 항목과 사용자용 요약
- 눈누의 폰트 관련 원본·구조화 데이터
- 폰트명·영문명·분류·굵기·이탤릭 등 스타일
- 자동 판정, 검수 큐, 변경 전후 보고서, 되돌리기 자료
- 폰트 상세 화면의 라이선스·다운로드 표시
- 주기적 링크·라이선스 재검사

### 제외

- 폰트 목록 화면의 필터 추가·고도화
- 눈누 사용자 계정·질문·댓글
- 광고·관련 폰트·사이트 메뉴·추적 정보
- 출처가 불확실한 값을 추정하여 공개하는 행위
- 사용자의 최종 승인 없는 prod 쓰기

## 5. 데이터 구조

### 5.1 공개 현재값: `fonts`

기존 컬럼은 바로 삭제하지 않고 새 컬럼을 추가해 단계적으로 전환한다.

| 컬럼 | 용도 |
|---|---|
| `official_url` | 기존 호환용 주소. 의미를 바꾸지 않고 legacy로 동결 |
| `foundry_url` | 제작사 공식 홈페이지 |
| `download_url` | 다운로드 안내 페이지 |
| `license_source_url` | 라이선스 원문 페이지 |
| `foundry` | 제작사 이름 |
| `license_summary` | FontAgit 문장으로 작성한 공개 요약 |
| `download_source_kind` | `official` / `public` / null |
| `license_source_kind` | `official` / `public` / null |
| `download_evidence_id` | 선택한 내부 근거 스냅샷 ID |
| `license_evidence_id` | 선택한 내부 근거 스냅샷 ID |
| `download_status` | `pending` / `verified` / `broken` / `needs_review` |
| `license_status` | `pending` / `verified` / `needs_review` |
| `download_checked_at` | 다운로드 링크 마지막 확인일 |
| `license_checked_at` | 라이선스 마지막 확인일 |
| `allow_commercial` | `allowed` / `conditional` / `denied` / null |
| `allow_modify` | `allowed` / `conditional` / `denied` / null |
| `allow_redistribute` | `allowed` / `conditional` / `denied` / null |
| `allow_embedding` | `allowed` / `conditional` / `denied` / null |
| `allow_font_sale` | `allowed` / `conditional` / `denied` / null |
| `attribution_requirement` | `required` / `recommended` / `not_required` / null |

`null`은 추정하지 않은 `미확인`으로 화면에 표시한다. 기존 `is_commercial_free`와 `license_verified`는 호환을 위해 유지하되 신규 파이프라인이 함께 갱신한다.

- `license_status='verified'`이면 `license_verified=true`, `license_source_url`, `license_checked_at`, 허용된 `license_source_kind`, `license_evidence_id`가 모두 있어야 한다.
- `license_status<>'verified'`이면 웹은 검증된 라이선스 문구를 표시하지 않는다.
- `allow_commercial='allowed'`이면 `is_commercial_free=true`, `conditional`·`denied`이면 false로 dual-write한다. null은 기존 boolean을 새 판정 근거로 사용하지 않는다.
- `download_status='verified'`이면 `download_url`, `download_checked_at`, 허용된 `download_source_kind`, `download_evidence_id`가 모두 있어야 한다.
- 위 규칙은 backfill 완료 후 DB CHECK로 강제한다. backfill 전에는 새 상태를 기본 `pending`으로 두고 새 UI를 배포하지 않는다.

`official_url`은 현재 웹과 파이프라인에서 다운로드 CTA로 사용하므로 의미를 제작사 홈페이지로 바꾸지 않는다. 새 UI가 `foundry_url`·`download_url`을 사용한 뒤에도 한 릴리스 이상 legacy 읽기용으로 유지하고, 호출처 전수 확인 전에는 삭제하지 않는다.

전환 전 `official_url`, `is_commercial_free`, `license_verified`를 읽거나 쓰는 웹 mapper, 검색·클릭 RPC, 컬렉션 조회, uploader, 제출·검수 경로를 전수 확인한다. 새 값과 기존 값의 dual-read·dual-write 기간을 거친 뒤 소비자가 0개임을 확인해야 legacy 의미를 제거할 수 있다.

검증 필드의 단일 writer는 전용 audit apply RPC다. 기존 눈누 import·enrich와 일반 uploader는 원본 snapshot·후보 finding까지만 만들며 `download_url`, `license_source_url`, 라이선스 6개 항목, 검증 상태와 근거 ID를 직접 확정하지 못한다. 사용자 폰트 제출 주소도 검증값이 아니라 후보로만 취급한다.

### 5.2 안정 출처 식별: `font_sources`

dev와 prod의 UUID가 달라도 같은 폰트를 찾을 수 있도록 환경 공통 출처 키를 둔다.

- `font_id`
- `provider`(예: `google-fonts`, `noonnu`)
- `provider_record_id`(예: Google family key, 눈누 페이지 번호)
- `source_role`(`primary` / `reference`)
- `source_url`
- `first_seen_at`, `last_seen_at`, `status`

`(provider, provider_record_id)`는 환경 안에서 unique다. 한 폰트는 여러 출처를 가질 수 있지만 하나의 제공자 레코드가 여러 폰트에 연결되면 자동 보정을 중단한다. prod manifest는 UUID나 slug가 아니라 이 안정 출처 키로 대상을 찾고, 현재 이름·slug·기존 URL과 현재 제작사 값(공란 포함)을 exact precondition으로 검사한다.

기존 레코드에 안정 출처 키를 연결하지 못하거나 Tier A·B 중복 가능성이 있으면 자동 병합하지 않고 검수 대상으로 보낸다.

#### 1회성 안정키 bootstrap

안정키가 아직 없는 prod 행은 다음 버전 고정 자료에서만 연결한다.

- Tier A: 전수 조사 실행에 사용한 Google Fonts upstream snapshot의 family key·name_en·slug·기존 Google 주소
- Tier B: 최초 적재에 사용한 눈누 seed의 page ID·source_page·name_ko·slug·당시 official_url과 dev `license_proposals.source_url`

Tier A는 `source_tier + name_en + slug + 기존 Google 주소`, Tier B는 `source_tier + slug + 정규화 name_ko + 당시 official_url`이 모두 정확히 일치하고 후보가 1개일 때만 자동 연결한다. prod `foundry`는 현재 전량 공란이므로 최초 bootstrap 조건에 사용하지 않고 안정키 연결 후 별도 검증값으로 채운다.

과거 주소가 바뀌었거나 후보가 0개·2개 이상이면 자동 연결하지 않는다. bootstrap 결과는 public 값을 수정하지 않는 별도 manifest로 만들고, 사용자에게 자동 연결·미연결·충돌 개수를 보고한 뒤 prod에 원자적으로 적용한다. 이후 모든 환경 간 반영은 이 안정키를 사용한다.

### 5.3 수집 실행: `font_audit_runs`

한 번의 전수 조사 단위를 기록한다.

- 실행 ID와 단계
- 대상 환경과 대상 개수
- 시작·종료 시각
- 성공·자동 보정·검수·실패 개수
- 파서 버전과 실행 상태
- dry-run 여부
- 기준선 exact count, 기준선 해시, manifest 해시

### 5.4 내부 원본: `font_source_snapshots`

출처별 원문을 append-only로 저장한다. 이전 원문을 덮어쓰지 않는다.

- 실행 ID, 폰트 ID
- 제공자와 제공자 레코드 ID(예: `noonnu:854`)
- 출처 종류(`official` / `public` / `noonnu`)
- 자료 종류(`download` / `license` / `metadata`)
- 요청 주소, 최종 주소, HTTP 상태
- 폰트 관련 원문 HTML·텍스트와 구조화 추출값
- 원본 해시와 정규화한 폰트·라이선스 본문 해시
- 구조화 필드별 근거 문장 위치와 추출 규칙 ID
- 수집 시각과 파서 버전

서비스 역할만 접근할 수 있도록 RLS를 잠근다. 원문을 공개 API에 노출하거나 웹 화면에서 직접 HTML로 렌더링하지 않는다.

`download_evidence_id`와 `license_evidence_id`는 `font_source_snapshots.id`를 `on delete restrict`로 참조한다. audit apply RPC는 evidence의 font ID, provider, source kind, document kind가 갱신 필드와 일치하는지 다시 검사한다.

동일한 출처의 정규화 본문 해시가 바뀌지 않으면 원문을 다시 저장하지 않고 이전 스냅샷을 참조한다. 동적 배너·조회수·공백 변경은 정규화 해시에서 제외한다. 해시가 바뀐 경우에만 새 스냅샷을 추가해 변경 이력을 보존한다.

HTML·텍스트 응답은 정해진 최대 크기까지만 저장한다. PDF·폰트 바이너리는 DB에 넣지 않고 주소·파일 해시·추출한 폰트 관련 텍스트만 보관한다.

### 5.5 검수 항목: `font_audit_findings`

- 실행 ID, 폰트 ID, 대상 필드
- 현재값과 제안값
- 근거 출처와 신뢰 단계
- 자동 보정 가능 여부
- 검수 사유
- `proposed` / `approved` / `rejected` / `applied`

`(run_id, font_id, field_name)`을 unique로 두어 재실행 중복을 막는다. 허용 상태 전이는 `proposed → approved|rejected → applied`이며 applied 결과를 다시 바꾸려면 새 finding을 만든다.

기존 `license_proposals`는 즉시 삭제하지 않는다. 새 구조로 필요한 증거를 옮긴 뒤 호환 여부를 확인한다.

`font_sources`, `font_audit_runs`, `font_source_snapshots`, `font_audit_findings`는 모두 RLS를 활성화하고 공개 읽기·쓰기 정책을 만들지 않는다. 공개 화면에 필요한 출처 종류는 검증 후 `fonts`에 복제한다.

## 6. 데이터 수집 계층

### 6.1 눈누 원본 보관층

눈누에서 폰트와 직접 관련된 정보를 먼저 수집한다.

- 폰트명·영문명·제작사
- 분류·태그·가격
- 다운로드 주소
- 라이선스 본문·허용표
- 웹폰트 CSS와 파일 주소
- 굵기·스타일
- 페이지 번호와 수집 시각
- 그 밖의 폰트 관련 구조화 정보

robots.txt, 식별 가능한 User-Agent, 요청 간격, 재시도 간격을 지킨다. 같은 실행에서 같은 페이지를 중복 요청하지 않는다.

전수 수집 전 눈누의 현재 robots.txt와 관련 이용 조건을 증거로 남기고, 허용된 요청·내부 저장 범위를 기록한다. 원문 HTML·본문의 장기 저장 허용 여부가 불명확하면 승인 전까지 원문을 저장하지 않고 폰트 관련 구조화 값, 근거 위치, 원본 해시, 출처 URL만 저장한다. 수집 가능 여부와 원문 보관 가능 여부를 따로 판정한다.

### 6.2 눈누 분석 데이터층

페이지 전체의 첫 외부 링크를 선택하지 않는다. `다운로드 페이지로 이동`처럼 의미가 명확한 요소를 우선 파싱한다. 하단 SNS·광고·메뉴·관련 폰트 링크는 후보에서 제외한다.

눈누 값은 공식값이 아니라 후보와 비교 근거다. 눈누 원문만으로 공개 데이터를 자동 확정하지 않는다.

### 6.3 FontAgit 검증 데이터층

제작사 공식 출처를 먼저 찾고, 없으면 허용된 공공기관 출처를 사용한다. 폰트명·제작사·페이지 내용이 대상 폰트와 일치해야 한다.

자동 후보는 다음 네 곳에서만 만든다.

1. 눈누에서 의미가 명확한 다운로드·라이선스 링크
2. 기존 DB 주소
3. 사람이 승인한 제작사 이름↔공식 도메인 레지스트리
4. 한국저작권위원회·공유마당 등 승인된 공공기관 도메인 레지스트리

일반 검색 결과와 임의 민간 사이트는 자동 확정 근거로 사용하지 않고 검수 후보로만 남긴다. 공식·공공기관 도메인 레지스트리는 코드로 버전 관리하며 서브도메인·리다이렉트 허용 규칙을 명시한다.

레지스트리 각 항목에는 정규화 제작사명, 허용 도메인, 허용 역할(`foundry` / `download` / `license`), 공식·공공기관 구분, 승인자·승인일, 근거 스냅샷 ID를 저장한다. 검색으로 새 도메인을 발견해도 `discovery` 후보일 뿐이며, 근거 검수와 승인을 거쳐 레지스트리에 들어오기 전에는 `verified` 판정에 사용할 수 없다.

안정적인 연결키는 다음을 함께 사용한다.

- 환경별 DB 폰트 ID
- `font_sources`의 제공자와 제공자 레코드 ID
- 정규화한 폰트명
- 제작사

slug 단독 일치는 자동 확정 근거로 사용하지 않는다.

## 7. 1단계: 법적·다운로드 정보 조사

1. prod 1,240종을 읽기 전용 스냅샷으로 고정하고 안정 출처 키를 연결한다.
2. 눈누 폰트 관련 정보를 전량 수집해 내부 원본과 분석값으로 저장한다.
3. 제작사 공식 출처를 찾고 공공기관 출처를 대체 후보로 찾는다.
4. 제작사·폰트명·페이지 의미가 일치하는지 검사한다.
5. 제작사 홈페이지·다운로드·라이선스 주소를 분리한다.
6. 라이선스 원문을 저장하고 6개 항목과 공개 요약을 만든다.
7. 높은 신뢰 결과만 dev에 자동 보정한다.
8. 충돌·누락·차단은 검수 항목으로 만든다.

### 링크 판정

- 최초 상태는 `pending`이다.
- 첫 `404`·`410`: `needs_review`로 기록하고 다운로드 버튼 상태를 자동 변경하지 않음
- 최초 확인에서 24시간 이상 지난 독립 실행도 `404`·`410`: `broken`
- `400`·`401`·`403`·`429`: 봇 차단 가능성이 있어 `needs_review`
- `5xx`·타임아웃: 일시 장애로 보고 재시도 후에도 실패하면 `needs_review`
- `2xx`: 폰트명·제작사·다운로드 또는 라이선스 의미까지 확인
- 다른 도메인·홈페이지 첫 화면으로 이동: 자동 확정하지 않고 `needs_review`

외부 주소는 `http`·`https`만 허용한다. localhost, 사설 IP, link-local 주소와 해당 주소로 향하는 리다이렉트는 요청하지 않는다. 최초 요청과 모든 리다이렉트 단계에서 DNS 결과를 다시 검사한다. 응답 크기와 콘텐츠 타입에도 상한을 두어 내부망 접근과 과도한 다운로드를 막는다.

단순 DNS 사전 검사만으로는 DNS rebinding을 막을 수 없다. HTTP 연결은 검사에서 허용한 IP에만 고정하되 원래 hostname의 TLS SNI·인증서 검증을 유지한다. 사용 라이브러리가 이를 보장하지 못하면 크롤러를 별도 네트워크 격리 실행기로 옮기고 사설·link-local·클라우드 metadata 대역으로 나가는 통신을 차단한다.

링크 검사는 HEAD를 참고할 수 있지만 최종 판정은 제한된 GET으로 수행한다. HEAD를 지원하지 않는 정상 사이트를 broken으로 오판하지 않는다.

`횡성한우체`처럼 브라우저와 자동 요청의 결과가 다를 수 있으므로 단일 상태 코드만으로 다운로드 버튼을 제거하지 않는다.

### 자동 보정 조건

다음을 모두 만족해야 한다.

- 허용된 공식 또는 공공기관 출처
- 폰트명과 제작사 일치
- 링크와 페이지 역할 일치
- 기존 검증 출처와 충돌 없음
- 라이선스 원문 근거 존재
- 제안값과 판정 사유를 재현 가능

하나라도 부족하면 검수 대상으로 보낸다.

공개 요약은 검증된 구조화 값과 핵심 제한 문구를 이용한 결정론적 템플릿으로 만든다. LLM이 원문에 없는 조건을 추가하거나 완화하지 않도록 자동 자유서술 생성을 사용하지 않는다.

### 라이선스 판정 신뢰 규칙

6개 라이선스 항목을 자동으로 `verified` 처리할 수 있는 경우는 다음뿐이다.

1. 버전이 고정된 표준 라이선스 레지스트리(OFL·Apache 등)와 공식·공공기관 원문이 정확히 일치한다.
2. 사람이 승인한 제작사·공공기관별 파싱 규칙의 selector, 템플릿 버전, 문서 fingerprint가 모두 일치한다.
3. 사람이 원문과 필드별 근거 위치를 직접 확인해 승인한다.

각 필드는 원문 근거 위치와 파싱 규칙 ID를 가진다. 공식 원문에 해당 조건이 실제로 적혀 있지 않으면 추정하지 않고 `null`로 둔다. 맞춤형 문구, 새 템플릿, 누락·충돌, LLM 추출 결과는 항상 `needs_review`이며 LLM 결과만으로 `verified`를 만들 수 없다.

### 전수 조사 시작 기준

전체 1,240종 전에 제작사·도메인·출처 유형이 고르게 섞인 50종 파일럿을 실행한다. `흰꼬리수리`와 `횡성한우체`를 반드시 포함한다.

- 50종 모두 다운로드는 `verified` / `needs_review` / `broken`, 라이선스는 `verified` / `needs_review` 중 하나로 분류되어야 한다. `pending`이 남으면 파일럿 미완료다.
- 파일럿의 `needs_review`가 10%를 넘으면 대량 수동 검수를 시작하지 않는다. 제작사·문서 템플릿별로 묶어 승인 가능한 결정론적 규칙을 보강한 뒤 파일럿을 다시 실행한다.
- 전체 조사에는 임의의 verified 최소 비율을 두지 않는다. 대신 100% 상태 분류와 미해결 건수·사유 공개를 요구하고, prod 반영 전 사용자가 미해결 건수를 명시적으로 승인한다.

## 8. 2단계: 일반 메타데이터 조사

- 폰트명·영문명
- 제작사
- 분류와 태그
- 굵기
- 이탤릭 등 스타일
- 중복 폰트와 이름 충돌

가능하면 공식 배포 폰트 파일을 `fontTools`로 읽어 굵기·스타일을 확인한다. 페이지 설명과 파일 정보가 충돌하면 파일을 자동 변경 근거로 쓰지 않고 검수 대상으로 보낸다.

## 9. 폰트 상세 화면

목록 필터와 카드는 변경하지 않는다.

상세 화면은 DB의 실제 값을 사용한다.

- 제작사와 출처 종류
- 제작사 공식 홈페이지(`foundry_url`)
- FontAgit 라이선스 요약
- 상업 사용·수정·재배포·웹폰트·폰트 파일 판매·출처 표기
- 마지막 확인일
- 다운로드 페이지
- 라이선스 원문 보기

고정된 `웹폰트 가능`, `재배포 가능` 값은 제거한다. 다운로드 CTA는 `download_status='verified'`인 `download_url`만 사용하며 legacy `official_url`로 자동 fallback하지 않는다.

공식·공공기관 출처를 확인하지 못하면:

- 페이지와 미리보기 유지
- 다운로드 버튼 제거
- 확인되지 않은 라이선스 단정 제거
- `라이선스 재확인 필요` 표시
- 신고 기능 유지

## 10. 자동 재검사

저장소에 예약 실행 구조가 없으므로 GitHub Actions 예약 작업을 추가한다.

- 매주: prod 공개 데이터의 다운로드 링크 검사
- 분기마다: 라이선스 원문 내용과 해시 검사
- 예약 작업은 prod·dev 쓰기 키를 갖지 않고 prod 공개 읽기 키만 사용한다.
- 예약 작업은 상태·최종 주소·내용 해시만 비공개 실행 산출물에 기록하며 원문 전체를 남기지 않는다.
- 원문과 상세 결과의 dev 저장은 사람이 실행하는 인증된 import 단계에서만 수행한다.
- 예약 산출물을 사람이 dev로 import할 때 변경·오류를 검수 항목으로 만들며 prod를 자동 수정하지 않는다.

키와 토큰은 환경 변수 또는 GitHub Secrets로만 주입하고 로그·산출물·오류 메시지에 출력하지 않는다. 예약 산출물은 짧은 보존 기간을 사용하고 시크릿이 없다는 검사를 거친다.

예약 산출물에는 스키마 버전과 파일 해시를 넣는다. dev import는 예상 스키마와 해시가 맞는 산출물만 받고, 중복 import는 같은 run ID로 거부한다.

각 링크 관찰값은 `normalized_url`, `observed_at`, HTTP 상태, 최종 주소, 내용 해시를 가진다. dev import는 같은 정규화 주소의 이전 관찰 스냅샷과 연결한다. 서로 다른 실행에서 24시간 이상 떨어진 두 번의 `404`·`410`이 확인될 때만 `broken` 후보를 만든다. 산출물이 import되지 않았거나 이전 관찰값과 연결되지 않으면 `needs_review`를 유지하고 절대 `broken`으로 올리지 않는다. 최초 전수 조사도 24시간 뒤 두 번째 확인 실행을 완료해야 한다.

예약 실행이 대상 0건, 빈 산출물, 처리하지 못한 오류로 끝나면 성공으로 기록하지 않고 non-zero로 실패한다. GitHub Actions 실패 알림과 실행 요약에 대상·성공·오류 개수를 남긴다.

## 11. 테스트 전략

복잡한 핵심 서비스만 테스트한다. 단순 UI 컴포넌트, 값 전달 래퍼, 단순 CRUD에는 새 테스트를 만들지 않는다.

각 핵심 기능은 정상 사례 1개와 치명적 예외 1~2개, 최대 3개로 제한한다.

- 다운로드 링크 선택: 의미 있는 다운로드 링크가 하단 SNS보다 우선됨
- 링크 판정: 반복된 404·410만 broken, 차단·불일치는 needs_review
- 라이선스 파싱: 6개 항목 정상 추출, 누락·충돌은 자동 보정 금지
- 출처 병합: 공식 → 공공기관 → 눈누 참고 순서 유지
- 멱등성: 동일 스냅샷 재실행 시 중복·추가 변경 없음
- manifest 적용: 모든 precondition 일치 시 전량 적용, 한 행 충돌 시 0건 적용
- 되돌리기: 정방향 manifest 적용 후 역방향 manifest를 적용하면 대상 필드가 byte-for-byte로 원복됨
- SSRF: 공개 주소는 성공하고 private·link-local·metadata IP 및 해당 주소로의 리다이렉트는 차단됨

라이브 네트워크 대신 저장된 HTML·응답 픽스처로 핵심 로직을 검증한다. 실제 링크 전수 검사는 별도의 조사 실행으로 검증한다.

## 12. prod 반영과 되돌리기

1. prod 1,240종의 변경 대상 필드와 `updated_at`을 백업한다.
2. 변경 전후 manifest와 출처 근거 보고서를 생성하고 SHA-256 해시를 고정한다.
3. dev에 additive 컬럼·감사 테이블 마이그레이션을 적용한다. 기존 CHECK는 아직 강화하지 않는다.
4. 1단계 전수 조사·자동 보정·검수를 완료한다.
5. 2단계 전수 조사·자동 보정·검수를 완료한다.
6. dev 전체 개수·중복·출처·상태·멱등성을 검증한다.
7. 사용자에게 변경·보류·실패 건수와 대표 사례를 보고한다.
8. 사용자 승인 후 prod에 additive 마이그레이션을 먼저 적용한다. 이 단계에서는 기존 필드를 바꾸지 않는다.
9. 새 nullable 필드를 우선 읽고 값이 없으면 legacy 필드를 읽는 호환 웹·RPC를 배포한다. 기존 정적 페이지도 정상인지 확인한다.
10. 안정 출처 키 bootstrap manifest를 원자적으로 적용하고 자동 연결·미연결·충돌 개수를 검증한다.
11. 승인된 해시의 데이터 manifest를 원자적으로 적용한다.
12. 새 값과 legacy boolean·URL의 dual-write 결과를 확인한 뒤 신규·기존 필드 정합 CHECK를 강화한다.
13. 새 데이터로 정적 페이지를 다시 빌드·배포하고 prod DB와 실제 상세페이지를 직접 확인한다.
14. 한 릴리스 이상 관찰하고 legacy fallback 소비자가 0개일 때만 제거 작업을 별도 진행한다.

다음 조건이면 prod 반영을 중단한다.

- 대상 개수 불일치
- 중복 폰트 또는 중복 출처 ID
- 근거 없는 라이선스 확정
- `needs_review` 값을 verified로 공개
- 예상 manifest 밖의 행 변경
- 기준선 이후 `updated_at` 또는 before 값 변경
- manifest 해시·스키마 버전·안정 출처 키 불일치

prod 변경은 기존 행별 `noonnu_publish` upsert를 재사용하지 않는다. service-role만 실행 가능한 전용 DB RPC가 manifest 전체의 대상 개수, 안정 출처 키, before 값, `updated_at`, 허용 필드와 변경 상한을 먼저 검사한다. 하나라도 실패하면 0건 적용하고, 모두 통과할 때 한 트랜잭션으로 반영한다.

문제가 생기면 현재값 precondition을 가진 역방향 manifest로 이전 값을 복원하고 보관한 직전 정적 빌드 산출물을 다시 배포한다. 역방향 manifest도 일부 복원은 허용하지 않는다.

prod 적용 전 dev에서 `정방향 적용 → 역방향 적용 → 대상 필드 byte-for-byte 비교`를 통과해야 한다. `conditional`을 legacy `false`로 바꾸는 동안 기존 화면에서 `denied`처럼 보일 수 있으므로 호환 웹·RPC 검증에서 세 상태의 표시를 각각 확인한다.

1,240종은 2026-07-18 기준선이다. 실행 시작 시 prod exact count를 다시 확인하며 값이 달라졌으면 자동 진행하지 않고 새로운 기준선과 차이를 사용자에게 보고한다.

## 13. 실패 사전 점검

| 실패 가능성 | 방어책 |
|---|---|
| 공식처럼 보이는 엉뚱한 주소 자동 승인 | 폰트명·제작사·페이지 역할을 함께 확인 |
| 봇 차단을 죽은 링크로 오판 | 차단 상태는 broken 금지, needs_review 처리 |
| 눈누 원문을 공개값으로 오염 | 원본·분석·검증 계층 분리 |
| 라이선스 변경을 자동 덮어쓰기 | 내용 해시 변경은 검수 대상으로만 등록 |
| slug 충돌로 다른 폰트 수정 | DB ID·제공자 ID·이름·제작사 복합 연결 |
| 대량 보정 중 일부만 prod 반영 | 승인된 manifest와 변경 수 가드 사용 |
| 조사 중 다른 작업이 같은 행 수정 | before 값·updated_at 낙관적 잠금, 충돌 시 전량 중단 |
| dev·prod UUID 불일치 | 안정 출처 키로 대상 해석, slug 단독 upsert 금지 |
| legacy URL 의미 변경으로 CTA 오작동 | `official_url` 동결, `foundry_url`·`download_url` additive 전환 |
| 재실행으로 증거·검수 항목 중복 | 실행 ID와 출처 키를 이용한 멱등 저장 |

## 14. 완료 기준

- 최초 기준선 1,240종 또는 실행 시 사용자가 승인한 갱신 기준선 전체가 누락 없이 조사 결과에 포함된다.
- 모든 폰트에 다운로드와 라이선스 확인 상태가 있다.
- dev와 prod의 모든 자동 변경 대상이 동일한 안정 출처 키로 단일 매칭된다.
- 공개 라이선스 값은 공식·공공기관 근거 또는 명시적 미확인 상태다.
- UI가 실제 DB 값을 사용하며 권한을 고정 표시하지 않는다.
- `흰꼬리수리`는 눈누 인스타그램을 다운로드·라이선스 출처로 사용하지 않는다.
- `횡성한우체`는 유효한 공식·공공기관 대체 출처를 쓰거나 다운로드 버튼 없이 재확인 상태가 된다.
- 동일한 전수 조사 재실행 결과가 멱등하다.
- prod manifest는 충돌 없는 전체 적용 또는 0건 적용만 가능하다.
- 매주 링크 검사와 분기 라이선스 검사가 prod·dev 쓰기 키 없이 동작한다.
- 모든 조사 대상이 정의된 상태 중 하나로 분류되고 사용자가 미해결 건수와 사유를 승인한다.
- 안정키 bootstrap 결과의 자동 연결·미연결·충돌 개수가 보고되고, 미연결·충돌 행은 자동 적용되지 않는다.
- 정방향·역방향 manifest 왕복 후 대상 필드가 byte-for-byte로 같다.
- 기존 import·enrich·uploader가 검증 필드를 직접 변경할 수 없다.
- 서로 다른 실행의 24시간 간격 관찰값이 연결되어야만 다운로드 상태가 `broken`으로 바뀐다.
- prod 반영 전후 DB 상태와 실제 상세페이지가 직접 검증된다.

## 15. legacy 소비자 조사 기준선

구현 전에 아래 실제 호출처를 다시 `rg`로 확인하고, 새 필드 dual-read·dual-write 전환표에 체크한다.

- 웹 변환·표시: `apps/web/lib/db/mappers.ts`, `apps/web/lib/db/types.ts`, `apps/web/components/LicenseSummaryCard.tsx`, `apps/web/lib/license.ts`, `apps/web/lib/db/collections.ts`, `apps/web/types/font.ts`
- 검색·클릭 RPC: `supabase/migrations/0002_upsert_font_rpc.sql`, `0006_search_fonts.sql`, `0007_font_clicks.sql`, `0009_chosung_search.sql`
- 눈누·일반 파이프라인: `apps/pipeline/src/fontagit_pipeline/models.py`, `uploader.py`, `transform.py`, `noonnu_import.py`, `noonnu_enrich.py`, `noonnu_review.py`, `noonnu_publish.py`, `__main__.py`
- 사용자 제출: `apps/web/components/SubmitForm.tsx`, `apps/web/lib/db/submissions.ts`, `supabase/migrations/0015_font_submissions.sql`
- 기존 눈누 보강 구조: `supabase/migrations/0016_noonnu_enrich.sql`의 라이선스 필드와 `license_proposals`

특히 현재 mapper의 고정 라이선스 표시, `official_url` 다운로드 CTA, boolean 기반 무료 판정, 행별 slug upsert, 눈누 첫 외부 링크 선택 규칙을 각각 제거 또는 후보 전용으로 제한했는지 확인한다.
