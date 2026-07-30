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
1. 대상 선정   state-v2.jsonl에서 recommended_action != keep 인 185종 추출
2. 재크롤      185종만, 요청 간 1초 지연, 기존 스캔기 재사용 (약 7분)
3. 판정        기존 noonnu_url_audit 로직 그대로
4. 적재        run(stage=metadata) -> 폰트당 snapshot 1건 + finding 2건
5. 대조 보고   07-29 판정 vs 현재 판정, 불일치 목록 제시
6. dev 적용    font-audit-review auto-approve -> manifest build --target dev
               -> preflight -> apply
7. dev 검증    재조회로 174종 반영 확인
8. prod 승인   승인 패키지 작성 -> 사용자 승인 1회
9. prod 적용   manifest build --target prod -> preflight -> apply -> 재조회 검증
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
| `evidence_locations` | 선택자 경로 + 앵커 문구 (`audit_noonnu._selector_path` 재사용) |
| `extraction_rule_id` / `parser_version` | 판정 재현용 |

### 3.5 저장되는 finding

폰트마다 2건.

| 필드 | before | after |
|---|---|---|
| `official_url` | 오염된 눈누 SNS 주소 | 재추출한 제작사 홈페이지 |
| `license_source_url` | 오염된 눈누 SNS 주소 | 눈누 폰트 상세 페이지 URL |

두 finding은 같은 `evidence_id`를 참조한다.

### 3.6 `auto_applicable` 매핑

| 판정 | 건수 | `auto_applicable` | 결과 |
|---|---|---|---|
| `auto_fix_safe` | 174 | `True` | `font-audit-review auto-approve`가 승인, manifest 포함 |
| `manual_review` | 10 | `False` | 적재만. 근거가 남으므로 재크롤 없이 사람이 판단 가능 |
| `nullify` | 1 (`google-sans-flex`) | `False` | `fonts.official_url`이 NOT NULL이라 비울 수 없음. 근거만 남기고 별도 처리 |

### 3.7 dev/prod 이식

`ManifestEntry`는 `font_id`가 아니라 `SourceKey(provider, provider_record_id)`를 키로 쓴다(`audit_manifest.py:228`). dev/prod의 `fonts.id`가 달라도 이 키로 대상을 찾는다. `manifest build --target prod`가 prod 현재값 기준으로 `before`/`expected_updated_at`을 재생성한다.

⚠️ 미검증: prod `font_sources`에 대상 185종의 `provider_record_id`가 빠짐없이 있는지. **계획 첫 단계에서 읽기 전용 조회로 검증하고, 누락이 있으면 진행 전에 보고한다.**

### 3.8 안전장치 (기존 구조 활용, 신규 없음)

- 파일 해시 일치 (`--sha256`, `--confirm-hash`)
- `expected_updated_at` 낙관적 잠금 (조회 후 타인이 변경했으면 거부)
- `preflight`가 DB 현재값과 manifest를 필드 단위 대조 (읽기 전용)
- prod 추가 관문: `FONTAGIT_PROD_MANIFEST_ENABLED=true` + `--approval-id` + 대화형 `yes`
- prod 쓰기 쿼리 전문을 사용자에게 제시하고 승인 후 실행

### 3.9 에러 처리

| 상황 | 처리 |
|---|---|
| 재크롤 실패 (HTTP 오류, 타임아웃) | 해당 건 finding 미적재, 리포트에 실패 목록 명시. 나머지는 계속 |
| 07-29와 판정 불일치 | 새 값 사용. 불일치 목록을 보고에 포함 |
| 페이지에서 링크 소실 | `no_link` 판정 -> `auto_applicable=False` |
| run 중단 | `complete_run` 미호출 상태로 남김. 재실행 시 새 run 생성 |

## 4. 검증

| 항목 | 방법 |
|---|---|
| 변환 함수 | 단위 테스트: 같은 입력에 같은 해시(결정성), 필드 매핑 정확성 |
| `auto_applicable` 매핑 | 판정별 플래그 테스트 |
| 승인 격리 | `manual_review`/`nullify`가 manifest에 포함되지 않음을 검증 |
| 회귀 | `uv run pytest -q` (기존 472 passed 유지), `ruff check .`, `mypy src` (기존 70 errors 유지) |
| dev 적용 후 | 재조회로 174종 `official_url`/`license_source_url` 반영 확인 |
| prod 적용 후 | 재조회 + 재배포 후 실화면 확인 |

## 5. 완료 기준

1. 185종 재크롤 완료, 실패 0건 (실패 시 목록 보고)
2. dev에 174종 정정 적용 및 재조회 검증
3. prod 승인 패키지 사용자 승인 후 174종 적용 및 재조회 검증
4. 재배포 후 폰트 상세 화면에서 제작사 링크가 눈누 SNS가 아님을 확인
5. `manual_review` 10건 + `nullify` 1건이 근거를 갖춘 채 미승인 상태로 남아 있음
6. `license_verified` 강등 별도 이슈 등록

## 6. 범위 밖

- `license_verified` / `license_status` 정책 (별도 이슈)
- 눈누 크롤러 고도화 (#120), 크롤러 결함 5종 (#141)
- 폰트 상세 UI 고도화 (#152)
- 브랜치 위생 정리 (#153) 중 develop 외 항목
