# Prod 폰트 데이터 감사 수집 정책

이 문서는 수집을 시작하기 전에 `robots.txt`와 이용 조건을 사람이 확인하는 기록이다.
승인 전 기본값은 `unknown`이며, 이때는 원문을 저장하지 않는 `structured-only` 모드만 쓴다.

## 정책 기록

| 출처 | robots URL | 이용 조건 URL | 확인 시각 | 수집 허용 | 원문 장기 저장 허용 | robots SHA-256 | 이용 조건 SHA-256 | 승인자 / 승인 시각 |
|---|---|---|---|---|---|---|---|---|
| noonnu | https://noonnu.cc/robots.txt | 미확인 | 미확인 | unknown | unknown | 미확인 | 미확인 | 미승인 |

`수집 허용`과 `원문 장기 저장 허용`은 서로 따로 승인한다. URL만 확인했거나 해시가 없으면
승인된 것으로 보지 않는다. `unknown` 또는 원문 저장 불허 상태에서는 출처 URL, 구조화 값,
근거 위치, 원본 해시만 저장하고 HTML·본문은 저장하지 않는다.

## 실행

```bash
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-policy-check \
  --out output/audit/collection-policy.json
```

명령은 승인 전 JSON을 만든다. `crawl_allowed`와 `raw_retention_allowed`는 모두 `unknown`이다.
담당자가 robots·이용 조건 원문과 SHA-256을 확인한 뒤 승인자와 승인 시각을 함께 기록해야 한다.
