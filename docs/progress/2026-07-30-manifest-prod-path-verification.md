# manifest prod 적용 경로 실측 검증 (#150 Task 1)

- 검증일: 2026-07-30
- 대상 계획: `docs/superpowers/plans/2026-07-30-noonnu-url-finding-ingest.md` Task 1
- 판정: **조건부 통과.** prod 이식 경로는 검증됐으나 승인 단계에 차단 결함 발견

## 1. manifest apply가 대상 폰트를 찾는 경로

**결과: 설계 3.7절이 맞다.** dev의 `font_id`를 쓰지 않는다.

`supabase/migrations/0026_manifest_official_url.sql:233-234`:

```sql
select fs.font_id into v_font_id from fontagit.font_sources fs
  where fs.provider=v_entry#>>'{source_key,provider}'
    and fs.provider_record_id=v_entry#>>'{source_key,provider_record_id}';
```

`(provider, provider_record_id)`로 `font_sources`를 조회해 대상 환경의 `font_id`를 얻는다. 이어서 `0026:237`이 `for update`로 행을 잠근다.

manifest 자체의 `source_key` 중복도 이미 검사한다(`0026:161`, `group by ... having count(*) > 1`).

## 2. provider_record_id 실측 (dev / prod)

읽기 전용 조회. 두 환경 동일 쿼리.

| 항목 | dev | prod |
|---|---|---|
| `provider='noonnu'` 소스 수 | 1,110 | 1,110 |
| `provider_record_id` 중복 | 0 | 0 |
| `provider_record_id` 빈 값 | 0 | 0 |
| 샘플 값 | `410` (`.../font_page/410`) | `394` (`.../font_page/394`) |
| 전체 식별자 집합 md5 | `ec66575df971be7cd885eb73df24aea8` | `ec66575df971be7cd885eb73df24aea8` |

**식별자 집합 해시가 완전히 일치한다.** 설계 3.7절의 미검증 2건(누락 없음, 유일성)이 모두 해소됐다.

`provider_record_id`는 `source_url`의 마지막 경로 조각과 같다. 계획 Task 3의 `provider_record_id_from_source_url` 규칙이 맞다.

## 3. 오염 현황 실측

| 항목 | dev | prod |
|---|---|---|
| `official_url` 오염 | **173** | 172 |
| `license_source_url` 오염 | 172 | 172 |

### dev의 1건 초과분

`신촌랩소디체` 1건이 추가로 잡혔다.

```
slug                = 신촌랩소디체
has_noonnu_source   = false
license_source_url  = NULL
updated_at          = 2026-07-17 15:09:52 UTC
```

**눈누 소스가 없는 폰트다.** 스캔 대상(눈누 1,110종) 밖이므로 이번 정정 범위에 들어오지 않는다. prod에는 없거나 오염되지 않았다. 다른 경로로 오염된 별개 건이므로 **별도 이슈로 분리한다.**

## 4. 승인 단계 차단 결함 (핵심)

**`official_url`은 현재 어떤 승인 경로로도 승인할 수 없다.**

`0026` 마이그레이션이 manifest 레벨에서 `official_url`을 허용 필드에 추가했으나, **Python 쪽 승인 화이트리스트는 갱신되지 않았다.**

| 상수 / 함수 | 위치 | `official_url` | `license_source_url` |
|---|---|---|---|
| `get_proposed_findings`의 `in_` 필터 | `audit_store.py:897` | 없음 | **없음** |
| `MANUAL_APPROVABLE_FIELDS` | `audit_store.py:27-37` | **없음** | 있음 |
| `derive_proposed_value` | `audit_metadata.py:667-683` | 없음 (`return None`) | 있음 (`:682`) |

정리하면,

- `font-audit-review auto-approve` (무인 승인): 대상 필드가 `{tags, weights, foundry, download_url, download_source_kind}`로 하드코딩돼 있어 **두 필드 모두 승인 불가**
- `font-audit-review approve --field` (사람 배치 승인): `license_source_url`은 가능, **`official_url`은 입력값 오류로 거부**

계획 Task 7 Step 4(`auto-approve`로 175건 승인)는 **이 상태로는 성립하지 않는다.**

## 5. 부수 확인

`auto-approve`와 `approve` 모두 run 상태가 `completed`여야 동작한다(`__main__.py:1263-1264`, `1452-1454`). 계획 Task 5의 순서(스캔 종료 후 `complete_run` 호출)와 일치한다.

`derive_proposed_value`는 snapshot의 `extracted`에서 **필드명을 키로 그대로** 꺼낸다(`audit_metadata.py:682`). 자동 승인 경로를 쓰려면 계획 Task 3의 `extracted`에 `license_source_url` 키가 있어야 하는데 현재 없다. 승인 경로 결정에 따라 함께 수정한다.

## 6. 다음 조치

승인 경로를 어떻게 열지는 사용자 결정 사항이다. 결정 전까지 Task 7 Step 4 이후는 진행하지 않는다.
