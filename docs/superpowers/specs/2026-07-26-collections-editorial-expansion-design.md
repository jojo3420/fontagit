# 컬렉션 에디토리얼 10종 확장 설계

- 작성일: 2026-07-26
- 상태: 사용자 승인
- 관련 이슈: #56, 후속 #104

## 1. 목적

운영 `/collections`의 컬렉션을 3종에서 10종으로 먼저 확대한다. Tier B 1,110종의 metadata 전수 보강은 이 작업을 막지 않으며, 10종 공개 후 별도 #104 작업으로 이어간다.

운영 DB 읽기 전용 확인 기준:

- 발행 폰트 1,240종
- Tier A 130종은 license status가 verified
- Tier B 1,110종은 license status가 pending
- tags 보유 47종, weights 보유 446종
- 선정한 고유 폰트 40종은 dev·운영 DB에 모두 존재하며 `published`·`verified`·`OFL`

따라서 이번 단계는 정보가 충분한 Tier A와 현재 확인된 필드를 중심으로 사람이 고른 에디토리얼 컬렉션을 만든다.

## 2. 검토한 접근

### A. 검증된 폰트로 에디토리얼 10종 완성 — 채택

- 기존 3종을 유지·보강하고 새 컬렉션 7종을 추가한다.
- 발행 상태와 라이선스 상태가 확인된 폰트를 우선 사용한다.
- 스키마와 웹 화면을 바꾸지 않고 새 데이터 마이그레이션만 추가한다.

장점은 빠르고 현재 데이터로 정확하게 만들 수 있다는 점이다. 단점은 새 폰트가 들어올 때 자동 갱신되지 않는다는 점이다.

### B. 현재 metadata로 자동 컬렉션 생성 — 기각

tags는 47종에만 있고 Tier B 1,110종의 라이선스는 아직 pending이다. 지금 규칙을 만들면 빈약하거나 잘못 분류된 컬렉션이 생길 위험이 크다.

### C. #104 전수 처리 후 컬렉션 생성 — 후속

자동화에는 가장 적합하지만 사용자 화면이 계속 3종으로 남는다. A 완료 후 #104와 자동 컬렉션 설계를 별도 작업으로 진행한다.

## 3. 컬렉션 구성

모든 컬렉션은 발행 폰트 5종 이상을 가진다. 같은 폰트가 서로 다른 목적의 컬렉션에 중복되는 것은 허용한다.

### 기존 3종 보강

| slug | 제목 | 폰트 |
|---|---|---|
| `dawn-serif` | 새벽 감성 명조 모음 | `gowun-batang`, `nanum-myeongjo`, `song-myung`, `noto-serif-kr`, `hahmlet` |
| `brand-gothic` | 브랜드 첫인상 고딕 | `black-han-sans`, `do-hyeon`, `gasoek-one`, `bagel-fat-one`, `gugi` |
| `playful-hand` | 손끝의 온기 손글씨 | `gaegu`, `kirang-haerang`, `jua`, `nanum-brush-script`, `nanum-pen-script` |

### 신규 7종

| slug | 제목 | 폰트 |
|---|---|---|
| `ui-korean-sans` | 화면에 또렷한 한글 고딕 | `noto-sans-kr`, `ibm-plex-sans-kr`, `gothic-a1`, `nanum-gothic`, `asta-sans`, `gowun-dodum` |
| `wide-weight-korean` | 굵기를 자유롭게 고르는 한글 폰트 | `gothic-a1`, `hahmlet`, `noto-sans-kr`, `noto-serif-kr`, `ibm-plex-sans-kr`, `asta-sans` |
| `korean-display` | 한눈에 꽂히는 한글 디스플레이 | `bagel-fat-one`, `gugi`, `moirai-one`, `dokdo`, `cute-font`, `gasoek-one` |
| `latin-sans-essentials` | 영문 산세리프 기본 컬렉션 | `inter`, `source-sans-3`, `dm-sans`, `montserrat`, `figtree` |
| `latin-serif-editorial` | 영문 에디토리얼 세리프 | `lora`, `merriweather`, `eb-garamond`, `libre-baskerville`, `playfair-display`, `bitter` |
| `developer-monospace` | 코드와 숫자를 위한 모노스페이스 | `inconsolata`, `jetbrains-mono`, `roboto-mono`, `source-code-pro`, `nanum-gothic-coding` |
| `verified-ofl-picks` | OFL 라이선스 확인 추천 | `noto-sans-kr`, `noto-serif-kr`, `ibm-plex-sans-kr`, `inter`, `lora`, `jetbrains-mono`, `bagel-fat-one` |

## 4. 데이터 변경

신규 마이그레이션 `supabase/migrations/0020_expand_editorial_collections.sql` 하나를 추가한다.

마이그레이션은 다음 순서로 동작한다.

1. 대상 폰트 slug가 모두 존재하고 `published`인지 검사한다.
2. 하나라도 없으면 예외를 발생시켜 전체 변경을 중단한다.
3. 새 컬렉션 7종을 upsert하고 기존 3종의 제목·소개는 유지한다.
4. 대상 10종의 `collection_items`만 삭제 후 확정 목록으로 다시 넣는다.
5. 각 컬렉션의 `sort_order`와 폰트별 한 줄 설명을 함께 저장한다.
6. 재실행해도 컬렉션과 폰트 연결이 중복되지 않아야 한다.

스키마 변경, 자동 규칙 엔진, 관리 UI, 웹 컴포넌트 변경은 하지 않는다.

## 5. 문구 원칙

- 컬렉션 소개는 사용 상황과 선택 이유를 1~2문장으로 설명한다.
- 폰트별 설명은 실제 형태·굵기·용도처럼 확인 가능한 내용만 쓴다.
- 라이선스가 허용한다고 추정하거나 인쇄 품질을 보장하는 표현은 쓰지 않는다.
- 영문 컬렉션도 제목과 소개는 한국어로 제공한다.

## 6. 실패·복구

- 폰트 누락, 발행 상태 불일치, 중복 slug가 있으면 마이그레이션을 실패시킨다.
- 기존 3종 외의 컬렉션은 건드리지 않는다.
- 운영 적용 전 기존 `collections`와 `collection_items`를 JSON 또는 SQL 결과로 저장한다.
- 운영 롤백은 신규 7종 삭제와 기존 3종의 이전 8개 연결 복원으로 제한한다.

## 7. 검증

### 데이터

- 발행 컬렉션이 정확히 10종 이상이다.
- 이번 대상 10종은 각각 발행 폰트 5종 이상을 가진다.
- 컬렉션 안에 같은 폰트가 중복되지 않는다.
- 모든 연결 폰트가 `published`다.

### 웹

- `/collections/`에 10종이 정렬 순서대로 표시된다.
- 각 상세 페이지와 폰트 링크가 모두 열린다.
- 정적 빌드와 SEO 검증에서 10종의 canonical·sitemap URL이 빠지지 않는다.
- 모바일과 데스크톱에서 기존 레이아웃이 깨지지 않는다.

단순 시드·조회용 단위 테스트는 추가하지 않는다. 데이터 불변식은 SQL 검증과 정적 빌드로 확인한다.

## 8. 배포 경계

1. dev DB에 마이그레이션 적용
2. dev 데이터 검증
3. dev DB 데이터를 사용한 production-mode 정적 빌드·SEO 검증
4. PR 병합
5. production DB 적용
6. production 재빌드·배포
7. `https://fontagit.com/collections/`와 대표 상세 페이지 직접 확인

코드 병합만으로 운영 완료라고 판단하지 않는다.

## 9. 후속 2단계

이 설계 완료 후 #104를 별도 설계·계획으로 진행한다.

- Tier B 1,110종 metadata 전체 실행
- 감사 → auto-approve → manifest build → apply 단일 체인
- dev 전체 검증 후 production 적용
- 채워진 metadata를 이용한 DB 규칙 엔진과 자동 컬렉션 materialize

에디토리얼 10종은 후속 자동 컬렉션과 공존한다.

## 10. 시작점 검증 메모

최신 `origin/develop`(`444a8d7`) 기반 새 작업공간에서 `pnpm install --frozen-lockfile`을 실행했으나, 기존 `pnpm-lock.yaml`과 `apps/web/package.json` 불일치로 실패했다. 이번 컬렉션 변경 전부터 존재한 기준선 문제다.

웹 검증 전에 잠금 파일 문제를 별도 최소 변경으로 해결하거나, 이미 검증된 최신 기준선으로 브랜치를 보정해야 한다. 컬렉션 시드 변경과 한 커밋에 섞지 않는다.

초기 후보였던 `geist`는 운영에서는 발행 상태지만 현재 dev에서는 `draft`라서 제외했다. dev·운영에서 모두 발행 상태인 `source-sans-3`로 교체해 환경에 따른 마이그레이션 실패를 막는다.
