# Dual Plan Review Report: 2026-07-30-noonnu-url-finding-ingest-design.md

- Generated: 2026-07-30 17:37
- Reviewers: Codex (gpt-5.5, xhigh) + Antigravity agy (gemini-3.5-flash-high)
- Mode: **Dual** (두 모델 모두 exit 0)
- 점수: Codex 6.5/10, agy 7.5/10

## 1. 모델별 리뷰 원문

- Codex: `docs/review/review-result-codex-20260730-173719.md`
- agy: `docs/review/review-result-agy-20260730-173719.md`

## 2. Claude 통합 크로스 리뷰

### 종합 소견

두 모델이 독립적으로 **같은 3가지 급소**를 지목했다: 재크롤 실패 시 부분 적용, run 생명주기 부재, 판정 강등 시 자동승인 필터 누락. 합의 항목은 전부 원본 문서에서 실재를 확인했다. 단독 지적 중에서는 Codex의 prod 시간차 문제와 SourceKey 중복 검증, agy의 nullify 1건 미처리가 실제 결함이었다. 반면 Codex의 auto-approve 범위 우려와 URL 스킴 검증 누락, agy의 evidence_id 유일성 우려는 코드 실측 결과 이미 처리돼 있어 패스했다.

### 항목별 판정

| # | 지적 | 위치 | 출처 | 판정 | 근거 |
|---|---|---|---|---|---|
| 1 | 재크롤 실패 시 부분 적용 위험 | 3.9 vs 5절 | 합의 | 동의 -> Must | 원본 3.9 "나머지는 계속" vs 5절 "실패 0건" 실제 충돌. 일괄 승인 방식과 결합하면 승인 내용과 적용 결과가 어긋남 |
| 2 | run 생명주기/고아 run/중복 finding | 3.9 | 합의 | 동의 -> Must | 원본 3.9에 "재실행 시 새 run 생성"만 있고 미완료 run 검사 없음 |
| 3 | 판정 강등 시 auto_applicable 재평가 | 3.3, 3.6 | 합의 | 동의 -> Must | 원본 2절은 "값 불일치 시 새 값 사용"만 다루고 판정 자체가 바뀌는 경우 미규정 |
| 4 | 완료 기준이 검증 불가 형태 | 5절 | 합의 | 동의 -> Must | 원본 "재조회 검증", "실화면 확인"에 기대 수치 없음 |
| 5 | prod 적용 시간차로 남의 수정 덮어쓰기 | 3.7 | Codex 단독 | 동의 -> Must | `build --target prod`가 before를 재생성하므로 dev 승인 이후 prod 변경이 before에 흡수됨. 낙관적 잠금은 build 이후만 방어 |
| 6 | SourceKey 존재뿐 아니라 유일성 검증 필요 | 3.7 | Codex 단독 | 동의 -> Must | 중복 시 엉뚱한 폰트 수정. 원본은 "빠짐없이 있는지"만 검증 대상으로 적음 |
| 7 | nullify 1건이 오염 상태로 잔존 | 3.6 | agy 단독 | 동의 -> Must | 실측: `db_official_url`, `db_license_source_url` 모두 눈누 인스타그램. `official_url_contamination: noonnu_account` |
| 8 | snapshot+finding 저장 원자성 미명시 | 3.3, 3.5 | Codex 단독 | 동의 -> Should | 실측: `audit_store.py`에 transaction/commit 없음(REST 기반). 원자성 불가이므로 재실행 안전성으로 대체 |
| 9 | evidence_locations 필드별 분리 | 3.4 | Codex 단독 | 동의 -> Should | 두 필드의 근거 위치가 다름(제작사 앵커 vs 라이선스 표) |
| 10 | mypy "70 errors 유지"는 신규 오류 은폐 | 4절 | Codex 단독 | 동의 -> Should | 총계만 보면 기존 감소가 신규 증가를 가림 |
| 11 | rollback 절차 부재 | 3.8, 5절 | Codex 단독 | 동의 -> Should | 원본에 되돌리기 언급 없음 |
| 12 | prod 사전검증을 코드로 자동화 | 3.7 | agy 단독 | 동의 -> Should | 수동 조회는 인적 누락 위험 |
| 13 | 검증 SQL 템플릿 커밋 | 5절 | agy 단독 | 동의 -> Should | 재현성 확보 |
| 14 | auto-approve가 과거 run까지 승인할 위험 | 3.6, 3.8 | Codex 단독 | **부분 동의** | 실측: `__main__.py:2189-2191` `--run-id required=True`. run 격리는 이미 강제됨. 다만 건수 검증 제안은 유효해 완료 기준에 반영 |
| 15 | URL 안전 검증(javascript: 차단 등) 누락 | 3.8 | Codex 단독 | **비동의 -> 패스** | 실측: `audit_noonnu.py:290`이 http/https만 통과, `noonnu_url_scan.py:206`이 https만 허용. 이미 차단됨 |
| 16 | finding.evidence_id 유일성 제약 확인 필요 | 3.5 | agy 단독 | **비동의 -> 패스** | 실측: `0017_font_audit_schema.sql`에 findings 관련 unique 제약 없음(fonts의 FK만). 공유 가능 |
| 17 | 충돌 시 `manifest build --target prod --force` 복구 | 3.7 | agy 단독 | **비동의 -> 패스** | 그런 플래그가 없고, 낙관적 잠금을 강제로 뚫는 것은 이 설계의 안전장치를 무력화. 재빌드 + 대조 + 재승인으로 대체 |

### 모델 합의도

- 합의 지적: 4건 (모두 Must로 확정 -- 합의 신뢰도가 실제로 높았음)
- Codex 단독: 8건 (동의 6 / 부분 동의 1 / 패스 1)
- agy 단독: 5건 (동의 3 / 패스 2)
- Claude 자체 발견: 1건 (nullify 건의 `license_source_url`은 `0026:60-62`상 정정 가능 -- 필드 단위로 쪼개면 사람 검수 범위가 줄어듦)

### 검증 과정에서 정정한 자체 오류

`google-sans-flex` 레코드를 처음 조회할 때 JSON 키 이름을 잘못 지정해(`current_official_url`, 실제는 `db_official_url`) 값이 비어 보였고, agy의 지적을 환각으로 판정할 뻔했다. 올바른 키로 재조회해 오염 상태를 확인하고 판정을 뒤집었다.

## 3. 통합 권고 (합집합)

### 즉시 반영 (Must) -- 7건, 전부 설계 문서에 반영 완료

1. 재크롤 실패 정책: `auto_fix_safe` 대상 1건이라도 실패하면 apply 전면 중단, `--retry-failed`로 보충 (합의)
2. run 생명주기: 시작 시 미완료 run 검사 후 중단-보고, 폰트+필드 단위 갱신으로 멱등성 확보 (합의)
3. `auto_applicable`은 재크롤 시점 판정으로 결정, 강등 목록 별도 표기 (합의)
4. 완료 기준 9개를 수치와 SQL로 재작성 (합의)
5. prod manifest 빌드 후 `before`가 전부 오염 URL인지 대조, 아니면 중단 (Codex)
6. SourceKey가 dev/prod 각각 정확히 1건인지 검증 (Codex)
7. nullify 1건을 필드 단위로 분리 처리: `license_source_url`은 자동 정정, `official_url`은 사람 검수 (agy + Claude)

### 검토 후 반영 (Should) -- 6건, 설계 문서에 반영 완료

8. 저장 원자성 한계를 명시하고 재실행 안전성으로 대체
9. `evidence_locations` 필드별 분리
10. mypy를 "신규 오류 0건"으로 변경
11. 되돌리기 절차(3.10절 신설)
12. prod 사전검증을 스캔 명령 첫 단계로 코드화
13. 검증 SQL을 `scripts/`에 커밋

### 패스 (비동의) -- 3건

14. URL 스킴 검증 (이미 구현됨)
15. evidence_id 유일성 (제약 없음)
16. `--force` 복구 (안전장치 무력화)

## 4. 메타데이터

- Codex 종료 코드: 0 / agy 종료 코드: 0
- 설계 문서 반영: Must 7건 + Should 6건 전부 반영
- 주요 변경 절: 3.3(흐름 0단계 신설), 3.4, 3.5, 3.6(nullify 분리), 3.7(prod 대조), 3.9(전면 재작성), 3.10(신설), 4, 5
