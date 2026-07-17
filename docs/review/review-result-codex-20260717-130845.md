### 종합 평가
- 전체 점수: 7/10
- 한줄 요약: SQL 핵심은 맞지만, 디바운스 훅의 경쟁 조건과 테스트 구멍은 구현 전 반드시 고쳐야 합니다.

### 항목별 리뷰
| 관점 | 평가 | 상세 |
|------|------|------|
| 완성도 | 주의 | Task 단위 deliverable은 좋습니다. 다만 Task 6 테스트가 핵심 버그를 못 잡고, 드롭다운 스타일 파일이 빠졌습니다. |
| 누락 항목 | 주의 | stale 응답 방어, generated type 갱신, authenticated 권한 필요 여부, migration 트랜잭션 처리가 빠졌습니다. |
| 일관성 | 양호 | `searchSuggestions(q, lim=8)`, `{ q, lim }`, `foundry`, `SuggestItem` 흐름은 대체로 일치합니다. |
| 실현 가능성 | 주의 | PostgreSQL 초성 함수와 Route Handler는 실현 가능성이 높습니다. Vitest fake timer와 React race 처리는 보강이 필요합니다. |

### 구체적 피드백

1. [Blocker] Task 6 구현은 빈 쿼리로 바뀐 뒤 늦게 온 응답이 다시 items를 채울 수 있습니다.  
   문제 코드: `if (!q) { setItems([]); setLoading(false); return; }`  
   `seqRef.current`를 증가시키기 전에 return 하므로, 이전 fetch가 Abort를 무시하고 resolve되면 stale 결과가 반영될 수 있습니다. `const seq = ++seqRef.current;`를 빈 쿼리 검사보다 앞으로 옮기세요.

2. [Blocker] Task 6 테스트 이름은 “마지막 응답만 반영”인데 실제로는 fetch 1번만 검증합니다.  
   `rerender`로 `query`를 바꾸고, 첫 요청은 늦게 resolve, 두 번째 요청은 먼저 resolve되는 테스트가 필요합니다.

3. PostgreSQL `to_chosung` 공식은 맞습니다.  
   `ascii(ch) between 44032 and 55203`, `(ascii - 44032) / 588`, 배열 1-based 인덱싱 모두 정상입니다. `지마켓산스`는 `ㅈㅁㅋㅅㅅ`가 맞습니다.

4. `regexp_split_to_table(p, '') with ordinality` + `string_agg(order by ord)`도 방향은 맞습니다.  
   문자 순서 보존 목적에 적합합니다.

5. `generated always as (fontagit.to_chosung(alias_norm)) stored`는 가능합니다.  
   조건은 `to_chosung`이 `IMMUTABLE`이고, `alias_norm`이 일반 컬럼이면 됩니다. 현재 계획은 이 조건을 만족합니다.

6. `drop function fontagit.search_fonts(text)` 후 `search_fonts(q text, lim int default 20)` 재정의는 SQL 호출 기준 하위호환됩니다.  
   다만 Supabase 타입을 생성해서 쓰고 있다면 generated type도 갱신해야 합니다.

7. 권한은 시그니처가 맞습니다.  
   `revoke/grant ... search_fonts(text, int)`는 새 함수와 매칭됩니다. 단, 로그인 사용자가 `authenticated` role로 호출할 가능성이 있으면 `grant execute ... to authenticated`도 검토해야 합니다.

8. migration은 트랜잭션으로 감싸는 편이 안전합니다.  
   지금은 `drop function` 뒤 create가 실패하면 검색 RPC가 사라질 수 있습니다. `begin; ... commit;`을 권장합니다.

9. SQL 테스트 C6은 lim clamp를 실제로 검증하지 않습니다.  
   “에러 없음”만 봅니다. `lim=0`, `lim=-5` 결과가 `<= 1`인지까지 확인하는 게 좋습니다.

10. Task 8 테스트는 `push` mock 초기화가 필요합니다.  
   `const push = vi.fn()`만 있고 테스트마다 clear하지 않으면 이전 테스트 호출 때문에 IME 테스트가 실패할 수 있습니다.

11. `HeaderSearch`의 ARIA 방향은 좋습니다.  
   다만 items가 바뀔 때 `activeIndex`가 범위를 벗어나지 않게 clamp/reset하는 로직이 필요합니다.

12. Task 7은 스타일 파일이 파일 구조에 없습니다.  
   기능은 동작해도 드롭다운 위치, z-index, hover, active 상태가 깨질 수 있습니다. CSS Module 또는 기존 스타일 파일을 명시하세요.

### 개선 제안

1. P0: Task 6의 `seqRef` 위치를 고치고, stale 응답 테스트를 추가하세요.

2. P0: migration을 트랜잭션으로 감싸세요.

3. P1: Supabase generated types 사용 여부를 확인하고, 쓰고 있다면 타입 갱신 단계를 추가하세요.

4. P1: `authenticated` role에서도 검색이 필요한지 결정하세요.

5. P2: `listboxId = 'header-suggest-listbox'` 대신 `useId()`를 쓰면 중복 id 위험이 줄어듭니다.