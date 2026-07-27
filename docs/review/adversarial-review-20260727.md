# 적대적 셀프 리뷰: 통합 설계 + 구현 계획 2건

> Generated: 2026-07-27 15:20 KST
> 방식: Claude 자체 공격 패스 + deep-reasoner(Opus) 독립 공격 패스 → 크로스 검증(코드 실측 대조)
> 대상: `docs/superpowers/specs/2026-07-27-license-audit-crawl-design.md`, `docs/superpowers/plans/2026-07-27-license-audit-pipeline.md`, `docs/superpowers/plans/2026-07-27-web-attribution-specimen.md`
> 기준 코드: `feature/90-license-audit-crawl` (origin/main 1789b4e)

## 확정 결함 (계획서에 반영 완료)

| # | 결함 | 출처 | 근거 | 반영 |
|---|------|------|------|------|
| 1 | 파이프라인 Task1 테스트-구현 코드의 ManifestBundle 필드 접근이 실제 구조와 불일치 | deep-reasoner | 실측: `ManifestBundle{forward/reverse: FontAuditManifest, *_sha256}`, `FontAuditManifest{entries, evidence_bundle(snapshots/findings dict)}` (audit_manifest.py:239,368-373). 계획의 `chunk.evidence`/`chunk.findings`는 존재하지 않음 | Task1 코드 전면 교체(`chunk.forward.evidence_bundle.snapshots` 등) |
| 2 | archive 등급 차단 지점 누락: `_SOURCE_KIND_FIELDS` 값 검증자(audit_manifest.py:432-434)가 {'official','public'}만 허용 | deep-reasoner | 계획 Task2는 `_evidence_role_is_valid`(:130-167)만 수정 대상으로 지정 — :432 미수정 시 archive 값 전부 ManifestError | Task2 Step4에 :432 확장 추가 |
| 3 | 눈누 download_candidates에 파일 직링크 혼입 시 스펙 규칙("download_url = 페이지 URL") 위반 경로 | Claude | 스냅샷 download_candidates는 출처 무관 후보 목록(audit_noonnu.py:29-33) — 필터 없으면 .ttf/.zip이 download_url로 승격 가능 | Task4에 확장자 필터(.ttf/.otf/.woff/.woff2/.zip 제외) 추가 |
| 4 | auto-approve의 승인 필드 화이트리스트 존재 여부 미실측 — foundry/download_* findings가 자동 승인 단계에서 무시될 수 있음 | Claude(deep-reasoner 요청 항목이나 미검증 반환) | `font-audit-review auto-approve`(__main__.py:1356)의 필드 제한은 아직 아무도 실측하지 않음 ⚠️ | Task4에 실측-확장 스텝 추가(구현 시 확인 강제) |
| 5 | 웹 Task1 테스트 제목이 단언하지 않는 내용("다른 slug 분산")을 주장 | Claude | 해당 테스트는 결정성만 단언 | 제목 수정 |

## 기각한 지적 (반론)

- deep-reasoner #3, #4, #5, #6, #7 "함수/파일/필드 미구현-미존재": 계획서가 **생성을 지시하는 산출물**을 "현재 코드에 없음"으로 오판. 계획 문서의 본질상 결함 아님.
- deep-reasoner #10 "allow_embedding DB 컬럼 존재 불확실": 기각 — `_PERMISSION_FIELDS`(audit_manifest.py:77-84)에 `allow_embedding` 실존을 이 세션에서 이미 grep으로 확인함.
- deep-reasoner #9 "dev 스키마 실측 필요": 계획 Task5 Step1이 이미 OpenAPI 선실측을 명시 — 중복 지적.

## 검증 통과 (전제 확인됨)

- `ManifestEntry.evidence_ids/finding_ids` 실존(audit_manifest.py:199-200) — Task1 검증 로직 성립
- `FindingDraft` 필드 실측(audit_store.py:39-49) — Task3/4 생성 패턴 확정, 계획서에 필드명 명기함
- LicenseSummaryCard.tsx:55 ctaLabel, mappers.ts rowToFont — main 병합(#118) 이후에도 위치 유지, 웹 Task3 성립
- spec의 등급 규칙-legal 게이트-prod 게이트와 계획 스텝 간 모순 없음(kogl-preview는 DB 쓰기 없음 명시 확인)

## 잔여 주의 (구현 중 확인)

- `font-audit-run --require-slug`의 정확한 동작(단일 slug 강제 vs 필터)은 Task5 실행 전 __main__.py:1297 실측
- google/fonts 디렉터리명 불일치 폰트(METADATA.pb 404)는 skip-리포트 경로로 흡수됨(Task3 설계대로)
