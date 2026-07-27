# progress-011: Tier B 1,110종 metadata 전체 실행 + 상세 굵기별 견본 기능 (2026-07-27)

## 맥락
컬렉션 확장의 남은 절반(전체 1,110종 metadata run, 이슈 #104)과 그 데이터를 화면에 반영하는 기능(이슈 #107)을 한 세션에 완주. #104는 파일럿(47종, PR #102) 검증 완료 상태에서 무인 체인화 + 전량 실행, #107은 브레인스토밍→스펙(codex 리뷰)→8태스크 plan→subagent-driven 구현.

## 구현 요약
- `scripts/audit-chain.sh`(신규): 7단계 무인 체인(baseline→bootstrap→bootstrap-apply→docker 감사→auto-approve→manifest build→apply dev). `--run-id` 재개, Tier B 수 자동 산출(jq `.entries[].current.source_tier`), 시딩 RPC 재적용은 'provider key collision' 감지로 멱등 스킵.
- manifest 청크 분할: `audit_manifest.py` `split_manifest_into_chunks`/`write_chunked_manifest_bundles` + build `--chunk-size`. 청크별 자기완결(참조 evidence만 포함) + 개별 sha. index.json 산출.
- `audit_store.py` in-list 배치 100→40 (prod ollidam 502).
- web(#107): `lib/weightLabels.ts`(variants 4형태 정규화-이탤릭 판정-weights 정규화), `Font.confirmedWeights?/variants?`(optional — 픽스처 회귀 방지), `resolveDetailFontPreview`(Tier A만 ital,wght CSS2), `DetailSpecimenPanel`(클라 래퍼: 문장 상태+시트 1회 로드 Promise 캐시+document.fonts 실로드 검증+5s 타임아웃), `WeightSpecimenSection`(표시 전용, 행 SSoT=variants 조합, font-synthesis:none), SpecimenBox controlled 모드, page.tsx는 서버 컴포넌트 유지.

## 시도와 실패 (재발 방지)
1. apply RPC에 1,073건 단일 트랜잭션 → **57014 statement timeout** (파일럿 47건만 통과 가능했던 구조, 엔트리당 evidence 번들 전체 jsonb 스캔 O(N²)). 해법=빌드 단계 청크 분할(RPC 무수정).
2. prod ollidam 게이트웨이가 UUID 100개 in-list URL(3.7KB) **502 거부** — aliases 502(PR #19)와 동일 패턴. 배치 40으로 축소.
3. deploy 시 **stale `.next` fetch-cache**로 sitemap이 옛 컬렉션 3개만 포함(HTML은 10개 — 비대칭이 신호) → SEO 게이트 실패. `rm -rf apps/web/.next` 후 성공. deploy.sh 캐시 정리 후속 제안(PR #113 본문).
4. bash 한글 인접 변수(`$var종`)가 비UTF8 로케일에서 unbound variable — `${var}종` 필수(deploy.sh dd7381f 재발).
5. 서브에이전트가 브리프 코드를 임의 변경(weight 범위 축소, Tier B combos 반환, familyName을 CSS 폴백 문자열로) — 태스크별 독립 리뷰어가 전부 검출, 5회 수정. "브리프 verbatim" 지시만으로 부족, 리뷰 게이트 필수.
6. 감사 4단계는 Linux 게이트라 docker(fontagit-pipeline:local) 필수, 스크립트 실행 비트(chmod +x)와 deploy.sh main 브랜치 가드 주의.

7. 릴리스 승격(develop→main) 시: (a) gh pr merge `--auto`는 이 저장소에서 비활성(직접 merge 필요), (b) main 전용 핫픽스와 develop 백포트로 progress.md 병합 충돌 발생 → main을 develop에 역병합해 해소 후 승격, (c) `.worktrees/`의 유령 워크트리가 develop 체크아웃을 잠가 `git worktree remove` 선행 필요.

## 결정 근거와 기각된 대안
- timeout 해법: psql 직접 접속(터널) 기각 — 무인 체인의 재사용성(레거시 경로 회피, dev/prod 동일 경로) 때문에 청크 채택.
- crawl-all 재사용 기각: `--stage legal` 전용. metadata 전체는 font-audit-run --limit <전수>가 유일 경로.
- #107 이탤릭: 대표 1행/토글 기각, 사용자 결정=지원 조합 전부 노출. 배치=별도 섹션(SpecimenBox 불침습).
- 견본 행 SSoT=variants 조합(confirmedWeights 기각) — 이탤릭 전용 굵기에서 합성 견본 방지(codex 리뷰 반영).

## 재현-검증 명령어
```bash
./scripts/audit-chain.sh                     # dev 전체 체인 (~2h)
./scripts/audit-chain.sh --run-id <uuid>     # 재개(빌드부터, 멱등)
# prod: build --target prod --chunk-size 100 후 청크별 apply(FONTAGIT_PROD_MANIFEST_ENABLED=true, --approved-hash, --approval-id, echo yes |)
pnpm --filter web test && pnpm --filter web lint && pnpm --filter web build
```
검증 실측: dev/prod Tier B weights 1,075-tags 895, published 1,240 불변, SEO 1,256 URL(collections 10), pytest 283 passed, vitest 242 passed.
