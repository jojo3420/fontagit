# Dual Plan Review Report: 2026-07-15-upload-atomicity-alias-sync-design.md
> Generated: 2026-07-15 12:42:49
> Reviewers: Codex (gpt-5.5, xhigh) + Antigravity agy (Gemini 3.5 Flash High)
> Mode: **Degraded — Codex 단독** (agy 인증 만료 exit=1, PR #7 리뷰와 동일 원인)

---

## 1. 모델별 리뷰 원문
- Codex: 완료(exit 0) — `docs/review/review-result-codex-20260715-124249.md` (점수 7/10)
- agy: 실패(exit 1) — "authentication required. Run 'agy' to log in". settings 모델 정상 원복 확인.

## 2. Claude 통합 크로스 리뷰 (Codex 단독, 원본 대조)

### 종합 소견
방향은 타당하나 DB 함수 보안 경계(EXECUTE 권한)와 몇몇 정책 명시가 빠졌다. 보안 1건만 Must, 나머지는 문서 명확화 수준의 Should.

### 항목별 판정
| # | 지적 | 대상 | 판정 | Claude 근거 |
|---|------|------|------|-------------|
| 1 | SECURITY DEFINER 권한 회수 미명시 | 0002 RPC | **동의 → Must** | DEFINER는 RLS 우회. PG 기본 PUBLIC EXECUTE라 anon도 쓰기 가능. revoke 필수 |
| 2 | p_font jsonb 컬럼 매핑 불명확 | 0002 RPC | **부분 동의 → Should** | 구현 시 명시 매핑 당연하나, 설계에 화이트리스트(_FONT_COLS) 명시로 계약 좁히면 좋음 |
| 3 | alias 빈값/중복 검증 | uploader | **부분 동의 → Should** | 기존 build_alias_rows가 이미 `if norm and norm not in seen`로 처리. 설계에 명시(회귀 방지) |
| 4 | 빈 alias 배열 정책 | 0002 RPC | **부분 동의 → Should** | delete만 하고 insert 스킵. published는 최소 1 alias 보장되나 정책 명시 |
| 5 | 원자성 롤백 테스트 부족 | 테스트 | **동의 → Should** | 원자성이 핵심인데 롤백 검증 케이스 미명시. 통합에 추가 |
| 6 | 실패 시 루프 동작 애매 | 에러 처리 | **동의 → Should** | 기존 동작=첫 예외 전파→중단. "첫 실패 즉시 중단, 처리분 유지, return 3" 명시 |
| 7 | 동시 업로드 리스크 | 0002 RPC | **동의하지 않음 → Nice** | 단일 프로세스 배치라 현실 위험 낮음. on conflict가 row lock. 전제 한 줄이면 충분 |
| 8 | licenses.py 분리 권장 | 설계 3 | **동의하지 않음(이미 처리)** | 설계 3번이 이미 "독립 소작업"으로 분리 |

### Claude 추가 발견 (Codex 미지적)
- **A. updated_at 갱신 누락** — 0001의 fonts는 `updated_at default now()`만 있고 update 트리거 없음. upsert do update 시 updated_at이 안 바뀜. RPC의 do update에 `updated_at = now()` 명시 필요. → **Should**

### 모델 합의도
- 합의: 0건(agy 실패로 합의 판정 불가) / Codex 단독: 8건 / Claude 추가 발견: 1건

## 3. 통합 권고 (합집합)

### 즉시 반영 (Must)
- **#1 RPC EXECUTE 권한 제한**: `revoke execute on function fontagit.upsert_font(jsonb,jsonb) from public, anon, authenticated;` + `grant execute ... to service_role;`

### 검토 후 반영 (Should)
- #2 함수 입력 컬럼 화이트리스트(_FONT_COLS) 명시 매핑
- #3 build_alias_rows 중복/빈값 제거를 설계에 명시(기존 로직 유지)
- #4 빈 alias 배열 = delete만, insert 스킵 명시
- #5 통합 테스트에 "alias insert 실패 → fonts upsert+alias delete 롤백" 케이스 추가
- #6 업로드 실패 정책: 첫 RPC 실패 즉시 중단, 처리분 유지, slug 포함 에러 로그 후 return 3
- A. RPC do update에 updated_at = now() 포함

### 참고 (Nice-to-have)
- #7 "단일 프로세스 배치 전제(동시 업로드 없음)" 한 줄 명시

## 4. 메타데이터
- Codex 종료 코드: 0 / agy 종료 코드: 1(인증)
- Codex 리뷰: `docs/review/review-result-codex-20260715-124249.md`
- 이 통합 리포트: `docs/review/review-result-dual-20260715-124249.md`
