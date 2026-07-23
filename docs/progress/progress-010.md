# progress-010: metadata 무인 승인 + 감사 파이프라인 라이브 파일럿 완주 (2026-07-23)

## 맥락 (이 작업이 왜 필요했나)
컬렉션 확장 0단계의 목표는 Tier B 폰트 1,110종의 tags/weights 결측을 감사 파이프라인으로 채우는 것. 조립 코드는 PR #99+#101로 병합됐지만 (1)metadata 승인 CLI가 없었고 (2)전 구간이 mock으로만 검증돼 실DB에서 한 번도 안 돌았다. 사용자 거버넌스 결정(2026-07-23): metadata(tags/weights)는 per-finding 사람검수 없이 **전면 자동화**, 파일럿 1회만 apply 전 확인, legal은 사람 게이트 유지.

## 구현 요약 (무엇을 어디에)
- `font-audit-review auto-approve --run-id`: run 단위 무인 승인(reviewed_by=auto), 일부 실패 시 exit 3으로 체인 중단 (`__main__.py`, `audit_store.approve_finding/get_proposed_findings`)
- 마이그레이션 `0019_audit_manifest_run_agnostic_evidence.sql` (dev+prod 적용됨): evidence를 콘텐츠 기준으로 통일 — RPC content-conflict에서 run_id 비교 제거, INSERT는 매니페스트 run으로 FK 충족, tags/weights의 noonnu font-file-script reference 증거 경로 허용. 0018 대비 diff 3+3곳으로 최소화
- `get_current_fonts_with_snapshots`: run_id 필터 → **evidence_id 기준** 재작성(+`target_store` 인자로 prod 대상 모드 — current/expected_updated_at을 적용 대상 DB에서 조회, 스냅샷/finding을 대상 폰트로 재바인딩)
- font_sources 시딩 경로 신설: `font-audit-export-baseline --source dev-service`(published 필터) + `font-audit-bootstrap-apply --target dev|prod`(신형 22필드 산출물을 구형 RPC 7필드 계약으로 투영, prod는 FONTAGIT_PROD_MANIFEST_ENABLED 게이트)
- 파일럿 대상 선정: metadata stage는 Tier B만 (`main_audit_run`)

## 시도와 실패 (원인 포함) — 라이브 파일럿이 실증한 결함 13건
1. 기본 font_fetcher lambda가 max_bytes 키워드 미수용 TypeError — linux 라이브 전용 경로라 mock 불가탐, `Callable[...]`로 mypy 무력 (fix 20dca6f)
2. 파일럿 50종에 Tier A 24종 혼입 → 전원 AuditInputError → broken 50% 게이트 발동(게이트 자체는 정상 작동)
3. approve 경로 실스키마 불일치: findings에 stage 컬럼 없음(42703 실측), needs_review는 status 체크 제약상 불가값 — 실제 저장은 전부 proposed. mock만 통과하던 코드 (845b2b0)
4. 스냅샷 `_insert_once` dedup(unique normalized_sha256)이 과거 run 행 재사용 → run_id 필터가 evidence 25/47 누락 (8dde877)
5. build/Bundle/RPC의 "snapshot run_id==run" 강제가 dedup과 구조적 모순 → 0019로 근본 해결(사용자 A안 선택)
6. tags/weights의 noonnu reference 증거를 script 필드만 허용하던 검증기 (631f3ac)
7. bootstrap 산출물 DB 적용 CLI 부재(RPC 호출처 0) + prod 기준 산출물이라 dev precondition 거부
8. 클라우드 PostgREST는 총량 초과 Range에 416(자체호스팅 prod는 관대) — exact count 종료로 교정
9. dev service 키는 RLS 우회라 미공개 54종 혼입 → published 명시 필터
10. 신형 bootstrap 22필드 vs 구형 RPC 7필드 계약 괴리 → CLI 투영 계층
11. dev apply가 findings를 applied로 전이 → prod 재조립 시 approved 조회 0건 → applied 포함+정규화
12. prod build에서 스냅샷/finding의 dev font_id가 prod current rows와 미매칭 → 대상 재바인딩
13. apply/auto-approve 성공 로그 미출력(코스메틱) → apply가 "조용히 성공"해 재시도 혼선 유발. 미수정, 후속 1순위
- ⚠️worker 사고 1건: 0019 1차 산출에서 status='applied' 전이 줄 삭제+재포매팅 — 컨트롤러 diff 검증으로 잡아 복원(82af234). SQL 위임 시 함수 diff 증명 필수.

## 결정 근거와 기각된 대안
- 무인 승인(사용자 결정): per-finding/batch 사람검수 기각 — 자동화 목적과 충돌. 안전장치=자동 게이트(assert_safe broken 10%, published 불변, apply RPC 단일 경로, 멱등성 stale updated_at)
- 0019(A안) vs 승인 시 재스탬프(B안): B는 1,110 확장 prod 적용 시 content conflict 재폭발이라 기각
- bootstrap RPC 계약: DB 재변경 대신 CLI 투영 — RPC가 대상 DB 대조로 재검증하므로 안전성 동일

## 재현-검증 명령어
```bash
# dev 체인 (apps/pipeline에서)
uv run python -m fontagit_pipeline font-audit-export-baseline --source dev-service --out output/audit/dev-baseline.json
uv run python -m fontagit_pipeline font-audit-bootstrap --prod-snapshot output/audit/dev-baseline.json --out output/audit/dev-bootstrap-manifest.json
uv run python -m fontagit_pipeline font-audit-bootstrap-apply --manifest ... --target dev --confirm-hash <sha256>
docker run --rm -v "$(pwd):/repo" -w /repo/apps/pipeline fontagit-pipeline:local python -m fontagit_pipeline font-audit-run --stage metadata --bootstrap ... --limit 50 --out ...
uv run python -m fontagit_pipeline font-audit-review auto-approve --run-id <run>
uv run python -m fontagit_pipeline font-audit-manifest build --run-id <run> [--target prod] --out <dir>
uv run python -m fontagit_pipeline font-audit-manifest apply --manifest .../forward.json --sha256 .../forward.sha256 --target dev --confirm-hash <sha>
# prod apply는 추가로: FONTAGIT_PROD_MANIFEST_ENABLED=true + --approved-hash + --approval-id + 대화형 yes
# 검증: 전체 테스트 uv run pytest (272 passed, 4 skipped=linux전용)
```
결과 실측: 파일럿 run 11b51d56 — 감사 50종(broken 3=6%), 승인 89건, dev/prod 각 47종 tags 47/47 + weights 42/42 일치, findings 89 applied.
