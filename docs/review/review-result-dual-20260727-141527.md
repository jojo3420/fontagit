# Dual Plan Review Report: 2026-07-27-license-audit-crawl-design.md

> Generated: 2026-07-27 14:20 KST
> Reviewers: Codex (gpt-5.5, xhigh) + Antigravity agy (Gemini 3.5 Flash High)
> Mode: **Degraded — Codex 단독** (agy 2회 시도 모두 무효: 1차 빈 출력(headless 권한 자동거부), 2차 주제 이탈 출력(문서 리뷰 대신 CLI 플래그 설명). 두 모델 합의가 아님을 명시함)

---

## 1. 모델별 리뷰 원문

### 1-1. Codex 리뷰

원문: `docs/review/review-result-codex-20260727-141527.md` (8/10, "legal 판정 기준과 적용 전 검증 기준 구체화 필요")

### 1-2. agy 리뷰

실패(무효). 원문: `docs/review/review-result-agy-20260727-141527.md` — 문서 리뷰가 아닌 무관한 출력이라 크로스 리뷰에서 제외.

---

## 2. Claude 통합 크로스 리뷰

### 종합 소견

Codex 리뷰는 전반적으로 정확하고, 특히 데이터 의미론(download_url)과 롤백 문서화 지적이 유효하다. 다만 Blocker 2건 중 1건(rollback)은 인프라가 이미 실존해 "설계 결함"이 아니라 "스펙 문서 누락"이며, 일부 지적은 스펙에 이미 처리된 내용이다.

### 항목별 판정

| # | 지적 | 출처 | 판정 | Claude 의견(근거) |
|---|------|------|------|------------------|
| 1 | [Blocker] KOGL 매핑 확정 취급 금지 | Codex | 부분 동의 | 스펙 S3에 "초안-그룹 승인 시 공식 대조 후 확정" + 사람 게이트 기재됨. 다만 "공식 기준 대조 선행 체크포인트"를 S3 첫 작업으로 명시하면 더 안전 → Should |
| 2 | [Blocker] rollback 기준 부재 | Codex | 부분 동의(문서 누락은 사실) | 실측: audit_manifest.py:238,371에 rollback_mode-reverse manifest 실존. 설계 결함이 아니라 스펙 미기재 → 스펙에 "prod 적용 시 reverse manifest 산출-보관" 명시 필요 → Must(저비용) |
| 3 | 제작사 용어 모호(Sandoll/NHN/네이버) | Codex | 부분 동의 | 5절 정규화 사전으로 일관되나, 권리사/디자이너/표기명 용어 정의 1단락 보강 가치 → Should |
| 4 | download_url 파일 직링크 vs 페이지 충돌 | Codex | 동의 | 실측: mappers.ts:78에서 verified 시 상세 "공식 다운로드" CTA href로 직접 노출. Tier A `files["regular"]`(gstatic 파일)과 Tier B 눈누 후보(페이지 URL) 의미 혼재 위험 실재 → Must(의미론 결정 필요) |
| 5 | 자동 게이트 기준 불명 | Codex | 부분 동의 | audit_policy.py 공식 도메인 화이트리스트 실존(모델은 코드 미열람). 스펙에 참조-필드별 게이트 1줄 보강 → Should |
| 6 | 재크롤 22종 실패 재현 기준 없음 | Codex | 동의 | HTTP/파싱/차단 분류 기준을 plan 단계에 정의 → Should |
| 7 | 적용 후 변경 수 검증 약함 | Codex | 부분 동의 | 7절에 "건수-샘플 쿼리" 기재됨. "기대 변경 수 = 실제 변경 수" 명문화 보강 → Should |
| 8 | 승인 기록 방식 없음 | Codex | 동의 | 스냅샷에 reviewed_by/reviewed_at 필드 실존, KOGL 그룹 승인 기록 절차만 스펙에 명시 → Should |
| 9 | 견본 문구 풀 범위 혼합 | Codex | 동의하지 않음 | 사용자 명시 결정(이번 포함)이며 S4 독립 슬라이스라 배포 판단 분리 이미 가능 → 패스 |
| 10 | 테스트 우선순위 | Codex | 부분 동의 | KOGL 파서-매핑-무결성 우선은 타당, 계획 단계 반영 → Nice |

### 모델 합의도 분석

- 합의 지적: 0건 (agy 무효 — Degraded)
- Codex 단독: 10건 / agy 단독: 0건
- 두 모델 모두 놓쳐 Claude가 발견: 0건

### 동의하는 핵심 피드백 (Top 3)

1. (#4) download_url 의미론 통일 — 파일 직링크 vs 다운로드 페이지, 사용자 결정 필요
2. (#2) reverse manifest 산출을 prod 적용 필수 절차로 스펙 명시
3. (#8) KOGL 그룹 승인 기록(누가-언제-근거 링크) 절차 명시

### 동의하지 않는 피드백 (반론과 근거)

- (#9) 견본 풀 분리: 사용자가 범위 포함을 명시 결정했고, 슬라이스가 이미 독립적(S4)이라 배포 리스크 분리 가능.

---

## 3. 통합 권고사항

### 즉시 반영 (Must)

1. download_url 의미 결정(파일 직링크/페이지 링크) 후 스펙 S1 명시 — 사용자 결정 대기 [Codex #4]
2. 적용 절차에 "reverse manifest 산출-보관, 실패 시 rollback_mode 재적용" 명시 [Codex #2]

### 검토 후 반영 (Should)

3. S3 첫 작업으로 "공공누리 공식 기준 대조 체크포인트" 명시 [Codex #1]
4. 5절에 권리사/디자이너/표기명 용어 정의 보강 [Codex #3]
5. 자동 게이트를 audit_policy 화이트리스트 참조로 구체화 [Codex #5]
6. 재크롤 실패 분류 기준(HTTP/파싱/차단) 추가 [Codex #6]
7. 적용 후 "기대 변경 수 = 실제 변경 수" 검증 기준 명문화 [Codex #7]
8. KOGL 그룹 승인 기록 방식(reviewed_by/at + 근거 링크) 명시 [Codex #8]

### 참고 (Nice-to-have)

9. 테스트 우선순위(KOGL 파서 > 매핑 > 무결성 > 견본) 계획 단계 반영 [Codex #10]

---

## 4. 메타데이터

- Codex 종료 코드: 0 / agy 종료 코드: 0(출력 무효 2회)
- Codex 리뷰 파일: `docs/review/review-result-codex-20260727-141527.md`
- agy 리뷰 파일: `docs/review/review-result-agy-20260727-141527.md`
- 이 통합 리포트: `docs/review/review-result-dual-20260727-141527.md`
