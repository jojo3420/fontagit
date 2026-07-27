# progress-013: 라이선스 검수 + 크롤 고도화 (2026-07-27)

## 맥락

#120(사용자 신고): fontagit.com 나눔명조 상세에서 제작사-공식출처-원문보기가 전부 구글폰트로 표시. 구글폰트는 제작 주체가 아니라 재배포 아카이브이므로 잘못된 출처 정보. 라이선스 신뢰가 서비스 핵심 가치라 우선 처리. 여기에 #90(눈누 proposed 44건/KOGL 271 후보/크롤 오류 22종 검수), #96(Tier A download_url 전량 null), #114(manifest 청크 무결성 가드)를 한 사이클로 통합.

## 구현 요약

### 데이터 모델: 출처 등급 3단계

- 등급: `official`(제작사) > `public`(공공기관) > `archive`(재배포처: 구글폰트, GitHub, 눈누) > null
- `audit_policy.may_update_source_kind(current, proposed)` — 같거나 높은 등급만 갱신 허용, 등급 체계 밖 값(discovery)은 fail-closed 거부
- `audit_policy.AUTO_APPLICABLE_SOURCE_KINDS = {official, public}` — archive는 항상 사람 검수
- 마이그레이션 0021(fonts.download_source_kind CHECK에 archive 추가), 0022(apply RPC의 `_audit_manifest_value_valid`에 archive 추가 — 0021만으로는 적용이 100% 차단됨)
- `license_source_kind`는 archive 미허용 유지(아카이브 근거로 라이선스 자동 승인 금지)

### 신규 모듈

- `tier_a_meta.py`: google/fonts METADATA.pb에서 designer/copyright 파싱 → `extract_rights_holder()`로 권리사 추출 → `resolve_foundry()`가 눈누 표기와 대조(일치 시 auto, 아니면 needs_review). specimen 페이지를 archive 등급 download_url fallback으로 제안. `data/brand_normalization.json`(원본명-표시명-근거URL-검수상태) 보유
- `audit_kogl.py`: `detect_kogl_type()` 공공누리 제1~4유형 판별. 복수 검출/부정문/빈값은 전부 미검출. `KOGL_PERMISSIONS` 4유형 x 6권한 필드(allow_embedding은 None — 승인 시 확정)
- CLI 2종: `font-audit-tier-a-meta`(dry-run 시 findings 상세 리포트), `font-audit-kogl-preview`(DB 쓰기 없음)

### 기존 모듈 변경

- `audit_metadata.compare_metadata`: foundry/download_url/download_source_kind findings 생성. 파일 직링크(.ttf/.otf/.woff/.woff2/.zip) 제외
- `audit_manifest`: 청크 분할 시 `_validate_chunk_references`로 evidence/finding 참조 무결성 단정, 강등 엔트리 스킵 집계, 빈 entries를 ManifestError로 변환
- `__main__` auto-approve: fail-closed — evidence_id 없음/스냅샷 미발견/값 불일치는 승인하지 않음. `auto_applicable` 기본값 False

### 웹

- `lib/specimenPhrases.ts`: 분류 5그룹 x 6문구 = 30개, slug djb2 해시로 결정적 선택(SSG hydration 안전), `nextPhrase`로 순환
- `DetailSpecimenPanel`: 한국어 verified 폰트만 문구 풀 적용(그 외는 기존 글리프 확인 문구 유지), "다른 문구" 버튼
- `LicenseSummaryCard`: `downloadSourceKind === "archive"`면 CTA 라벨 구분

## 시도와 실패 (원인 포함)

1. **KOGL preview 집계 28 → 1건 급감**: 페이지네이션(range 루프)만 추가했더니 오히려 검출이 줄었다. 원인은 폰트당 metadata 스냅샷이 평균 2건(2,230건/1,110종)인데 `collected_at`이 전량 NULL이라 정렬이 무의미 → first-wins가 license_text 없는 스냅샷을 선택. license_text 보유 건 우선 선택으로 31건 회복(제1유형 27 + 미검출 4)
2. **"KOGL 271종" 기준 오해**: 271은 출처 도메인 기반 후보 수이고, 라이선스 본문에 공공누리 언급이 실재하는 건 31건. 나머지는 본문 미확보라 재크롤 전 유형 확정 불가
3. **license_proposals에 license_text 없음**: raw_permissions JSONB 구조이고 proposed_license_type은 전량 custom-free. 라이선스 본문의 유일한 소스는 `font_source_snapshots.extracted.license_text`
4. **confidence="archive"가 DB CHECK 위반**: 0017의 findings.confidence는 official/public/reference/unverified만 허용. archive는 링크 등급이지 근거 신뢰도가 아니므로 "reference"로 해결(스키마 변경 회피)
5. **discovery 처리에서 URL 축 우회 경로**: 등급 밖 출처의 kind draft만 막으면, 이미 official인 폰트에 미검증 URL이 들어가 링크와 등급 표시가 어긋난다. 현재 등급이 없을 때만 URL 제안하도록 좁힘

## 결정 근거와 기각된 대안

| 결정 | 기각안 | 근거 |
|---|---|---|
| download_url = 다운로드 페이지 URL | 폰트 파일 직링크(#96 원안) | 사용자 결정. 제작사 페이지 맥락(약관-최신 버전-설치 안내) 보존. 파일 후보는 font_file_candidates 소관 |
| 컬럼 1개 + download_source_kind로 등급 구분 | official용-fallback용 컬럼 2개 | 화면 버튼이 1개뿐이라 두 링크 저장은 YAGNI. 원천 링크는 감사 증거에 남음 |
| confidence="reference" + review_reason에 archive 명시 | findings.confidence CHECK에 archive 추가 | 스키마 표면적 최소화. 되돌리기 쉬움 |
| 견본 문구 = 자체 풀 30개 + slug 해시 | 눈누 견본 문구 크롤 수집 | SSG 결정적 렌더 보장, 전 폰트 커버, 재크롤 불필요. 수집안은 백로그 |
| 견본 그룹 기준 = category | 스펙의 "태그 그룹별" | 웹 Font 타입에 tags 미노출(실측). category가 대표 분류 |

## 미완 (fail-closed, 데이터 오염 위험 없음)

- **#131**: Task3/4 findings는 evidence role 불일치로 manifest 적용 불가. `_evidence_role_is_valid`가 download_*에 `document_kind='download'` + official/public을 요구하는데 실제로는 noonnu/metadata 스냅샷(confidence=reference)이 붙음. noonnu 예외는 tags/weights/script에만 존재. tier_a_meta는 evidence_id=None이라 승인 시 `build_manifest`가 실패
- 현재 도달 불가한 이유: `source_registry.json`에 official/public 엔트리 0건(archive 3 + discovery 1)이라 auto_applicable이 항상 False. 사람 승인 시 발현
- mypy strict `__main__.py` 41건(라이브러리 코드 9건은 해소), 0022 트랜잭션 스타일

## 재현-검증 명령어

```bash
cd apps/pipeline
uv run pytest -q                      # 309 passed, 4 skipped
uv run ruff check src tests           # All checks passed
uv run python -m fontagit_pipeline font-audit-tier-a-meta --limit 200 --dry-run --out /tmp/t.json
jq -r '.findings[] | select(.name_en|test("Nanum Myeongjo")) | "\(.field_name): \(.before_value) -> \(.proposed_value)"' /tmp/t.json
# foundry: null -> 네이버 / foundry_url -> hangeul.naver.com/fonts
uv run python -m fontagit_pipeline font-audit-kogl-preview --out /tmp/k.json   # type_1=27 undetected=4
cd ../.. && pnpm --filter web test    # 255 passed
```

## 리뷰 이력

Task별 리뷰 8회(Critical 15건) + 적대적 셀프 리뷰 + 최종 브랜치 리뷰(Opus). 최종 리뷰 Critical 3건(confidence 제약, RPC 검증자 미확장, 무증거 자동 승인)과 Important 10건 수정 후 재리뷰에서 N1(등급 밖 URL 오염 경로) 1건 추가 반영. 리포트: `docs/review/adversarial-review-20260727.md`, `docs/review/review-result-dual-20260727-141527.md`, `docs/review/review-result-20260727-143848.md`
