# progress-014: Tier A 제작사/다운로드 prod 반영과 적용 경로 결함 3종 (2026-07-28)

## 맥락

2026-07-27 세션에서 Tier A 감사 findings 291건을 만들어 사람 승인까지 마쳤으나, dev 적용이 `finding UUID content conflict`(P0001)로 291건 전량 실패했다. 이 세션의 목표는 원인 규명 후 dev/prod 적용을 완료해 #96과 #120 문제점 1번(제작사가 구글폰트로 잘못 표기)을 해소하는 것이었다.

## 구현 요약

### 결함 1: SQL NULL vs jsonb 'null' 오탐 (마이그레이션 0025, PR #139)

291건 전량이 단일 원인으로 충돌했다. 12개 비교 필드 중 `before_value` 하나만 291/291 어긋났고, 값 차이가 아니라 **표현 차이**였다.

- 파이프라인 writer(`audit_store.py`)는 Python `None` → PostgREST → **SQL NULL**로 저장
- manifest는 JSON 파일이라 **jsonb `'null'`** 리터럴로만 표현 가능
- RPC 충돌 검사가 원시 비교 (`null::jsonb is distinct from 'null'::jsonb` = true)

같은 함수의 entries 검사는 `_audit_font_value`(0018:79)가 `coalesce(...,'null'::jsonb)`로 정규화해 정상 동작했다. findings/snapshots 루프만 누락이었다.

과거 apply 성공 1,769건은 전부 before_value에 실제 값이 있어 미발현. dev 실측으로 `applied & before SQL NULL = 0`건 확인 — NULL-before 클래스는 한 번도 통과한 적이 없다.

수정 4종: findings/snapshots 비교를 양쪽 `coalesce` 정규화, 예외 메시지에 `id=%, field=%` 추가, insert 값을 `nullif(...,'null'::jsonb)`로 SQL NULL 단일화.

### 결함 2: 사전 진단 수단 부재 (PR #140)

예외 메시지가 `finding UUID content conflict`뿐이라 291건 중 무엇이 왜 틀렸는지 알 수 없어 원인 규명에 세션 2개가 들었다. `font-audit-manifest preflight` 신설 — manifest와 DB를 RPC와 동일 의미론으로 필드 대조하고, apply의 기본 게이트로 배선(어긋남 시 RPC 호출 전 exit 2, `--skip-preflight`로만 생략).

리뷰에서 CRITICAL 1건 지적: 신규 insert 예정 행은 `source_key`→`font_sources` 해석 검증을 건너뛰어, 첫 감사 run(전부 신규)에서 preflight가 무의미해지는 거짓 통과. 수정 후 재검증 통과.

### 결함 3: dev-only 폰트가 prod 빌드 전체를 차단 (PR #143)

`get_current_fonts_with_snapshots`가 대상 DB에 없는 폰트를 RuntimeError로 처리해, dev에만 있는 2종(Fraunces, Orbitron) 때문에 나머지 126종까지 막혔다. prod 실측 결과 두 폰트는 fonts 행 자체가 없다(dev/prod 폰트 목록이 다른 건 정상).

수정: `target_store` 지정 시에만 누락을 제외 처리, 중복 매칭(2행+)은 계속 예외. 리뷰 HIGH 2건 반영 — `excluded_out`을 필수 파라미터화(미래 호출부가 빠뜨리면 조용한 누락 재현), 제외 목록을 `excluded.json` 사이드카로 저장(로그에만 남던 제외 사실을 산출물에 기록).

## 시도와 실패

**잘못된 원인 지목 1**: 이전 세션에서 "청크에 entries 밖 finding이 섞였다"고 지목했으나 실측 0건으로 반증됨.

**잘못된 원인 지목 2**: 눈누 크롤 실패 22종을 조사하며 `noonnu.cc/font_page/NNN`을 curl로 쳐서 "정상 응답인데 우리만 실패"라고 판단했으나, 실제 fetch 대상은 각 폰트의 **외부 라이선스 출처 URL**(14개 서드파티 호스트)이었다. 대상을 잘못 짚은 오진.

**prod 마이그레이션 누락**: 사용자가 0025만 적용해 `manifest field or value is invalid: download_source_kind`로 실패. 0025는 apply 함수만 재생성하고 검증 함수(`_audit_manifest_value_valid`, 0022)와 테이블 제약(0021)은 이전 마이그레이션 소관. 0021~0024 적용 후 0025 재적용(0024가 같은 함수를 덮어쓰므로)으로 해결.

## 결정 근거와 기각된 대안

**null 비교 수정 위치 — SQL 검증부 선택**: 파이썬 manifest 생성부 수정은 도달 불가능한 목표다. JSON에 두 종류 null이 없고, PostgREST JSON body로 jsonb `'null'`을 저장할 수도 없다(dev 9,487행 중 jsonb `'null'` 0건 실측). 기각된 대안: (a) DB 5,312행 backfill — 감사 원본 변조 + prod 동반 변조, (b) manifest에 null 종류 sentinel 추가 — 스키마+양쪽 코드 변경 대비 이득 없음.

**제외 처리의 fail-visible 설계**: "조용한 스킵"은 이 PR이 막으려던 문제를 다른 지점에서 재현한다. 로그 경고 + 프로그램적 접근자 + 산출물 사이드카 3중으로 남기고, 중복 매칭은 진짜 데이터 오류이므로 계속 차단.

## 재현-검증 명령어

```bash
# 반사실 재현: 0025 없이 0024까지만 적용한 DB에서 회귀 케이스 실행 → conflict 재현
psql -f supabase/tests/font_audit_manifest_test.sql   # 0025 적용 후 ALL PASS

# prod 적용 (0021~0025 선행 필요)
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-manifest build --run-id <run> --target prod --out <dir> --chunk-size 100
uv run python -m fontagit_pipeline font-audit-manifest preflight --manifest <chunk>/forward.json --sha256 <chunk>/forward.sha256 --target prod
echo yes | FONTAGIT_PROD_MANIFEST_ENABLED=true uv run python -m fontagit_pipeline font-audit-manifest apply \
  --manifest <chunk>/forward.json --sha256 <chunk>/forward.sha256 --target prod \
  --confirm-hash <sha> --approved-hash <sha> --approval-id <id>
```

## 적용 결과 (실측)

| 대상 | 결과 |
|---|---|
| dev | chunk 100 + 28 = 128종, findings applied 291 |
| prod | chunk 100 + 26 = 126종, findings applied 287, `download_source_kind=archive` 126건, foundry 채워진 폰트 30건 |
| 나눔명조(prod) | `foundry: 네이버`, `foundry_url: hangeul.naver.com/fonts` |
| 제외 | Fraunces, Orbitron (prod에 fonts 행 없음) — `excluded.json` 기록 |

되돌리기용 reverse manifest 보관: `apps/pipeline/output/audit/manifest-tiera-prod-20260728/` (gitignore 대상)

## 부수 발견 (이슈로 분리)

- **#141 크롤러 결함 5종 + 데이터 오염 의심**: User-Agent 미전송으로 봇 차단에 걸림(gongu.copyright.or.kr에 35종 물림, UA 한 줄로 회복). HTTP 상태 코드만 보고 판정해 "200 OK인데 본문은 차단 안내문"을 정상 저장(89건 샘플 중 2건). 이번 run은 `verified_count=0`이라 전량 사람 게이트 앞 정지 — prod 자동 반영 없음.
- **#142 체크포인트가 실패를 완료로 기록**: `audit_runner.py:2042-2044`가 성공/실패 구분 없이 배치 전체를 완료로 기록해 재개 시 실패분이 영구 누락. 이번에 22종 재크롤을 위해 체크포인트를 손으로 수정해야 했다.
