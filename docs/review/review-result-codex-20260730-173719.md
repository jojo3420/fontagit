### 종합 평가
- 전체 점수: 6.5/10
- 한줄 요약: 큰 방향은 맞지만, **실패·재실행·자동승인·prod 적용 전 검증 게이트가 약해서 바로 구현 승인하기는 어렵습니다.**

### 항목별 리뷰
| 관점 | 평가 | 상세 |
|------|------|------|
| 완성도 | 주의 | run → snapshot → finding → 승인 → manifest → apply 흐름은 잘 잡혀 있습니다. 다만 실패·재실행·부분 적용 방지 기준이 부족합니다. |
| 누락 항목 | 미흡 | 고아 run, 중복 finding, auto-approve 범위 제한, prod 시간차 검증, rollback 기준이 빠져 있습니다. |
| 일관성 | 주의 | “실패 시 나머지 계속”과 “실패 0건 완료”가 충돌합니다. 185종, 174종, 348 finding 기준도 완료 기준에 더 명확히 들어가야 합니다. |
| 실현 가능성 | 주의 | 구현은 가능하지만, 현재 설계 그대로면 의도치 않은 승인이나 prod 덮어쓰기 위험이 있습니다. |

### 구체적 피드백
1. [Blocker] 3.9, 5.1: 재크롤 실패 처리 기준이 불명확합니다.  
`실패 건은 finding 미적재, 나머지는 계속`이면 174건 중 일부만 적용될 수 있습니다. `auto_fix_safe` 174종 중 1건이라도 실패하면 apply 중단, 부분 적용은 별도 승인으로 고정해야 합니다.

2. [Blocker] 3.9: run 생명주기가 부족합니다.  
중단 run이 남고 재실행 때 새 run을 만들면 고아 run과 중복 finding이 생깁니다. 승인과 manifest는 반드시 `completed` 또는 `correction_ready` 상태의 특정 `run_id`만 대상으로 해야 합니다.

3. [Blocker] 3.6, 3.8: auto-approve 범위가 너무 넓습니다.  
`auto_applicable=True`만으로 승인하면 과거 run이나 다른 finding이 같이 승인될 수 있습니다. `run_id`, 대상 목록 해시, 허용 필드 2개, 174 fonts, 348 findings, before가 오염 URL인지까지 확인해야 합니다.

4. [Blocker] 3.7: prod 적용 시 시간차 문제가 남아 있습니다.  
prod manifest가 prod 현재값으로 `before`를 다시 만들면, dev 적용 후 prod 값이 바뀐 경우 그 변경을 덮어쓸 수 있습니다. prod preflight는 “승인 당시 expected before”와 prod 현재값이 같은지도 확인해야 합니다.

5. [Blocker] 3.7: `SourceKey` 존재 여부만으로는 부족합니다.  
prod `font_sources`에 185종이 있는지만 보지 말고, `provider + provider_record_id`가 dev/prod에서 각각 정확히 1건인지 확인해야 합니다. 중복이면 엉뚱한 폰트가 바뀔 수 있습니다.

6. 3.4, 3.5: evidence 공유는 가능하지만 보강이 필요합니다.  
`official_url`과 `license_source_url`이 같은 snapshot을 공유하는 설계는 타당합니다. 다만 근거 위치는 필드별로 나눠야 합니다. `official_url`은 제작사 링크 앵커, `license_source_url`은 눈누 상세 페이지 또는 라이선스 표 위치를 따로 남겨야 합니다.

7. 3.3, 3.5: snapshot 1건 + finding 2건 저장 원자성이 명시되지 않았습니다.  
한 폰트 저장 중 끊기면 finding이 1개만 남을 수 있습니다. 폰트 단위로 snapshot과 finding 2건을 한 트랜잭션으로 저장한다고 적어야 합니다.

8. 2, 3.3, 3.6: 07-29 판정과 현재 판정 불일치 처리 기준이 약합니다.  
값만 달라지고 여전히 `auto_fix_safe`면 보고 후 진행 가능하지만, action이 `manual_review`나 `no_link`로 바뀌면 자동 적용에서 제외해야 합니다.

9. 3.8: URL 안전 검증 규칙이 빠져 있습니다.  
`http/https`만 허용, `javascript:` 차단, 리다이렉트 후 최종 host 검증, IDN/punycode 처리 기준을 문서에 넣어야 합니다.

10. 4, 5: 완료 기준이 아직 검증 가능한 형태가 아닙니다.  
“재조회 검증”, “실화면 확인”만으로는 부족합니다. SQL 기대 count, 리포트 경로, manifest 해시, apply row count, 화면 확인 대상 기준을 명시해야 합니다.

11. 4: `mypy src (기존 70 errors 유지)`는 위험합니다.  
총 오류 수만 같으면 새 오류가 생겨도 놓칠 수 있습니다. “기존 baseline 대비 신규 mypy 오류 0건”으로 바꾸는 게 맞습니다.

12. 3.8, 5: rollback 기준이 없습니다.  
잘못 적용된 뒤 되돌릴 절차가 없습니다. 최소한 manifest의 `before` 값으로 복구 패키지를 만들 수 있고, 복구도 preflight와 사용자 승인을 거친다고 적어야 합니다.

### 개선 제안
1. 최우선: 승인·manifest 명령에 `--run-id`, `--expected-font-count 174`, `--expected-finding-count 348`, `--target-list-hash`를 강제하세요.

2. 재크롤 실패 정책을 고정하세요. 추천은 **auto_fix_safe 실패 1건이라도 있으면 전체 apply 중단**입니다. 부분 적용은 별도 승인일 때만 허용하세요.

3. prod preflight에 “승인 당시 before 값과 prod 현재값 일치” 검사를 추가하세요. 다르면 중단하고 재승인 받는 게 안전합니다.

4. 완료 기준을 숫자로 바꾸세요: `174 fonts`, `348 field updates`, `manual_review 10 + nullify 1 미승인`, `중복 active finding 0`, `고아 run 승인 대상 0`.

5. 같은 evidence 공유는 유지하되, field별 `evidence_locations`를 분리하세요. 새 스키마를 크게 만들 필요는 없고, 기존 snapshot 구조 안에서 근거를 더 선명하게 남기면 됩니다.