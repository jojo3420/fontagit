# PR #101 리뷰 최종 리포트 (Codex + Claude 크로스 리뷰)

> 생성: 2026-07-23 - PR: https://github.com/jojo3420/fontagit/pull/101 - develop ← feature/collections-phase0-exec
> Codex 원문: `pr-review-101-codex-run.md` - Codex 종합 5.5/10(Must-fix 존재) - **머지 결정: 차단(BLOCKED)**

## 크로스 리뷰 판정 (실코드 대조)

### Must-fix (동의 → 머지 차단)
| 파일:라인 | 문제 | Claude 판정 | 근거(실코드) |
|---|---|---|---|
| audit_store.py:798,823,831 | 페이지네이션 부재 — 세 조회 `.select("*").execute()` 단발, `.range()/.limit()` 없음. Supabase 기본 1,000행 제한으로 (1)full run findings 1,000+ 초과 시 silent partial manifest, (2)`fonts` 전체(1,240) 로드→1,000 잘림→대상 폰트 누락 시 build_manifest "finding font has no current row" 오류(파일럿도 위험) | **동의(Must-fix)** | 798/823/831 모두 range/limit/order 없음 확인. 823은 전체 fonts 로드 후 in-memory 필터라 잘림에 취약 |

**수정 방향**: fonts는 `.in_("id", font_ids)`로 run 대상만(1,000 초과 시 청크). findings/snapshots는 안정 정렬 + `.range()`로 끝까지 조회 + 개수 검증(부분 조회 시 즉시 중단).

### Should-fix (동의)
| 파일:라인 | 문제 | 판정 |
|---|---|---|
| test_task3_integration.py:151~ | "비타우톨로지 통합테스트"가 실제 헬퍼(get_current_fonts_with_snapshots 등) 미호출 — SupabaseAuditStore import 안 함, `_make_font`가 출력형식 직접 구성 후 build_manifest만 호출. Task3 정합이 자동테스트로 미증명(수동추적으로만 확인) | 동의 — 실제 헬퍼(mock DB) → build_manifest 연결 테스트로 교체 필요 |
| audit_store.py:845~871 | source_key가 `if "source_key" not in`으로 첫 snapshot만, 복수 snapshot 충돌 미검사, 오래된/None 값 방치 | 동의 — snapshot의 (provider,provider_record_id) 유일성 검증 후 항상 그 값 사용, 충돌 시 RuntimeError |
| audit_store.py:496~558 | approve_finding이 stage=="metadata"/비어있지 않은 reviewed_by 미강제, UPDATE가 id+status만 조건(검증↔갱신 사이 TOCTOU) | 동의 — 사전 강제 + UPDATE에 stage/field 조건 추가 |
| test_main.py:260 | 기존 테스트의 `mock_write.assert_called_once()`+`assert result==3` 삭제로 약화 | 동의 — 복원 + 신규 테스트 분리 |
| test_audit_store.py:80~230 | 조건부 승인 테스트가 UPDATE 조건 미검증("예외 없음"만) — `.eq("status","needs_review")` 삭제돼도 통과 | 동의 — UPDATE payload/조건 명시 검증 |

### Medium (동의, 후속 가능)
- __main__.py:697 예외 클래스만 로깅(원인 추적난) → 안전 메시지+traceback / 예외 세분화.
- audit_store.py 반환행 Mapping/필드 검증 부재.
- select("*") 불필요 컬럼(raw_text 포함) → 필요 컬럼만(페이지네이션과 함께).
- test 예외 검증에 pytest.raises(match=) 사용.

## 비동의/패스
- 없음(모든 지적이 실코드에서 확인됨).

## 최종 권고
- **머지 차단**: Must-fix(페이지네이션) 1건 동의. 파일럿(50종)도 fonts 잘림 위험이 있어 파일럿 전 수정 필요.
- 통합테스트 타우톨로지(Should-fix)는 Task3 정합 증명 공백이라 함께 수정 권장.
- 나머지 Should-fix/Medium은 견고성/테스트 품질 향상.
