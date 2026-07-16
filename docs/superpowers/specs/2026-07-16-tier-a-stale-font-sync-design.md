# Tier A stale 폰트 동기화 설계

> 작성일: 2026-07-16 | 상태: 사용자 승인 | 상위 작업: Slice 0.5 Task 5

## 1. 문제

구글폰트 인기순 목록에서 `Urbanist`가 빠지고 `Geist`가 들어왔다. 현재 파이프라인은 새 폰트를 upsert하지만, 이번 수집 결과에서 빠진 기존 폰트는 그대로 `published` 상태로 남긴다. 그 결과 dev 공개 폰트가 130종에서 131종으로 늘어 파이프라인 결과와 DB가 달라졌다.

## 2. 결정

전체 업로드가 성공한 뒤, 이번 결과에 없는 기존 Tier A 폰트만 `draft`로 바꾼다.

- 행과 별칭은 삭제하지 않는다. 기록과 slug를 보존한다.
- Tier B/C 폰트는 건드리지 않는다.
- 다음 수집에서 폰트가 다시 나타나면 기존 `upsert_font`가 `published`로 복구한다.
- 폰트별 업로드가 하나라도 실패하면 stale 동기화를 실행하지 않는다.
- 빈 slug 목록은 DB 함수에서 오류로 막아 전체 Tier A 비공개 사고를 방지한다.
- 적용 환경은 dev(`zgxtfcpiokhkcrywlxmc`)만이다. prod에는 적용하지 않는다.

## 3. 검토한 접근

1. **DB RPC 동기화(채택)**: 모든 upsert 성공 후 DB 함수 한 번으로 누락 Tier A를 `draft` 처리한다. 기존 보안 패턴과 같고, 동기화 갱신이 한 트랜잭션으로 처리된다.
2. 클라이언트에서 fonts 테이블 직접 update: 파일은 적게 바뀌지만 대량 조건 갱신과 권한 경계가 코드에 퍼진다.
3. 누락 행 삭제: DB는 깔끔하지만 이력과 상세 주소를 잃고, 재등장 처리도 불필요하게 복잡해진다.

## 4. 구조와 흐름

### 4.1 DB 함수

`supabase/migrations/0005_sync_tier_a_fonts.sql`에 아래 함수를 추가한다.

```sql
fontagit.sync_tier_a_fonts(p_active_slugs text[]) returns integer
```

동작:

1. `p_active_slugs`가 비었으면 예외를 발생시킨다.
2. `source_tier = 'A'`, `status = 'published'`, active slug 목록에 없는 행만 `draft`로 변경한다.
3. `updated_at`을 현재 시각으로 바꾼다.
4. 변경한 행 수를 반환한다.
5. 실행 권한은 `service_role`에만 부여한다.

`0005`는 아직 파일이 없는 다음 번호다. 기존 예정 번호는 구현 전에 검색 `0006`, 클릭 집계 `0007`, 등록 `0008`로 한 칸씩 조정한다.

### 4.2 파이프라인

`upload_records()`는 기존처럼 폰트별 `upsert_font`를 실행한다. 전체 반복이 끝난 뒤에만 Tier A slug 집합으로 `sync_tier_a_fonts`를 한 번 호출한다.

- upsert 실패: 예외 전파, sync 호출 없음.
- sync 실패: 예외 전파, CLI 종료 코드 3. 이미 성공한 upsert는 유지되며 다음 멱등 실행으로 복구한다.
- 성공 로그: 업로드 수와 비공개 전환 수를 분리해 기록한다.

## 5. 테스트

핵심 서비스 로직에 테스트 2개만 추가한다.

1. 성공 경로: 모든 `upsert_font` 뒤에 `sync_tier_a_fonts`가 정확히 한 번 호출되고 active slug가 전달된다.
2. 치명적 예외: 중간 upsert 실패 시 `sync_tier_a_fonts`가 호출되지 않는다.

DB 함수 자체는 dev에 마이그레이션을 적용한 뒤 실데이터로 검증한다.

## 6. 완료 기준

- 파이프라인 전체 테스트 통과.
- dev 재적재 종료 코드 0.
- 공개 폰트 130종, 전체 폰트 137종. `Urbanist`는 `draft`, `Geist`는 `published`.
- `name_ko` 31종, 한글 별칭 보유 32종, 한글 38종 전수 대조 불일치 0건.
- 현재 파이프라인 결과에 포함된 라틴 92종의 `name_ko`는 모두 null.
- Tier B/C 상태 변경 0건.
- prod 쓰기 0건.
