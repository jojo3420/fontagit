# Dual Plan Review Report: 2026-07-28-noonnu-official-url-audit-design.md

> Generated: 2026-07-28 23:02:06
> Reviewers: Codex (gpt-5.5, xhigh) + Antigravity agy (Gemini 3.5 Flash High)
> Mode: Dual (agy는 1차 호출이 프롬프트 전달 실패로 무효 → 재호출 후 정상 수신)

---

## 1. 모델별 리뷰 원문

- Codex: `docs/review/review-result-codex-20260728-230206.md` (점수 8/10)
- agy: `docs/review/review-result-agy-20260728-230206.md` (점수 8/10)

두 모델 모두 8/10을 줬고, 방향과 경로 분리는 타당하다고 평가했다. 지적은 "정정 기준의 구체성"과 "prod 적용 안전장치"에 집중됐다.

⚠️ agy 1차 호출은 `--print`에 stdin을 리다이렉트해 프롬프트가 전달되지 않았고, 다음 인자를 프롬프트로 해석해 CLI 플래그 설명을 반환했다(exit 0이라 실패로 잡히지 않음). 프롬프트를 인자로 넘겨 재호출한 결과가 위 파일이다. `--effort`는 이 모델에서 미지원이라 제외했다.

---

## 2. Claude 통합 크로스 리뷰

### 종합 소견

두 모델의 핵심 지적은 같은 곳을 가리킨다. **"mismatch로 판정한 값을 곧바로 정답으로 쓰는 것"이 이 설계의 가장 약한 고리**다. PR #149의 새 추출기도 본문 안에서는 여전히 첫 링크를 택하므로, 재추출 값이 항상 옳다는 보장이 없다. 172종을 잘못된 값에서 또 다른 잘못된 값으로 바꿀 수 있다.

다만 두 모델 모두 실제 스키마를 확인하지 못해 manifest 허용 필드에 대한 지적 일부는 사실과 다르다. 아래에서 코드로 대조해 걸렀다.

### 항목별 판정

| # | 지적 | 대상 | 출처 | 판정 | Claude 의견(근거) |
|---|------|------|------|------|------------------|
| 1 | mismatch를 곧바로 정정 대상으로 보는 기준이 약함 | 컴포넌트 3 | Codex | 동의 | 원본 확인: "mismatch로 판정된 폰트에 대해 manifest를 만들어"가 전부. 새 추출기도 본문 내 첫 링크 의존이라 오탐 가능 |
| 2 | license_verified 강등 기준 불명확 | 컴포넌트 3 | 합의 | 동의 | 원본은 "새 근거가 확보되지 않으면 false" 한 줄뿐. 판정 분기가 없음 |
| 3 | license_verified가 manifest v_allowed에 없을 수 있음 | 컴포넌트 2 | agy | 동의하지 않음 | 코드 확인: `0025:32`에 `license_verified` 이미 포함. 0026 추가 불필요 |
| 4 | license_source_url도 v_allowed에 추가 필요 | 컴포넌트 2 | agy | 동의하지 않음 | 코드 확인: `0025:28`에 `license_source_url` 이미 포함 |
| 5 | 정정 대상 필드가 official_url만 언급됨 | 컴포넌트 3 | agy | 동의 | 원본 확인: 배경엔 두 필드 오염이라 썼는데 정정 절에는 필드 명시가 없음 |
| 6 | prod 승인 패키지가 "쿼리 전문"만으로 부족 | 컴포넌트 3 | Codex | 동의 | 원본 확인: 건수-샘플-역방향 manifest 제시 규격이 없음 |
| 7 | 리포트에 recommended_action 필드 필요 | 컴포넌트 1 | Codex | 동의 | 판정 4갈래만 있고 조치 권고가 없어 구현자가 정책을 임의 결정하게 됨 |
| 8 | 스캐너 재개 로직이 리스크에만 있고 설계에 없음 | 컴포넌트 1 | 합의 | 동의 | 원본 확인: 상태 파일 위치-저장 주기-중복 요청 방지 모두 없음 |
| 9 | UA/robots/rate limit 구현 방식이 모호 | #141 | 합의 | 동의 | 원본 확인: "함께 넣어"만 있고 방법 없음. curl subprocess에서 robots 파싱 주체가 불명 |
| 10 | 본문 sanity 게이트의 오류 페이지 판정 기준 없음 | #141 | Codex | 동의 | 원본 확인: 기준 미정의 |
| 11 | 고정 1초 지연은 WAF 패턴 감지 위험, 지터 필요 | 리스크 | agy | 부분 동의 | 방향 타당. 다만 눈누 WAF 존재는 미확인 추정이므로 백오프를 우선 |
| 12 | no_container 임계치 초과 시 2단계 폴백 스캔 | 리스크 | agy | 부분 동의 | 원본에 "많이 나오면 폴백 선택자를 다시 본다"가 이미 있음. 임계치 수치화가 추가 가치 |
| 13 | official_url 동시 실행 충돌 테스트 필요 | 컴포넌트 2 | Codex | 부분 동의 | 단일 운영자 환경이라 동시 실행 가능성은 낮음. 우선순위 하향 |
| 14 | 테스트 범위가 넓음, #141은 최소 케이스만 | 테스트 | Codex | 부분 동의 | 타당하나 sanity 게이트는 172종 오염과 같은 뿌리라 축소 대상에서 제외 |
| 15 | #141/#142를 #150과 별도 PR로 유지 | 범위 | Codex | 동의 | 롤백 단위 분리가 맞음 |

### 모델 합의도 분석

- 합의 지적: 3건 (license_verified 기준, 스캐너 재개, UA/rate limit 구체화) — 신뢰도 높음
- Codex 단독: 7건 / agy 단독: 5건
- 두 모델 모두 놓쳐 Claude가 발견: 2건 (아래)

### 두 모델이 놓친 추가 관점

**A. `official_url`의 대조 키 이중 역할이 마이그레이션 범위를 넓힐 수 있다**

`0018_apply_font_audit_manifest.sql`에서 `official_url`은 두 곳에 더 등장한다.

```
0018:266  perform ... array['slug','name_en','name_ko','foundry','source_tier','official_url','status'], 'entry.current'
0018:291  or to_jsonb(v_existing.official_url) is distinct from v_entry#>'{current,official_url}'
0018:493  ... array['foundry','name_en','name_ko','official_url','slug','source_tier','updated_at']
```

`v_allowed`에 추가하는 것만으로 끝나지 않고, 266/291의 `current` 대조와 493의 배열이 변경 후 값과 충돌하지 않는지 함께 봐야 한다. 원본 문서는 이를 "pgTAP으로 검증한다"고만 적었고, **마이그레이션 자체가 이 세 지점을 함께 손대야 할 수 있다는 점**은 빠졌다.

**B. #150의 완료 기준이 없다**

문서는 리포트를 만들고 정정을 적용하는 데서 끝난다. "무엇을 확인하면 #150을 닫는가"가 없다. #150이 요구한 "938종 오염 여부 미검증" 해소를 어떤 수치로 증명할지 정의가 필요하다.

---

## 3. 통합 권고사항 (합집합)

### 즉시 반영 (Must)

1. **mismatch 후속 판정 추가** (Codex 단독, [Blocker]) — `recommended_action`을 `auto_fix_safe / manual_review / nullify / keep`으로 나눠, 자동 정정은 안전 조건을 만족한 건에만 적용한다.
2. **license_verified 정책표** (합의, [Blocker]) — 새 근거의 성격별 분기표를 명시한다. manifest 권한은 이미 있으므로 정책만 정하면 된다.
3. **정정 대상 필드 명시** (agy 단독) — `official_url`과 `license_source_url` 둘 다임을 컴포넌트 3에 적는다.
4. **prod 승인 패키지 규격** (Codex 단독) — 변경 건수, 필드별 건수, 샘플, 전체 slug 목록, 역방향 manifest, 검증 쿼리를 한 묶음으로 정의한다.
5. **스캐너 재개 설계** (합의) — 상태 파일 위치와 포맷, 저장 주기, 재시작 시 중복 요청 방지.
6. **0026 마이그레이션 범위 확장 검토** (Claude 발견) — `v_allowed` 외에 `0018:266/291/493`의 `official_url` 취급을 함께 점검.
7. **#150 완료 기준 정의** (Claude 발견) — 닫기 위해 증명할 수치.

### 검토 후 반영 (Should)

1. 리포트 JSON 스키마를 문서에 고정 (Codex)
2. UA / robots.txt / 요청 간격의 구현 주체와 방식 명시 (합의, #141 범위)
3. 본문 sanity 게이트의 오류 페이지 판정 기준 (Codex, #141 범위)
4. 429/403 수신 시 백오프와 안전 중단 (agy)
5. `no_container` 임계치 수치화 (agy)
6. #141/#142를 #150과 별도 PR로 분리 (Codex)

### 참고 (Nice-to-have)

1. manifest 동시 실행 충돌 테스트 (Codex)
2. #141 테스트를 결함별 최소 케이스로 한정 (Codex, 단 sanity 게이트는 제외)

---

## 4. 메타데이터

- Codex 종료 코드: 0 / agy 종료 코드: 0 (재호출분)
- Codex 리뷰 파일: `docs/review/review-result-codex-20260728-230206.md`
- agy 리뷰 파일: `docs/review/review-result-agy-20260728-230206.md`
- 이 통합 리포트: `docs/review/review-result-dual-20260728-230206.md`
