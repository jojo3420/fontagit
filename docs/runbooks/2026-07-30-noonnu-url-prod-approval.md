# prod 승인 패키지: 눈누 official_url / license_source_url 정정 (#150)

- 대상 DB: prod (`supabase.ollidam.com`, 스키마 `fontagit`)
- 기준 run: `a6a212f0-ba1e-4a49-94f7-d3ef09e8db72` (dev에 적재된 감사 run)
- forward manifest sha256: `37203d13e7bf91d0dbe85d650906a84a6125d6be149b51ec21b0e86020c553ff`
- reverse manifest sha256: `37fdcae5ce7cd4a3059fa20a02d39930c00ac24468d498f6a39aa0e17177171b`
- 산출물: `apps/pipeline/output/noonnu-url-manifest-prod/{forward,reverse}.json`
- 대상 slug 전체: `apps/pipeline/output/noonnu-url-prod-target-slugs.csv` (175행)

## 1. 무엇을 고치는가

눈누(noonnu.cc)에서 수집한 폰트의 `official_url`과 `license_source_url`이 폰트 제작사가 아니라
눈누 운영 계정(`https://www.instagram.com/noonnu_official/`)을 가리키고 있었다.
눈누 상세 페이지 본문 앵커를 근거로 제작사 실제 주소로 교체하고,
`license_source_url`은 근거가 된 눈누 상세 페이지(`https://noonnu.cc/font_page/<id>`)로 맞춘다.

## 2. 변경 규모

| 항목 | 수치 |
|------|------|
| 대상 폰트 | 175종 |
| finding(승인 완료) | 349건 |
| `official_url` 변경 | 174건 |
| `license_source_url` 변경 | 175건 |
| prod에 없는 폰트(excluded) | 0건 |
| preflight 어긋남 | 0건 |

`official_url`이 174건인 이유: `google-sans-flex` 한 종은 제작사 주소를 특정하지 못해
`official_url`을 사람 검수로 남겼다(`fonts.official_url`이 NOT NULL이라 비울 수 없다).
`license_source_url`만 정정한다.

### before 값 분포 (prod 현재 상태)

| before 값 | official_url | license_source_url |
|-----------|--------------|--------------------|
| 눈누 운영 인스타그램 | 164 | 165 |
| 그 외(typedia.kr 5종, github LICENSE 5종) | 10 | 10 |

"그 외" 10종은 제작사 페이지가 아니라 배포 플랫폼/라이선스 원문 페이지를 가리키던 건이라
같은 기준으로 제작사 주소로 교체한다. dev manifest와 before/after가 완전히 일치함을 확인했다
(source_key 집합 동일, before 불일치 0, after 불일치 0).

### 적용 후 남는 오염

prod의 눈누 인스타그램 잔존은 `official_url` 172건 → 8건이 된다.
남는 8건은 자동 정정 대상에서 의도적으로 제외한 건이다.

- `manual_review` 7종: 앵커가 여러 개거나 제작사 판별이 애매해 사람 판단 필요
- `nullify` 1종(`google-sans-flex`): 대체 URL 없음

## 3. 샘플 10건

| slug | noonnu id | before (official_url) | after (official_url) | after (license_source_url) |
|------|-----------|----------------------|----------------------|----------------------------|
| kopub바탕 | 32 | `https://www.instagram.com/noonnu_official/` | `https://www.kopus.org/biz-electronic-font2/` | `https://noonnu.cc/font_page/32` |
| kopub돋움 | 33 | `https://www.instagram.com/noonnu_official/` | `https://www.kopus.org/biz-electronic-font2/` | `https://noonnu.cc/font_page/33` |
| 타닥타닥체 | 325 | `https://www.instagram.com/noonnu_official/` | `https://tdtd.io/superboard/data/board/download/TDTDTadakTadak.zip` | `https://noonnu.cc/font_page/325` |
| neo둥근모 | 386 | `https://www.instagram.com/noonnu_official/` | `https://neodgm.dalgona.dev` | `https://noonnu.cc/font_page/386` |
| 노회찬체 | 468 | `https://www.instagram.com/noonnu_official/` | `http://hcroh.org/notice/218/` | `https://noonnu.cc/font_page/468` |
| 아인맘-손글씨 | 510 | `https://www.instagram.com/noonnu_official/` | `https://clova.ai/handwriting/list.html` | `https://noonnu.cc/font_page/510` |
| 암스테르담 | 511 | `https://www.instagram.com/noonnu_official/` | `https://clova.ai/handwriting/list.html` | `https://noonnu.cc/font_page/511` |
| 안쌍체 | 512 | `https://www.instagram.com/noonnu_official/` | `https://clova.ai/handwriting/list.html` | `https://noonnu.cc/font_page/512` |
| 아기사랑체 | 513 | `https://www.instagram.com/noonnu_official/` | `https://clova.ai/handwriting/list.html` | `https://noonnu.cc/font_page/513` |
| 바른히피 | 514 | `https://www.instagram.com/noonnu_official/` | `https://clova.ai/handwriting/list.html` | `https://noonnu.cc/font_page/514` |

## 4. 사전 조건

`apply_font_audit_manifest` RPC가 눈누 앵커 근거를 받아들이려면 마이그레이션 0026과 0027이
prod에 있어야 한다. 적용 전 prod에는 0026이 없었고 0027도 없었다.

```
0026_manifest_official_url.sql            -- official_url을 정정 가능 필드로 추가
0027_manifest_noonnu_url_evidence.sql     -- 눈누 앵커(evidence_role='noonnu-official-url-anchor')를
                                          --   official_url / license_source_url의 근거로 허용
```

적용 전 prod 함수 정의 백업: `apps/pipeline/output/prod-rollback/prod-audit-functions-before-0026-0027.sql`

## 5. 실행 명령

```bash
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-manifest preflight \
  --manifest output/noonnu-url-manifest-prod/forward.json \
  --sha256   output/noonnu-url-manifest-prod/forward.sha256 \
  --target prod

uv run python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/noonnu-url-manifest-prod/forward.json \
  --sha256   output/noonnu-url-manifest-prod/forward.sha256 \
  --target prod \
  --confirm-hash 37203d13e7bf91d0dbe85d650906a84a6125d6be149b51ec21b0e86020c553ff
```

## 6. 되돌리기

역방향 manifest를 같은 절차로 적용한다.

```bash
uv run python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/noonnu-url-manifest-prod/reverse.json \
  --sha256   output/noonnu-url-manifest-prod/reverse.sha256 \
  --target prod \
  --confirm-hash 37fdcae5ce7cd4a3059fa20a02d39930c00ac24468d498f6a39aa0e17177171b
```

RPC 정의를 되돌려야 하면 4절의 백업 SQL을 `psql -U supabase_admin`으로 재적용한다.

## 7. 검증

`scripts/verify-noonnu-url-fix.sql`을 prod에서 실행한다. 기대값:

- 오염 잔존(`contaminated_remaining`): 8 (사람 검수 7 + nullify 1)
- 정정 반영(`corrected`): 175
- 필드별 분포: `official_url` 174, `license_source_url` 175
