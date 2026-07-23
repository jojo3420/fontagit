# Dual Plan Review Report: 2026-07-22-collections-expansion-design.md
> Generated: 2026-07-22 15:31
> Reviewers: Codex (gpt-5.5, xhigh) + Antigravity agy (Gemini 3.5 Flash High)
> Mode: Degraded — 단일 모델(Codex)만 유효. agy는 실패(플래그 처리 오류로 리뷰 미생성, exit 0이나 본문 없음).

---

## 1. 모델별 리뷰 원문

### 1-1. Codex 리뷰 (성공)
- 전체 점수: 7/10
- 요약: 방향은 맞지만 "빌드타임 materialize + SSG 재빌드 + 눈누 재크롤링" 운영 흐름이 추상적이라 구현 계획으로 바로 넘기기엔 위험.
- 원문: `docs/review/review-result-codex-20260722-153145.md`

### 1-2. agy 리뷰 (실패)
- exit 0이나 stdout에 리뷰 본문 없음(`--dangerously-skip-permissions` 처리 중 permission/skill 탐색만 하고 종료). 유효 리뷰 아님 → 크로스 리뷰에서 제외.
- 원문: `docs/review/review-result-agy-20260722-153145.md`

---

## 2. Claude 통합 크로스 리뷰 (Codex 단독, 원본 문서 대조)

| # | 지적 | 대상 | 출처 | 판정 | Claude 근거 |
|---|------|------|------|------|------------|
| 1 | SSG 재빌드 트리거 막연(환경 구분 없음) | 절 8 | Codex[Blocker] | 동의 | 절 8은 "재빌드 트리거 필요"만, develop/main/prod 조건 없음 |
| 2 | materialize 실패 처리 없음 → 빈 페이지 정적생성 위험 | 절 6 | Codex[Blocker] | 동의 | 절 6에 롤백/유지 정책 부재. 실제 위험 |
| 3 | 눈누 재크롤링 fallback 부재 | 절 9 | Codex[Blocker] | 동의 | 절 9는 리스크 나열만, "못 가져오면" 대안 없음 |
| 4 | rule jsonb 스키마 느슨(허용 axis/op/value 목록 없음) | 절 6 | Codex | 동의 | 절 11-3에 미확정 표시 있으나 스키마 미정의는 빌드 붕괴 위험 |
| 5 | 자동 컬렉션 내 폰트 정렬 기준 없음 | 절 6,절 7 | Codex | 동의 | 문서에 auto 컬렉션 정렬 규칙 부재 |
| 6 | auto 컬렉션끼리 거의 동일 결과 처리 없음 | 절 6 | Codex | 부분 동의 | 절 6은 auto+editorial 중복만 다룸. 실제 발생 여지 |
| 7 | noindex(색인 제외)와 내부 노출 제한 혼용 | 절 7 | Codex | 동의 | 절 7 "노출/색인 제한" 표현이 둘을 섞음 |
| 8 | prod=dev 미해결이면 출시 판단 불안 | 절 9 | Codex | 동의 | 절 9에 인지됨. 출시 리스크로 격상, writing-plans 첫 작업으로 |
| 9 | B단계 첫 컬렉션 목록/rule 미구체 | 절 11 | Codex | 동의 | 절 11-3에 미확정. 구현 착수 전 구체화 필요 |
| 10 | "B단계 즉시" vs "0단계 정비 후" 문구 충돌 | 절 4 | Codex | 동의 | 절 4 "B단계(즉시, 정비 후)" 자체 모순 표현. 정리 필요 |
| 11 | 태그 출처/신뢰도 등급 구분 없음(원본/추론/검수) | 절 8 | Codex | 동의 | 절 8은 10% 감사만. 출처 구분이 검수 효율에 유리 |
| 12 | SEO description 템플릿 반복 = 얇은 문구 양산 | 절 7 | Codex | 부분 동의 | 절 7 템플릿 자동생성. 컬렉션별 고유화 규칙 권장 |

### Claude 추가 관점 (Codex도 놓친 것)
- **auto 컬렉션 slug 영속성**: rule이 바뀌면 slug/URL이 바뀌어 SEO 링크-색인이 깨진다. slug 고정 정책(rule 변경과 slug 분리)이 필요. (누락)
- **빌드 시간 영향**: 빌드타임 materialize는 1,240종 × 규칙 N개 평가를 빌드에 추가. 규칙 수가 적어 경미하나, 규칙 폭증 시 빌드 지연 감시 필요. (경미)

### 모델 합의도
- 합의: 0건 (agy 실패로 교차 불가) — Degraded
- Codex 단독: 12건 (Claude가 원본 대조로 11건 동의, 2건 부분 동의)
- Claude 자체 발견: 2건

---

## 3. 통합 권고사항

### 즉시 반영 (Must) — 구현 착수(writing-plans) 전 확정
1. **materialize 실패 처리**: "임시 테이블 생성 → 검증 → 원자적 교체" 방식. 실패 시 기존 `collection_items` 유지(빈 페이지 정적생성 방지). [Codex #2]
2. **SSG 재빌드 트리거 구체화**: 누가/어떤 조건/어떤 환경(develop/main/prod)을 재빌드하는지 명시. [Codex #1]
3. **rule jsonb 스키마 확정**: 고정 필드(`axis`, `op`, `value`, `minItems`, `sort`, `limit`, `noindexBelow`)와 허용값 목록 정의. 잘못된 rule의 빌드 붕괴 방지. [Codex #4]
4. **눈누 재크롤링 fallback**: 실패 시 기존 데이터 유지, 실패 URL 기록, 재시도 제한, 수동 보강 파일 허용. [Codex #3]

### 검토 후 반영 (Should)
- prod 데이터 검증을 writing-plans 첫 작업으로(dev vs prod의 fonts/collections/weights/tags 차이). [Codex #8]
- B단계 첫 컬렉션 8~12개 목록 + 각 rule + 예상 개수를 스펙에 명시. [Codex #9]
- 자동 컬렉션 내 폰트 정렬 기준(Tier A 우선/이름순/굵기 보유 우선 등). [Codex #5]
- noindex(색인 제외)와 내부 노출 숨김을 분리 정의. [Codex #7]
- 태그 출처 3구분(눈누원본/자동추론/사람검수) + 출처별 신뢰도. [Codex #11]
- "B단계 즉시" 문구를 "0단계 정비 후 착수"로 정리(모순 제거). [Codex #10]
- auto 컬렉션 slug 영속성 정책. [Claude]

### 참고 (Nice-to-have)
- SEO description 컬렉션별 고유화 규칙(템플릿 반복 완화). [Codex #12]
- auto 컬렉션 간 near-duplicate 감지. [Codex #6]

---

## 4. 메타데이터
- Codex 종료 코드: 0 (성공) / agy 종료 코드: 0 (본문 미생성, 무효)
- Codex 리뷰: `docs/review/review-result-codex-20260722-153145.md`
- agy 리뷰: `docs/review/review-result-agy-20260722-153145.md`
- 이 통합 리포트: `docs/review/review-result-dual-20260722-153145.md`
