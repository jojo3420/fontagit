# 눈누 URL 오염 정정 - 감사 finding 적재 경로 설계

- 작성일: 2026-07-30
- 관련 이슈: #150 (전수 검증 및 172종+ 데이터 정정), 원 결함 #148, 근본 수정 PR #149, 검출 도구 PR #151
- 선행 설계: `docs/superpowers/specs/2026-07-28-noonnu-official-url-audit-design.md`
- 선행 계획: `docs/superpowers/plans/2026-07-28-noonnu-official-url-audit.md`

## 1. 문제

PR #151로 검출 도구는 완성됐고 전수 스캔도 끝났다(1,110종, 오류 0). 그러나 **스캔 결과를 실제 정정으로 옮길 경로가 없다.**

`audit_manifest.py:365`가 정정 항목마다 근거 레코드(snapshot)를 1:1로 요구하고, 없으면 `finding.evidence_id` 검증에서 예외로 거부한다. 기존 스캔 산출물(`output/noonnu-url-scan-state-v2.jsonl`)의 `ScanRecord`에는 snapshot 필수 필드가 없다.

| snapshot 필수 필드 | ScanRecord 보유 여부 |
|---|---|
| `normalized_sha256` | 없음 |
| `raw_sha256` | 없음 |
| `final_url` | 없음 (리다이렉트 미기록) |
| `http_status` | 없음 |
| `evidence_locations` | 없음 (`evidence`는 사람이 읽는 한 줄 문자열) |

없는 근거는 합성할 수 없다. 대상 폰트를 다시 읽어오면서 그 시점에 근거를 남기는 것이 유일한 정직한 경로다.

## 2. 결정 사항 (2026-07-30 사용자 확정)

| 항목 | 결정 | 근거 |
|---|---|---|
| 재크롤 범위 | 정정 후보 185종 (`auto_fix_safe` 174 + `manual_review` 10 + `nullify` 1) | keep 925종은 정정 대상이 아니라 manifest에 들어가지 않음. 1,110종 전량은 42분 실측, 185종은 약 7분 |
| 07-29 판정과 불일치 시 | 목록으로 보고하고 **새 값 사용** | 근거가 현재 응답에서 나오므로 값과 근거의 짝이 항상 일치 |
| `license_source_url` 새 값 | 눈누 폰트 상세 페이지 (`https://noonnu.cc/font_page/<id>`) | 실제로 라이선스 표를 읽은 곳. `noonnu_enrich.py:567`이 이미 `license_source_url`에 눈누 페이지를 넣고 있음 |
| `license_verified` 강등 | **이번 범위 제외**, 별도 이슈로 분리 | (1) 오염된 것은 근거 URL이지 판정 내용이 아님 (2) 같은 논리면 눈누만 근거인 Tier B 전체가 대상이라 172종 한정은 기준 불일치 (3) `0026:337-339`가 `license_status` 동반 변경을 강제하는데 그 정책이 미정 |
| prod 승인 방식 | 승인 패키지 1회 일괄 승인, 한 트랜잭션 적용 | 174건이 이미 AND 조건(앵커 근거 + 검증된 제작사 호스트) 통과. 분할하면 부분 적용 상태와 복구 지점이 늘어남 |
| develop 브랜치 | `origin/main`으로 리셋해 유지 | develop-only 14커밋의 파일 내용이 전부 main에 존재 확인, main이 26커밋 앞섬 |

## 3. 설계

### 3.1 방침

새 모듈을 만들지 않는다. 원문 HTML이 손에 있는 순간에만 정직한 해시를 만들 수 있으므로 **크롤과 적재를 한 흐름에 둔다.** 기존 `noonnu_enrich._save_audit_candidate`(`noonnu_enrich.py:515`)가 동일한 일(눈누 HTML -> snapshot -> finding)을 하므로 그 패턴을 차용한다.

### 3.2 변경 지점

| 파일 | 변경 |
|---|---|
| `noonnu_url_scan.py` | `scan_targets()`에 선택적 감사 저장소 주입. 대상 필터 추가 |
| `noonnu_url_audit.py` | `ScanRecord` -> `SnapshotDraft`/`FindingDraft` 변환 함수 신설 |
| `__main__.py` | `noonnu-url-scan`에 `--store-findings`, `--only-actionable` 플래그 |

기존 판정 로직(`noonnu_url_audit.py`)과 추출 로직(`audit_noonnu.py`)은 변경하지 않는다.

### 3.3 실행 흐름

```
0. 사전 검증   dev/prod 양쪽에서 대상 185종의 (provider, provider_record_id)가
               각각 정확히 1건인지 읽기 전용 조회. 이상 시 중단하고 보고
               (수동 조회가 아니라 스캔 명령의 첫 단계로 코드에 넣는다)
1. 대상 선정   state-v2.jsonl에서 recommended_action != keep 인 185종 추출
2. 재크롤      185종만, 요청 간 1초 지연, 기존 스캔기 재사용 (약 7분)
               auto_fix_safe 대상 실패 시 --retry-failed로 채운 뒤 진행
3. 판정        기존 noonnu_url_audit 로직 그대로. auto_applicable은 이 판정 기준
4. 적재        run(stage=metadata) -> 폰트당 snapshot 1건 + finding 2건
               적재 후 finding 수 == 대상 수 x 2 검사
5. 대조 보고   07-29 대비 값 불일치 목록 + 판정 강등 목록 제시
6. dev 적용    font-audit-review auto-approve -> manifest build --target dev
               -> preflight -> apply
7. dev 검증    재조회로 174종 반영 확인
8. prod 승인   manifest build --target prod -> before가 전부 오염 URL인지 대조
               -> 승인 패키지 작성 -> 사용자 승인 1회
9. prod 적용   preflight -> apply -> 재조회 검증
10. 재배포     정적 사이트(output: 'export')라 DB만 고치면 화면이 안 바뀜.
               scripts/deploy.sh 필요
```

### 3.4 저장되는 snapshot

폰트마다 1건. 필드는 `noonnu_enrich._save_audit_candidate` 패턴을 따른다.

| 필드 | 값 |
|---|---|
| `request_url` | 눈누 폰트 상세 URL |
| `final_url` | 리다이렉트 후 최종 URL (실측) |
| `http_status` | 실측 응답 코드 |
| `raw_sha256` | 원문 HTML 바이트 해시 |
| `normalized_sha256` | 추출값 정규화 JSON 해시 (결정적: `sort_keys=True`) |
| `extracted` | 재추출한 `official_url`, `foundry`, 앵커 텍스트 |
| `evidence_locations` | **필드별로 분리해 기록.** `official_url`은 제작사 링크 앵커의 선택자 경로와 문구, `license_source_url`은 라이선스 표 영역의 선택자 경로 (`audit_noonnu._selector_path` 재사용) |
| `extraction_rule_id` / `parser_version` | 판정 재현용 |

### 3.5 저장되는 finding

폰트마다 2건.

| 필드 | before | after |
|---|---|---|
| `official_url` | 오염된 눈누 SNS 주소 | 재추출한 제작사 홈페이지 |
| `license_source_url` | 오염된 눈누 SNS 주소 | 눈누 폰트 상세 페이지 URL |

두 finding은 같은 `evidence_id`를 참조한다. 같은 HTML 응답 하나에서 두 값이 모두 나오므로 논리적으로 타당하고, `findings.evidence_id`에 유일성 제약이 없어 스키마상으로도 가능하다(`0017_font_audit_schema.sql`에는 `fonts` 테이블의 외래키 제약만 있음).

### 3.6 `auto_applicable` 매핑

| 판정 | 건수 | `auto_applicable` | 결과 |
|---|---|---|---|
| `auto_fix_safe` | 174 | `True` | `font-audit-review auto-approve --run-id`가 승인, manifest 포함 |
| `manual_review` | 10 | `False` | 적재만. 근거가 남으므로 재크롤 없이 사람이 판단 가능 |
| `nullify` | 1 (`google-sans-flex`) | `False` | 아래 별도 처리 |

⚠️ **`auto_applicable`은 07-29 판정이 아니라 재크롤 시점의 판정으로 결정한다.** 07-29에 `auto_fix_safe`였어도 재크롤 판정이 `manual_review`/`no_link`로 바뀌면 `False`로 적재한다. 판정 강등은 대조 리포트에 별도 목록으로 표기한다.

#### nullify 1건 (`google-sans-flex`) 도달 목표

실측(`noonnu-url-scan-state-v2.jsonl`):

```
db_official_url                   = https://www.instagram.com/noonnu_official/
db_license_source_url             = https://www.instagram.com/noonnu_official/
official_url_contamination        = noonnu_account
license_source_url_contamination  = noonnu_account
new_official_url                  = null   (상세 영역에 외부 제작사 링크 없음)
```

두 필드 모두 오염돼 있다. 필드별로 처리가 갈린다.

| 필드 | 제약 | 조치 |
|---|---|---|
| `license_source_url` | `0026:60-62`가 `null` 또는 문자열 허용 | **눈누 상세 페이지로 정정**. 다른 184종과 동일하게 자동 적용 대상 |
| `official_url` | `0001:19` `text not null` + `0026:63-64`가 문자열만 허용 | 비울 수 없고 재추출 값도 없음. `manual_review`로 승격해 사람이 대체값을 결정 |

즉 이 1건은 "보류"가 아니라 **필드 단위로 쪼개** `license_source_url`은 자동 정정, `official_url`은 사람 검수 대기로 둔다. 결과적으로 사람 검수 대기는 10건이 아니라 **11건**(폰트 기준 11종)이 된다.

### 3.7 dev/prod 이식

`ManifestEntry`는 `font_id`가 아니라 `SourceKey(provider, provider_record_id)`를 키로 쓴다(`audit_manifest.py:228`). dev/prod의 `fonts.id`가 달라도 이 키로 대상을 찾는다. `manifest build --target prod`가 prod 현재값 기준으로 `before`/`expected_updated_at`을 재생성한다.

⚠️ 미검증 (계획 첫 단계에서 읽기 전용 조회로 검증하고, 이상이 있으면 진행 전에 보고한다):

1. prod `font_sources`에 대상 185종의 `provider_record_id`가 빠짐없이 있는지
2. **`(provider, provider_record_id)`가 dev와 prod 각각에서 정확히 1건인지.** 존재 확인만으로는 부족하다. 중복이 있으면 manifest가 엉뚱한 폰트를 수정할 수 있다

#### prod 적용 시점의 값 대조 (필수)

`manifest build --target prod`는 prod 현재값으로 `before`/`expected_updated_at`을 **새로 만든다**. dev 승인 이후 prod에서 누군가 값을 바꿨다면, 그 변경이 `before`에 반영된 채 manifest가 만들어져 **남의 수정을 조용히 덮어쓴다.** `expected_updated_at` 낙관적 잠금은 build 이후의 변경만 잡지 build 이전의 변경은 못 잡는다.

따라서 prod manifest 빌드 후, apply 전에 다음을 확인한다.

- prod `before` 값이 오염 URL(`https://www.instagram.com/noonnu_official/`)인지 항목마다 확인
- 오염 URL이 아닌 항목이 하나라도 있으면 **apply 중단**, 해당 목록을 보고하고 재승인
- 이 대조 결과를 승인 패키지에 포함한다

### 3.8 안전장치 (기존 구조 활용, 신규 없음)

- 파일 해시 일치 (`--sha256`, `--confirm-hash`)
- `expected_updated_at` 낙관적 잠금 (조회 후 타인이 변경했으면 거부)
- `preflight`가 DB 현재값과 manifest를 필드 단위 대조 (읽기 전용)
- prod 추가 관문: `FONTAGIT_PROD_MANIFEST_ENABLED=true` + `--approval-id` + 대화형 `yes`
- prod 쓰기 쿼리 전문을 사용자에게 제시하고 승인 후 실행

### 3.9 에러 처리와 실패 정책

### 재크롤 실패

수집 단계는 실패를 허용하되(나머지 계속 진행), **적용 단계는 전부 아니면 전무로 막는다.**

| 판정 대상 | 실패 시 |
|---|---|
| `auto_fix_safe` 대상 중 1건이라도 실패 | **apply 전면 중단.** 실패 목록을 보고하고 재크롤로 채운 뒤 다시 진행 |
| `manual_review` / `nullify` 대상 실패 | 경고만. 어차피 자동 적용 대상이 아님 |

근거: 승인 방식이 "일괄 승인 1회"이므로 일부가 빠진 불완전한 패키지를 승인받게 되면 승인 내용과 적용 결과가 어긋난다. 실패 건만 재시도하는 `--retry-failed` 옵션을 두어 전량 재크롤 없이 채울 수 있게 한다.

### run 생명주기와 멱등성

| 상황 | 처리 |
|---|---|
| 시작 시 미완료 run 존재 | 같은 stage의 미완료 run을 조회해 **사용자에게 보고하고 중단.** 이어받을지 새로 시작할지는 사람이 정한다 |
| 실행 중 중단 | `complete_run` 미호출 상태로 남음. 다음 실행이 위 검사에서 잡아낸다 |
| 재실행 | 새 run 생성. 이전 run의 finding은 `--run-id`로 격리되므로 섞이지 않는다 |
| 같은 run 안에서 같은 폰트 재처리 | 폰트+필드 단위로 기존 finding이 있으면 갱신, 없으면 삽입 |

승인과 manifest 빌드는 이미 `--run-id`를 필수로 받으므로(`__main__.py:2189-2191`, `required=True`) 다른 run의 finding이 섞일 위험은 구조적으로 없다.

### 저장 원자성 (한계 명시)

`SupabaseAuditStore`는 REST 기반이라 **여러 레코드를 한 트랜잭션으로 묶을 수 없다.** 폰트 하나에 snapshot 1건 + finding 2건을 저장하는 도중 끊기면 finding이 1건만 남을 수 있다.

대응: 원자성을 흉내내지 않고 **재실행 안전성으로 해결한다.** 위 표의 폰트+필드 단위 갱신 규칙이 있으므로 같은 run을 다시 돌리면 빠진 finding이 채워진다. 추가로 적재 완료 후 `finding 수 == 대상 폰트 수 x 2`를 검사해 불일치 시 중단한다.

### 기타

| 상황 | 처리 |
|---|---|
| 07-29와 값 불일치 | 새 값 사용. 불일치 목록을 대조 리포트에 포함 |
| 07-29와 판정 불일치 (강등) | 재크롤 판정을 따라 `auto_applicable` 재계산. 강등 목록을 별도 표기 |
| 페이지에서 링크 소실 | `no_link` 판정 -> `auto_applicable=False` |

## 3.10 되돌리기

manifest의 `before` 값이 곧 복구 데이터다. apply 후 문제가 발견되면 `before`/`after`를 뒤집은 역방향 manifest를 만들어 되돌린다.

- 역방향 manifest도 동일한 관문을 거친다: `preflight` -> 사용자 승인 -> `apply`
- 적용에 쓴 manifest 파일과 해시를 `docs/review/`에 보관해 복구 근거로 남긴다
- prod 적용 후 되돌릴 때도 재배포가 필요하다 (정적 사이트)

## 4. 검증

| 항목 | 방법 |
|---|---|
| 변환 함수 | 단위 테스트: 같은 입력에 같은 해시(결정성), 필드 매핑 정확성 |
| `auto_applicable` 매핑 | 판정별 플래그 테스트 |
| 승인 격리 | `manual_review`/`nullify`가 manifest에 포함되지 않음을 검증 |
| 회귀 | `uv run pytest -q` (기존 472 passed 유지), `ruff check .`, `mypy src` (**기존 baseline 대비 신규 오류 0건**. 총계 70 유지만 보면 새 오류가 기존 오류 감소에 가려진다) |
| dev 적용 후 | 아래 검증 쿼리로 숫자 확인 |
| prod 적용 후 | 같은 쿼리 + 재배포 후 표본 화면 확인 |

### 검증 쿼리

dev와 prod에서 동일하게 실행한다. 쿼리는 `scripts/`에 함께 커밋해 재사용한다.

```sql
-- (1) 오염 잔존 0건이어야 함 (적용 후)
select count(*) from fontagit.fonts
where official_url = 'https://www.instagram.com/noonnu_official/'
   or license_source_url = 'https://www.instagram.com/noonnu_official/';
-- 기대: manual_review 대기분만 남음 (아래 3번과 합이 맞아야 함)

-- (2) 정정 반영 건수
select count(*) from fontagit.fonts f
join fontagit.font_sources s on s.font_id = f.id and s.provider = 'noonnu'
where f.license_source_url like 'https://noonnu.cc/font_page/%';
-- 기대: 175 (auto_fix_safe 174 + google-sans-flex의 license_source_url 1)

-- (3) 사람 검수 대기 (미승인으로 남아야 함)
select count(*) from fontagit.font_audit_findings
where run_id = :run_id and auto_applicable = false and status <> 'approved';
-- 기대: manual_review 10종분 + google-sans-flex의 official_url 1건
```

## 5. 완료 기준

수치로 검증 가능한 형태로 고정한다.

| # | 기준 | 검증 방법 |
|---|---|---|
| 1 | 185종 재크롤 완료, `auto_fix_safe` 대상 실패 0건 | 스캔 리포트 `summary.errors == 0` |
| 2 | 적재된 finding 수 == 대상 폰트 수 x 2 | 적재 후 자동 검사 (3.9 참조) |
| 3 | dev 적용: 검증 쿼리 (2)가 175 | SQL 실행 결과 첨부 |
| 4 | prod 승인 패키지에 대조 결과 포함, 사용자 승인 1회 | 승인 패키지 문서 |
| 5 | prod 적용: 검증 쿼리 (2)가 175, apply가 보고한 갱신 행 수 일치 | SQL + apply 출력 첨부 |
| 6 | 사람 검수 대기 11종이 미승인 상태로 보존 | 검증 쿼리 (3) |
| 7 | 재배포 완료 후 표본 3종의 상세 화면 링크가 눈누 SNS가 아님 | 화면 확인 (전수 아님, 표본) |
| 8 | 적용 manifest와 해시를 `docs/review/`에 보관 | 파일 존재 확인 |
| 9 | `license_verified` 강등 별도 이슈 등록 | 이슈 URL |

## 6. 범위 밖

- `license_verified` / `license_status` 정책 (별도 이슈)
- 눈누 크롤러 고도화 (#120), 크롤러 결함 5종 (#141)
- 폰트 상세 UI 고도화 (#152)
- 브랜치 위생 정리 (#153) 중 develop 외 항목
