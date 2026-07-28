### 종합 평가
- 전체 점수: 7/10
- 한줄 요약: 큰 방향은 실행 가능하지만, 서브에이전트가 그대로 실행하기엔 경로, 기존 코드 시그니처, 검증 기준, DB 적용 절차에 애매하거나 위험한 부분이 꽤 있습니다.

### 항목별 리뷰
| 관점 | 평가 | 상세 |
|------|------|------|
| 실행 모호성 | 주의 | “전체 교체” 지시가 많아 기존 props/import/CSS를 깨뜨릴 수 있습니다. 기존 컴포넌트 구조 확인 지시가 부족합니다. |
| 검증 방법 확실성 | 주의 | 단위 테스트는 있으나 DB 적용, 정적 export, 리다이렉트, 홈 필터 실제 동작 검증은 기대 결과가 약합니다. |
| 완성도 | 주의 | 핵심 기능은 포함됐지만 `/collections` 제거 후 상세 라우트, sitemap, redirect, build 산출물 검증이 더 구체적이어야 합니다. |
| 누락 항목 | 주의 | Supabase 중복 INSERT, PATCH 수렴 검증, created_at select 포함 여부, URL 쿼리 인코딩, 기존 테스트 mock 깨짐 가능성이 빠졌습니다. |
| 일관성 | 주의 | `createdAt`, `created_at`, `FontRow`, `getAllFonts`, `ComparePreset` 흐름은 맞지만 실제 DB select와 타입 반영 위치가 충분히 고정되지 않았습니다. |
| 실현 가능성 | 양호 | 기술적으로 가능하지만 Task 5~7은 기존 컴포넌트와 충돌 가능성이 높아 “그대로 붙여넣기” 방식은 위험합니다. |

### 구체적 피드백

1. [Blocker] Task 3: `created_at`이 실제 쿼리 select에 포함되는지 빠졌습니다.  
   `rowToFont`에 `createdAt: row.created_at`만 추가하면, `getAllFonts()`가 `created_at`을 DB에서 가져오지 않는 구조일 경우 항상 `undefined`가 됩니다. Task 3에 “DB select 또는 정적 데이터 생성 경로에서 `created_at` 포함 확인”을 넣어야 합니다.

2. [Blocker] Task 5: `FontCard.tsx` “전체 교체”는 위험합니다.  
   기존 `FontCard`가 다른 prop, className, 접근성 속성, tracking, preview 로직을 갖고 있으면 전부 날아갑니다. “전체 교체” 대신 기존 구조를 유지하고 `badge?`만 추가하라고 바꿔야 합니다.

3. [Blocker] Task 7: `CompareCanvas` preset 적용이 기존 사용자 선택을 덮어쓸 수 있습니다.  
   `useEffect`가 `preset` 객체 변경마다 실행됩니다. 부모가 매 렌더마다 새 객체를 만들면 사용자가 직접 바꾼 선택이 다시 preset으로 돌아갈 수 있습니다. preset 변경 기준을 `heroSlug + gridSlugs.join()` 등으로 고정하거나, 클릭 시에만 반영되게 해야 합니다.

4. [Blocker] Task 8: 컬렉션 INSERT는 부분 실패 시 중복/반쪽 데이터가 생길 수 있습니다.  
   `collections` 생성 성공 후 `collection_items` 생성 실패하면 다음 재실행 때 컬렉션은 “이미 존재”라며 건너뛰고 아이템은 비어 있을 수 있습니다. 기존 컬렉션이 있을 때 아이템 수를 확인하거나, upsert/삭제 후 재삽입 전략이 필요합니다.

5. Task 1: `plan_recategorization(rows: list[dict]) -> dict`는 너무 느슨합니다.  
   서브에이전트용 문서라면 반환 dict 구조를 더 정확히 적어야 합니다. 예: `changes`, `counts`, `distribution_after` 키와 값 타입을 명시하세요.

6. Task 1: `resolve_category(None, "고딕")` 테스트와 인터페이스가 불일치합니다.  
   인터페이스는 `tags: list[str]`라고 되어 있는데 테스트와 구현은 `None`을 허용합니다. 인터페이스를 `list[str] | None`으로 고쳐야 합니다.

7. Task 1/2: PATCH 검증이 로그 문자열에 의존합니다.  
   `Expected: PATCH 완료: 성공=N, 실패=0`만으로는 DB 반영을 충분히 증명하기 어렵습니다. 재실행 `changed=0`은 좋지만, 리포트 JSON의 `counts.changed == 0` 확인 명령을 추가하면 더 확실합니다.

8. Task 2: prod dry-run과 apply가 한 Step에 섞여 있습니다.  
   Step 5는 위험합니다. prod dry-run 리포트 생성, 리포트 검토, 사용자 최종 승인, prod apply, 수렴 확인을 분리해야 합니다.

9. Task 2: 리포트 파일 경로가 상대경로라 혼동됩니다.  
   `cd apps/pipeline` 기준이면 실제 경로는 `apps/pipeline/output/audit/...`입니다. 문서 전반에서 “명령 실행 기준 경로”와 “git add 기준 경로”가 섞입니다. 각 Task에 기준을 명확히 쓰세요.

10. Task 4: 정렬 로직의 “최신순 유지” 전제가 약합니다.  
    주석에 “fonts는 getAllFonts의 최신 등록순”이라고 되어 있지만, 이 전제가 깨지면 홈 품질이 바로 떨어집니다. `buildHomePreview`에서 `createdAt` 기준 정렬을 직접 넣거나, 입력 전제를 테스트로 고정하세요.

11. Task 4: `new Date(font.createdAt)`이 invalid date일 때 처리가 없습니다.  
    잘못된 문자열이면 `NaN`이 나오고 조용히 뱃지가 안 붙습니다. 치명적이진 않지만 테스트 1개로 “invalid createdAt은 undefined”를 고정하면 좋습니다.

12. Task 4/5: `/fonts?category=고딕&sort=popular` 쿼리 인코딩이 애매합니다.  
    브라우저가 처리할 수는 있지만, 안전하게 `URLSearchParams` 또는 인코딩된 쿼리 기준을 정하는 편이 낫습니다.

13. Task 5: `FilterChip`이 실제로 `button`과 `aria-pressed`를 렌더하는지 전제가 있습니다.  
    테스트는 `getByRole("button")`와 `aria-pressed`를 기대합니다. 기존 `FilterChip` 구현이 다르면 테스트가 실패합니다. Task에 “기존 FilterChip 확인 후 필요한 경우 aria-pressed 추가”를 명시하세요.

14. Task 5: `HomeExplorer`의 “전체 보기” 카드가 폰트 카드와 같은 grid 안에 들어갑니다.  
    `perChip=8`이면 실제 grid 아이템은 9개가 됩니다. 의도라면 명시하고, 아니라면 폰트 7개 + 더보기 1개로 제한해야 합니다.

15. Task 5: `FontCard`의 badge 위치가 작은 화면에서 깨질 수 있습니다.  
    `nameKo`가 긴 폰트명일 때 `footRight`와 겹칠 수 있습니다. `min-width: 0`, `text-overflow`, `flex-shrink` 규칙을 추가해야 합니다.

16. Task 6: `/collections` 목록 삭제 후 상세 라우트 보존 검증이 부족합니다.  
    `apps/web/app/collections/[slug]/page.tsx`가 남는지만 확인하지 말고, `pnpm build` 후 `out/collections/{slug}/index.html` 생성 여부까지 Task 6 또는 Task 9에 넣어야 합니다.

17. Task 6: `_redirects` 문법은 호스팅 환경 의존입니다.  
    Next 정적 export가 어디에 배포되는지에 따라 `_redirects`가 무시될 수 있습니다. 사용 중인 호스팅이 `_redirects`를 읽는다는 전제를 명시해야 합니다.

18. Task 6: Header의 `/#collections`는 현재 홈에서 클릭 시 동작이 애매할 수 있습니다.  
    같은 페이지 내 hash 이동은 되지만, fixed header가 있으면 위치가 가려질 수 있습니다. `scroll-margin-top`은 들어갔지만 실제 수동 검증에 포함해야 합니다.

19. Task 7: `familyOf(hero.fontKey)`가 `fontKey: null`일 때 안전한지 확인이 필요합니다.  
    인터페이스에 “무료 폰트 mock 9종”만 적혀 있지만, `familyOf`가 null을 받는지 명확하지 않습니다. 안 받으면 런타임 에러입니다.

20. Task 7: `PairingPresets` 테스트가 버튼 수 3개만 봅니다.  
    버튼 안에 `null` 렌더가 생기면 3개가 안 나와 실패하긴 하지만, 원인 파악이 어렵습니다. “PAIRINGS의 slug가 모두 fonts에 존재해야 한다” 테스트를 데이터 테스트로 분리하면 더 명확합니다.

21. Task 7: `HomeCompareSection`은 클라이언트 컴포넌트라 compare 전체가 클라이언트 경계 안으로 들어갑니다.  
    문제는 아니지만 홈 성능에 영향이 있습니다. 의도된 트레이드오프인지 적어야 합니다.

22. Task 8: `sort_order`가 “기존 10개 뒤”라는 전제가 하드코딩입니다.  
    이미 DB에 10개가 아니거나 sort_order가 0~9가 아니면 충돌할 수 있습니다. dry-run에서 기존 collection count와 sort_order 충돌 여부를 리포트해야 합니다.

23. Task 8: 후보가 0개인 컬렉션도 published로 생성됩니다.  
    빈 컬렉션을 허용할지 불명확합니다. 최소 후보 수 기준, 예를 들어 5개 미만이면 apply 중단 같은 규칙이 필요합니다.

24. Task 8: prod 적용 후 수렴 확인이 약합니다.  
    dev는 14개 카운트 확인이 있는데 prod도 같은 확인이 필요합니다. `collections` 카운트와 각 신규 컬렉션 item 수 확인을 Expected로 넣으세요.

25. Task 9: `pnpm start` 설명이 애매합니다.  
    Next 정적 export에서 `pnpm start`가 실제로 `out/`을 서빙하는지 프로젝트 스크립트에 따라 다릅니다. 정확한 명령을 확인해 문서에 고정해야 합니다.

26. Task 9: 테스트 범위가 좋지만 시각 회귀 확인이 부족합니다.  
    홈 개편은 UI 영향이 큽니다. 최소한 데스크톱/모바일에서 홈 첫 화면, 칩 전환, 컬렉션 스트립, 비교 섹션 스크린샷 확인을 넣는 게 안전합니다.

27. 마무리 절차: PR base가 `main`으로 고정되어 있는데 저장소 흐름과 맞는지 불명확합니다.  
    앞선 작업 문맥에서 `develop`을 쓰는 흐름이 있다면 `base: main`은 위험합니다. 이슈 #128의 실제 대상 브랜치를 명확히 해야 합니다.

### 개선 제안

1. 최우선: Task 3에 `created_at` 실제 데이터 로딩 경로 확인을 추가하세요.  
   `Font` 타입만 바꾸면 NEW 뱃지가 작동하지 않을 수 있습니다.

2. 최우선: Task 5와 Task 7의 “전체 교체” 지시를 줄이세요.  
   서브에이전트에게 “기존 파일을 먼저 보고, 기존 prop/import/접근성/스타일을 보존한 채 필요한 부분만 추가”라고 써야 합니다.

3. 최우선: Task 8에 idempotent, 즉 재실행해도 안전한 DB 적용 규칙을 넣으세요.  
   이미 컬렉션이 있으면 item 수 확인, 부족하면 보정, 실패하면 중단하도록 해야 합니다.

4. 중요: 각 DB apply Task는 dry-run, 사용자 승인, apply, DB 직접 확인을 별도 Step으로 분리하세요.  
   한 Step에 여러 위험 작업을 묶으면 서브에이전트가 승인 없이 넘어갈 가능성이 큽니다.

5. 중요: 모든 Expected를 “문자열 로그”보다 “파일/JSON/DB 상태” 기준으로 바꾸세요.  
   예: `report.counts.changed == 0`, `published collections == 14`, `신규 collection_items 각 1개 이상`.

6. 중요: Task 6/9에 정적 export 산출물 검증을 더 구체화하세요.  
   `/collections/index.html` 없음, `/collections/{slug}/index.html` 있음, `/collections` 301 동작 확인을 분리하면 좋습니다.

7. 보통: URL 쿼리는 `URLSearchParams` 또는 명시적 인코딩 규칙으로 통일하세요.  
   한글 category 쿼리는 작은 차이로 테스트와 실제 동작이 달라질 수 있습니다.

8. 보통: 홈 UI 수동 검증에 모바일 폭을 추가하세요.  
   이번 변경은 그리드, 스트립, 카드, 뱃지가 있어 모바일 깨짐 가능성이 큽니다.