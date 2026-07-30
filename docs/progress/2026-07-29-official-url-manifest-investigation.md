# official_url manifest 허용 조사 - 2026-07-29

## 배경

#150의 정정 대상 필드 중 `official_url`이 `apply_font_audit_manifest`의 `v_allowed`에 없다. 이 필드는 낙관적 잠금의 대조 키를 겸하고 있어, 허용 목록에 한 줄 추가하는 것으로 끝나지 않을 수 있다는 우려가 있었다. 마이그레이션을 쓰기 전에 실제 등장 지점을 전수 확인했다.

## 확인한 지점

`official_url`은 마이그레이션에 세 가지 역할로 등장한다. 최신 함수는 `0025`다(`0025`가 `0024`의 함수를 다시 만든다).

| 위치 | 역할 | 0026에서 손대야 하는가 |
|---|---|---|
| `0025:126` | `entry.current`의 필수 키 목록. `current`는 정확히 `slug, name_en, name_ko, foundry, source_tier, official_url, status` 7개여야 한다 | 아니오 |
| `0025:151` | 낙관적 잠금. `v_existing.official_url`이 `current.official_url`과 다르면 `current identity precondition mismatch` | **예** (아래 참조) |
| `0018:493`, `0018:500` | bootstrap 경로의 `before` 형태 검증 | 아니오 (별도 함수, manifest apply와 무관) |
| `0025` update 문 | `official_url` 반영 구문 자체가 없음 | **예** |

## 발견: 낙관적 잠금이 NULL 안전하지 않다

`0025:151`은 다른 필드와 처리가 다르다.

```sql
or (not (v_entry->'before'?'name_en') and coalesce(to_jsonb(v_existing.name_en),'null'::jsonb) is distinct from v_entry#>'{current,name_en}')
or (not (v_entry->'before'?'foundry') and coalesce(to_jsonb(v_existing.foundry),'null'::jsonb) is distinct from v_entry#>'{current,foundry}')
or to_jsonb(v_existing.official_url) is distinct from v_entry#>'{current,official_url}'
```

`name_en`, `name_ko`, `foundry`는 `coalesce(..., 'null'::jsonb)`로 감싸는데 `official_url`은 감싸지 않는다. `to_jsonb(NULL::text)`는 jsonb null이 아니라 **SQL NULL**을 반환하고, `NULL is distinct from X`는 항상 참이다. 따라서 `official_url`이 NULL인 폰트는 이 검사를 통과할 수 없다.

#134가 겪은 "SQL NULL vs jsonb null 정규화" 문제와 같은 뿌리다. `0025`가 다른 필드에 대해 이를 고쳤으나 `official_url`은 당시 변경 대상이 아니어서 남았다.

### 지금 당장은 문제가 없다

prod 실측: 발행 폰트 1,240종 중 `official_url`이 NULL인 것은 **0건**이다.

```
null_official=0, has_official=1240, total=1240
```

### 그러나 우리가 문제를 만든다

#150의 정정에는 `nullify`(공식 URL을 비움)가 포함된다. 적용 자체는 통과한다.

- `before.official_url` = 오염된 URL, `after.official_url` = null
- `current.official_url` = 오염된 URL (현재 값과 일치) → 잠금 통과

문제는 그 다음이다. 적용 후 그 폰트의 `official_url`은 NULL이 되고, **이후로 그 폰트를 manifest로 다루려 하면 `current` 대조가 항상 실패한다.** 한 번은 되고 그다음부터 막히는 함정이다.

## 결론: 0026의 범위

세 가지를 함께 손댄다. `v_allowed` 한 줄 추가로는 끝나지 않는다.

1. `v_allowed`에 `official_url` 추가
2. `0025:151`의 낙관적 잠금을 `coalesce(to_jsonb(v_existing.official_url),'null'::jsonb)`로 감싸 NULL 안전하게 만든다. `before`에 `official_url`이 있으면 대조를 건너뛰는 예외는 **넣지 않는다** — `before`와 `current`에 같은 값을 담으면 통과하므로 불필요하고, 예외를 늘리면 잠금이 약해진다
3. update 문에 `official_url` 반영 구문 추가 (다른 필드와 같은 `case when v_entry->'after' ? '...'` 패턴)

적용 순서는 `0021 → 0022 → 0023 → 0024 → 0025 → 0026`이다. 건너뛰면 실패한다(#134 기록).

## 정정 (2026-07-29, 로컬 실측 후)

위 "발견"과 "결론"의 두 주장이 **실측으로 반박됐다.** Task 6 구현자가 로컬 PostgreSQL(0001~0026 적용)에서 nullify manifest를 실제로 넣어본 결과다.

- "nullify는 한 번은 적용되고 그다음부터 막힌다" → **틀림.** `fonts.official_url`은 `0001_fontagit_schema.sql`부터 **NOT NULL**이라 nullify는 애초에 UPDATE 단계에서 제약 위반으로 항상 실패한다. prod `information_schema` 재확인으로도 `is_nullable=NO`.
- "낙관적 잠금의 NULL 함정" → jsonb 의미론 자체는 맞지만(위 실측 3건 유효) **발동 조건이 성립 불가**하다. NULL인 행이 존재할 수 없기 때문이다. `0025`가 이 줄에 coalesce를 안 붙인 것은 누락이 아니라 NOT NULL 컬럼이라 불필요했던 것으로 보는 게 맞다.

내 오류의 원인: prod에서 "NULL 0건"을 확인하고도 **왜 0건인지**(제약 때문인지 우연인지)를 컬럼 정의에서 확인하지 않고 데이터 분포로만 해석했다.

추가 사실: `license_source_url`은 **nullable**이다. 두 필드의 정정 정책이 달라야 한다.

- `official_url`: 교체만 가능. 비움 불가 (제약이 안전장치)
- `license_source_url`: 정책표대로 비울 수 있음 (기존 value_valid도 null 허용)

### 수정된 0026 범위 (4곳, 잠금 변경 철회)

1. `v_allowed`에 `official_url` 추가
2. `_audit_manifest_value_valid`에 official_url **별도 분기** (`string`만 허용, null 불허 — "nullify 미지원"을 계약 수준에 새김)
3. `_audit_font_value`에 official_url case 추가 (NOT NULL이므로 coalesce 없이)
4. UPDATE 절에 official_url 반영
- ~~낙관적 잠금 coalesce~~ 철회: NULL 불가 컬럼이라 죽은 코드가 됨. 대신 테스트에 tripwire를 둔다 — NOT NULL 제약이 존재하는지 assert하고, 제약을 풀 때는 잠금 coalesce를 함께 넣어야 한다는 의존성을 주석으로 남긴다

nullify 판정(`recommended_action=nullify`) 건은 정정 manifest에서 제외하고 보류 목록으로 보고한다. NULL 전환이 정말 필요하다고 스캔 리포트 이후 결정되면 그때 0027(제약 완화 + 잠금 coalesce + 웹 화면 영향 검토)로 별도 진행한다.

## 별건: CLI 설정 배선이 어긋나 있다

Task 4 Step 6(실제 DB 소규모 실행)이 실패한 원인을 찾았다. 자격증명이 없어서가 아니라 **읽는 키가 다르다.**

`main_noonnu_url_scan`은 `load_settings()`(= `Settings`)의 `supabase_url`/`supabase_secret_key`를 본다. 그런데 `.env.local`에는 그 이름의 키가 없고 `SUPABASE_DEV_URL`/`SUPABASE_DEV_SECRET_KEY`가 있다.

다른 감사 명령들은 `load_audit_settings()`(= `AuditSettings`)를 쓰고 `--target dev|prod`로 환경을 고른다. `config.py:65-67`의 주석이 그 의도를 밝힌다.

> 일반 `SUPABASE_URL`/`SUPABASE_SECRET_KEY`는 공개 기준선 읽기와 기존 명령 호환용일 뿐, 이 경계에서 fallback으로 사용하지 않는다.

`noonnu-url-scan`도 같은 패턴으로 바꿔야 한다. 다만 이 명령은 **읽기 전용**이므로 쓰기용 `dev_write_credentials()`(dev/prod origin 교차 검증 포함)까지 필요하지는 않다. `--target` 인자를 추가하고 해당 환경의 URL과 키를 읽는 선에서 맞춘다.

이 작업은 Task 7의 선행 조건이다.
