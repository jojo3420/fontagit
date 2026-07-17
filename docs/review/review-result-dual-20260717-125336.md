# Dual Plan Review Report: 2026-07-17-click-rate-limiting-design.md
> Generated: 2026-07-17 12:53:36 KST
> Reviewers: Codex (gpt-5.5, xhigh) + Antigravity agy (Gemini 3.5 Flash High)
> Mode: **Degraded — Codex 단독** (agy 인증 실패로 미수행. 자동 로그인 금지 정책상 재시도 안 함)

주의: agy 미참여로 "두 모델 합의"는 없다. 아래 판정은 Codex 리뷰를 Claude가 원본 문서와 대조해 검증한 결과다.

---

## 1. 모델별 리뷰 원문

### 1-1. Codex 리뷰 — 6.5/10
원문: `docs/review/review-result-codex-20260717-125336.md`. 핵심 지적 9건:
1. [Blocker] DB rate limit이 동시 요청에 취약(count 후 insert의 race).
2. [Blocker] Kong `limit_by: ip`가 실제 사용자 IP를 보는지 미검증(프록시/LB 뒤면 단일 IP로 보임).
3. [Blocker] Kong 스니펫이 기존 Supabase route(auth/CORS/apikey)와 충돌 가능.
4. count(*)는 방어 코드로 아쉬움(exists/카운터 테이블이 더 안전).
5. 병렬 요청 테스트 없음(현 테스트는 순차).
6. font_clicks 원본 보관 정책 없음.
7. "조용히 무시"의 운영 관측성 부재.
8. A안 curl 40회 검증이 빈약.
9. 롤백 절차 없음.

### 1-2. agy 리뷰
실패(exit=1): authentication required. 미수행.

---

## 2. Claude 통합 크로스 리뷰

### 종합 소견
Codex의 지적 대부분이 원본 문서에서 실제 확인된다. 특히 **#1 race condition은 진짜 설계 결함**이다 — B안의 존재 이유가 봇 방어인데 그 경로가 동시성에 뚫린다. #2/#3도 Kong 인계 문서를 그대로 따르면 오작동할 수 있어 보강이 필요하다. 나머지(#4~#9)는 방향은 맞으나 현재 트래픽 0 규모에선 우선순위가 낮거나 스코프 밖(#6은 롤업 cron 후속)이다.

### 항목별 판정
| # | 지적 | 대상 위치 | 출처 | 판정 | Claude 의견(근거) |
|---|------|----------|------|------|------------------|
| 1 | count 후 insert race | 4.3 SQL | Codex | **동의(CONFIRMED)** | 원본 4.3: `select count(*)` → `if < c_max` → `insert`는 원자적이지 않음. 동시 트랜잭션이 같은 스냅샷을 읽어 모두 통과. 봇 방어(1장 목적)의 정확히 그 경로가 무력화됨 |
| 2 | Kong 실제 IP 미검증 | 5.1/5.4 | Codex | **동의(CONFIRMED)** | 원본 5.4 미확인 사항에 IP 전달 검증 없음. prod가 프록시/LB/CF 뒤면 `limit_by: ip`가 remote_addr(단일 IP)만 봐서 전체 사용자 429 또는 제한 무력화 |
| 3 | Kong 라우트 플러그인 충돌 | 5.2 스니펫 | Codex | **부분 동의→Must** | 원본 5.3-1/5.4가 "실물 확인"은 언급하나, 새 service/route가 기존 /rest/v1 route의 apikey/CORS 플러그인을 **상속하지 않는다**는 구체 위험은 누락. 스니펫이 오도 가능 |
| 4 | count(*) 비효율 | 4.3 | Codex | **부분 동의→Nice** | 인덱스 있어 현 규모 성능 문제 없음(YAGNI). advisory lock으로 race 잡으면 정확성도 확보. 최적화는 규모 커진 뒤 |
| 5 | 병렬 테스트 없음 | 6.1 | Codex | **동의→Should** | 원본 6.1은 순차 경계만. 단 순수 SQL 테스트는 동시성 재현 한계 있음 → 시나리오 명시 + 한계 병기 |
| 6 | 원본 보관 정책 없음 | 8 | Codex | **동의하나 스코프 밖→Nice** | 보관 정책은 롤업 cron(font_click_daily) 후속의 영역. 이 설계(rate limiting) 스코프 아님. 리스크에 연결만 |
| 7 | 관측성 부재 | 4.1 | Codex | **부분 동의→Nice** | 익명 원칙상 상세 로깅 제약. 트래픽 0에 관측 인프라는 과함. 향후 지점만 명시 |
| 8 | A안 검증 빈약 | 5.3 | Codex | **동의→Should** | 원본 5.3-4는 429 확인만. 60초 해제/타 RPC 무영향/실제 insert 감소 추가 필요 |
| 9 | 롤백 절차 없음 | 전체 | Codex | **동의→Should** | 오탐 시 0008→0007 함수 복원 SQL, Kong 플러그인 비활성화 절차 필요 |

### 모델 합의도 분석
- 합의 지적: 0건 (agy 미참여 — Degraded)
- Codex 단독: 9건 (Claude 원본 대조로 개별 검증)
- Claude가 추가 발견: 0건(Codex #1이 핵심을 이미 포착)

### 동의하는 핵심 피드백 (Top 3)
1. **#1 race condition** — B안의 목적 자체를 무력화하는 실제 결함. 최우선.
2. **#2 Kong real IP** — 인계 문서대로 적용 시 정상 사용자 차단 또는 방어 무력화.
3. **#3 route 플러그인 미상속** — 스니펫이 apikey 검증을 우회시킬 수 있음.

### 동의하지 않는/강등한 피드백
- #4/#6/#7: 방향은 옳으나 현 규모(트래픽 0, 예산 0)에선 YAGNI 또는 다른 작업 스코프. Nice-to-have로 강등.

---

## 3. 통합 권고사항 (Degraded — Codex 단독 + Claude 검증)

### 즉시 반영 (Must) — 구현 착수 전
- **M1. B안 race 제거**: `record_click`에 폰트별 직렬화 추가. font_id 확정 직후 `perform pg_advisory_xact_lock(hashtext(p_slug))`(또는 font_id 기반)로 같은 폰트 동시 요청을 트랜잭션 단위 직렬화 → `count 후 insert` race 차단. fire-and-forget이라 짧은 대기 허용. (Codex #1)
- **M2. Kong real IP 검증 항목 추가**: 5.4에 "prod가 프록시/LB 뒤인지, X-Forwarded-For 신뢰(real_ip) 설정이 필요한지 확인"을 명시. 미확인 시 `limit_by: ip` 오작동 경고. (Codex #2)
- **M3. Kong route 플러그인 상속 경고**: 5.2 스니펫에 "새 route는 기존 /rest/v1의 apikey/CORS 플러그인을 상속하지 않음 → 그대로 붙이면 인증 우회 위험. 권장: 기존 rest route에 rate-limiting만 추가하거나 필요한 플러그인을 복제"를 경고로 추가. (Codex #3)

### 검토 후 반영 (Should)
- **S1. 병렬 테스트 시나리오**: 6.1에 "동시 50회 호출 후에도 상한 유지" 시나리오 추가 + 순수 SQL 동시성 재현 한계 병기. (Codex #5)
- **S2. A안 검증 보강**: 5.3에 429 발생/60초 후 해제/타 RPC 무영향/실제 insert 감소 확인 추가. (Codex #8)
- **S3. 롤백 절차**: 8장 또는 신설 절에 0008→0007 함수 복원 SQL, Kong 플러그인 비활성화 방법 명시. (Codex #9)

### 참고 (Nice-to-have)
- N1. count(*) → "20번째 존재만 확인(exists)" 최적화(규모 커진 뒤). (Codex #4)
- N2. font_clicks 보관 기간(예: 30일) — 롤업 cron 후속에서 결정. (Codex #6)
- N3. 무시 횟수 관측 지점(향후). (Codex #7)

---

## 4. 메타데이터
- Codex 종료 코드: 0 / agy 종료 코드: 1(인증 실패)
- Codex 리뷰 파일: `docs/review/review-result-codex-20260717-125336.md`
- agy 리뷰 파일: 없음(미수행)
- 이 통합 리포트: `docs/review/review-result-dual-20260717-125336.md`
