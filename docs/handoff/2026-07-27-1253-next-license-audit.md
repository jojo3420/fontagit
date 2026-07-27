# 세션 핸드오프 — 2026-07-27 12:53 KST

> **모드**: simple-change (docs/handoff 관례)
> **Feature**: 다음 작업 착수용 (이번 세션 작업은 전부 완료)
> **이전 세션 종결 사유**: 정상 완료 인계

## 한 줄 요약

#104(Tier B 1,110종 metadata 전체 실행)와 #107(상세 굵기별 견본+이탤릭)을 완료해 **v0.7.0으로 배포 라이브**했고, 이슈 close-백로그 이관-브랜치 정리까지 끝냈다. 다음 세션은 로드맵(#62) 데이터 기반 1순위인 **#90 라이선스 검수 잔여**부터 시작한다.

---

## 다음 세션이 가장 먼저 할 일

1. **이 핸드오프 파일을 읽는다** (`docs/handoff/2026-07-27-1253-next-license-audit.md`)
2. **`docs/progress/progress.md` 상단 2블록 + 릴리스 라인**을 읽는다 (세부는 progress-011.md)
3. **`git fetch --all --prune` + `gh pr list`**로 원격 확인 (중복 재작업 방지 관례)
4. **이슈 #90 본문**을 읽고 아래 "다음 단계 MUST"부터 시작한다

---

## 작업 컨텍스트

### 사용자 원본 요청 (이번 세션)

> "이슈 #62 확인 후 현재 가장 큰 명목이 무엇인지 찾아서 진행해보자" → #104 확정-완주. 이후 "#107 설계 착수", "prod 적용 승인", PR 듀얼 리뷰-병합-v0.7.0 배포-이슈 정리까지 순차 지시.

### 사용자 제약-금지사항 (반드시 준수)

- prod DB **쓰기**는 항상 사용자 확인 후 (조회는 자유). prod manifest apply는 `FONTAGIT_PROD_MANIFEST_ENABLED=true` + `--approved-hash` + `--approval-id` + `echo yes |` 게이트
- Tier B/C 폰트는 **외부 네트워크 요청 추가 금지** (웹 견본 미제공 정책)
- 확인되지 않은 데이터(굵기-이탤릭-라이선스)를 추정으로 표시 금지
- metadata(tags/weights)는 전면 자동 승인, **legal(라이선스)은 사람 게이트 유지** — #90 진행 시 핵심 제약

---

## 현재 상태 (2026-07-27 12:53 실측)

| 항목 | 상태 |
|---|---|
| 라이브 | fontagit.com = **v0.7.0** (main `3075778`, 태그 푸시됨). 지원 굵기 섹션 Tier A/B 렌더 실측 확인 |
| 데이터 | prod Tier B 1,110종: weights 1,075-tags 895, published 1,240 불변. dev 동일 |
| 브랜치 | develop `4abd1e0`(정본, 클린), main=v0.7.0. 작업 브랜치-유령 워크트리 전부 정리됨 |
| 이슈 | #104-#107 close. 백로그: **#114**(감사 체인 보강), **#115**(상세 견본 보강). 로드맵 #62에 기준선 코멘트 갱신 |
| 검증 | vitest 242 / pytest 283 / SSG 2,508p / SEO 1,256 URL 전부 그린(배포 시점 실측) |

## 결정 사항 (뒤집으려면 사용자 확인)

| # | 결정 | 근거 |
|---|------|------|
| 1 | manifest 적용은 청크 분할(build `--chunk-size 100`)이 표준 경로 | 1,073건 단일 트랜잭션은 statement timeout 57014. RPC 무수정 원칙 |
| 2 | prod REST in-list 배치는 40 (audit_store) | ollidam 게이트웨이가 URL 3.7KB(UUID 100개)를 502 거부 |
| 3 | 견본 행 SSoT는 정규화 variants 조합(confirmedWeights는 개수-헤더 전용) | 이탤릭 전용 굵기의 합성 견본 방지 (사용자+codex 합의) |
| 4 | 이탤릭은 확인된 조합 전부 노출, 미확인은 배지만 | 사용자 결정 |
| 5 | 병합은 squash, 릴리스는 develop→main PR 승격(#116 방식) 후 태그-deploy.sh | v0.6.0 관례 유지. gh `--auto` 병합은 이 저장소 비활성 |

## 블로커-미해결 이슈

| # | 이슈 | 영향 | 다음 시도 |
|---|------|------|----------|
| 1 | ⚠️ agy CLI가 request-pr-dual에서 2회 연속 무효(헤드리스 권한 자동 거부: "command permission auto-denied") | 듀얼 리뷰가 Codex 단독 Degraded로 동작 | `~/.gemini/antigravity-cli/settings.json`의 permissions.allow 점검 또는 스킬 수정 |
| 2 | ⚠️ PR #112 수동 확인 잔여: 모바일(375px)-네트워크 차단 시나리오 실기기 미확인 | 낮음(데스크톱 라이브 확인 완료) | 실기기 확인 후 이상 시 #115에 추가 |
| 3 | 기존 lint 오류 2건(CompareLazy.tsx, page.test.tsx — develop 유래) | 전체 lint 그린 불가 | 소규모 정리 커밋 |

## 다음 단계 (Next)

**MUST** (다음 세션 본작업):
- [ ] **#90 라이선스 검수 잔여 착수** — KOGL 271종, custom-free 1,110종, 눈누 대조 44건. legal은 사람 게이트 유지 제약 하에 검수 플로우 설계(brainstorming→spec)부터. 참고: 감사 하이브리드 재개점 메모리, OFL 자동 verified 선례(ofl_verify.py)
- [ ] 착수 전 #96(Tier A download_url 백필 필요성)과 우선순위 1회 확인 — 로드맵 코멘트 참조

**SHOULD**:
- [ ] #114 감사 체인 보강(청크 무결성 단정, 다중 청크 테스트, deploy.sh .next 캐시 정리 등)
- [ ] #115 상세 견본 보강(variable font weight 범위, 실패 link 재시도, officialUrl 검증, SpecimenBox 타입)
- [ ] 블로커 #1(agy) 점검, 블로커 #3(lint 2건) 정리

**NICE-TO-DO**:
- [ ] 기술부채 백로그 #3, #84, #105

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| 진행 일지 | `docs/progress/progress.md` (상단), `docs/progress/progress-011.md` (시행착오 7건) |
| 감사 체인 | `scripts/audit-chain.sh`, `apps/pipeline/src/fontagit_pipeline/audit_manifest.py` |
| 상세 견본 | `apps/web/components/DetailSpecimenPanel.tsx`, `WeightSpecimenSection.tsx`, `apps/web/lib/weightLabels.ts` |
| 스펙-리뷰 | `docs/superpowers/specs/2026-07-27-font-detail-weights-italic-design.md`, `docs/review/pr-review-11{2,3}-dual-20260727.md` |
| 배포 함정 | 메모리 `ref-deploy-pitfalls.md` (main 전용, .next 캐시) |

---

## 재개 프롬프트 (다음 세션에 그대로 복사-붙여넣기)

```
이전 세션의 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/handoff/2026-07-27-1253-next-license-audit.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. docs/progress/progress.md 상단 2블록을 읽는다
3. git fetch --all --prune && gh pr list 로 원격 상태 확인
4. 핸드오프의 "다음 단계 → MUST"(#90 라이선스 검수 착수, #96과 우선순위 확인)부터 시작
5. 제약 준수: prod 쓰기는 사용자 확인, legal 승인은 사람 게이트, Tier B/C 외부 요청 금지
6. 결정 사항 표(청크 100, in-list 40, squash-릴리스 PR 관례 등)는 뒤집지 않음

진행 전에 핸드오프 파일을 읽었음을 확인하고, 어디부터 시작할지 한 줄로 보고해주세요.
```

✅ 핸드오프 메모 작성 완료. 다음 세션은 위 재개 프롬프트로 시작.
