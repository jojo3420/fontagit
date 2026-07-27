# 라이선스 검수 + 크롤 고도화 통합 설계

- 날짜: 2026-07-27
- 대상 이슈: #90(일부), #96, #114(Should-fix), #120
- 접근법: A안 — 기존 감사 체인(수집 → findings → manifest 청크 → apply RPC) 확장
- 상태: 사용자 설계 승인 완료 (2026-07-27)

## 1. 목표

1. 나눔명조류 Tier A 폰트의 제작사/출처 오표기 정정 (#120 문제점 1)
2. Tier A/B download_url 백필 (#96, #120 요구 5)
3. KOGL(공공누리) 271종 유형 판별과 권한 매핑 (#90)
4. 과거 크롤 오류 22종 재현 확인-재크롤 (#90, #120)
5. 대량 적용 전 manifest 청크 무결성 가드레일 (#114 Should-fix)
6. 상세 견본 문구 다양화 — 태그별 문구 풀 30개 (사용자 추가 요구)

## 2. 범위 제외 (백로그)

| 항목 | 사유 | 행선지 |
|---|---|---|
| 눈누 proposed 44건 대조 | legal 사람 게이트, 사용자 시간 필요 | #90 잔여 |
| custom-free 1,110종 검수 전략 | 별도 결정 사이클 | #90 잔여 |
| 웹폰트 CSS 노출, 견본 글자크기 UI, 메타정보 칸 분리 | 새 UI 기능 | #120에서 분리해 신규 이슈 |
| 눈누 견본 문구 수집(specimen_text) | 전체 재크롤 필요 가능성 | 신규 백로그 이슈 |
| #105 나머지, #84, #3 | 이 클러스터와 별개 축 | 기존 이슈 유지 |

## 3. 확정 결정 (사용자 답변)

| # | 결정 | 근거 |
|---|---|---|
| 1 | 세션 범위 = #90(KOGL+재크롤) + #96 + #114 Should-fix + #120 | 로드맵 데이터 트랙 완성 |
| 2 | Tier A 제작사 = 공식 우선 + 눈누 보조 + needs_review | 거버넌스(공식 최우선, 눈누 참고용) |
| 3 | 비legal 필드(제작사/다운로드/출처)는 자동 게이트 | metadata 전례(2026-07-23 결정) |
| 4 | legal(KOGL 권한값)은 사람 게이트 — 유형 그룹 단위 일괄 승인 | 271건을 최대 5번 결정으로 압축 |
| 5 | 견본 다양화 = 문구 풀 30개(해시 선택), 크롤 수집은 백로그 | SSG hydration 안전 + 범위 억제 |
| 6 | 기존 결정 유지: manifest 청크 100, prod REST in-list 40, prod 쓰기 사용자 확인 | 핸드오프 계승 |

## 4. 슬라이스 구성 (실행 순서)

### S0. 가드레일 (#114 Should-fix)

- manifest 청크 분할에 참조 무결성 예외 단정: 청크별 `referenced_evidence_ids - included`, `referenced_finding_ids - included` 잔여 시 ManifestError
- 다중 청크 테스트 보강(3엔트리 chunk_size=2: 합집합 보존, 청크별 evidence 참조, reverse before/after, 누락 evidence 예외)
- audit-chain.sh 청크 실패 메시지에 "부분 적용 상태" 명시 + apply 멱등 재실행 보장 문서화
- 기존 PR/문서의 "무결성 검증 포함" 표현을 실제 구현 수준으로 정정

### S1. Tier A 공식 수집기 (#96, #120 문제점 1)

- 입력: google/fonts 저장소 METADATA.pb(designer, copyright), webfonts API(files) — 약 130종
- 산출 findings: `foundry`, `foundry_url`, `download_url`, `download_source_kind`, `license_source_url`
- download_url: webfonts API `files["regular"]` (#96 원안 유지)
- 실측 확인 완료: METADATA.pb designer 필드 실존(나눔명조 = "Sandoll Communication", copyright = "NHN Corporation")
- 스키마 변경 없음: fonts에 필요한 컬럼 전부 존재(0017 마이그레이션)

### S2. 눈누 재크롤 + 적용 스코프 확장 (#90 22종, #120)

- 과거 크롤 오류 22종 재현 확인 후 실패 지속 건만 재크롤(전량 재크롤 금지)
- 기존 파서(audit_noonnu.NoonnuFontSnapshot)가 #120 요구 6개 영역을 이미 수집 — 신규 개발이 아니라 **적용 스코프 확장**: 스냅샷의 foundry/download_candidates를 findings로 승격
- 눈누 크롤 실행은 사용자 승인 후(기존 하드 게이트 관례)

### S3. KOGL 271종 유형 판별 (#90)

- license_text에서 공공누리 제1~4유형 자동 판별(신규 파서 — 파이프라인에 KOGL 코드 전무 확인)
- 유형별 권한 매핑(초안 — 그룹 승인 시 공공누리 공식 유형 설명과 대조 후 확정):

| 유형 | allow_commercial | allow_modify | 공통 |
|---|---|---|---|
| 제1유형 | O | O | 출처표시 필수, 재배포 O(출처표시 조건), 폰트판매 X(보수 기본) |
| 제2유형 | X | O | 상동 |
| 제3유형 | O | X | 상동 |
| 제4유형 | X | X | 상동 |

- 유형 미검출 → needs_review 그룹 (허용 승격 금지)
- 적용은 유형 그룹 단위(최대 4그룹 + 미검출)로 사용자 일괄 승인 후 진행

### S4. 웹 슬라이스 — 표기 정리 + 견본 문구 풀 (#120 문제점 1, 견본 다양화)

- 상세 화면 "제작사"와 "출처/원문보기" 구분 표기 확인-정정. 나눔명조로 최종 검증(제작사=네이버 계열, 원문보기=실제 약관 페이지)
- 견본 문구 풀: 태그 그룹별 총 30개 문구 데이터 파일(apps/web) + slug 해시 고정 선택(SSG 안전) + 셔플 버튼. `specimen.ts` 확장, 기존 KOREAN_PANGRAM은 fallback

### 적용 절차 (S1~S3 공통)

1. dev 적용(자동 게이트: 공식 도메인 화이트리스트) → 실측 쿼리 검증(건수-샘플)
2. prod 적용은 사용자 확인(`FONTAGIT_PROD_MANIFEST_ENABLED=true`) 후 청크 100, in-list 40
3. dev 조회 Accept-Profile, 쓰기 Content-Profile: fontagit 헤더 준수

## 5. 제작사 매핑 규칙

- 원칙: **제작사 = 권리사** (디자인 스튜디오는 이번 미노출)
- 절차: 눈누 제작사 표기(제안값)를 공식 copyright 권리사와 대조 → 일치 시 자동 승인, 불일치 시 needs_review
- 브랜드 정규화 사전 1개 허용(데이터 파일, 예: "NHN Corporation" → "네이버"). 하드코딩 금지
- 공식 소스가 없는 Tier B는 눈누 값 + needs_review

## 6. 에러 처리

- 재크롤 실패, METADATA.pb 미존재/파싱 실패, KOGL 유형 미검출: needs_review 유지, 절대 허용 승격 금지(#90 안전 원칙)
- 청크 적용 중단 시: S0 가드레일의 "부분 적용 상태" 메시지 + 멱등 재실행

## 7. 테스트 전략

- 단위: KOGL 유형 파서, METADATA.pb 파서, 제작사 대조 규칙, 견본 해시 선택(경계: 태그 없음/풀 미매칭)
- 통합: S0 다중 청크 무결성 테스트
- 실측: dev 적용 후 건수-샘플 쿼리, 웹은 나눔명조 상세 화면 검증
- 웹 테스트는 env 격리 함정 주의(db import 컴포넌트는 db mock)

## 8. 리스크

- copyright 문자열 파싱 편차(법인명 표기 다양) → 정규화 사전 + needs_review로 흡수
- KOGL 유형이 license_text에 명시되지 않은 개체 존재 가능 → 미검출 그룹 규모 확인 후 후속 결정
- 웹폰트 files URL(gstatic)은 다운로드 UX로 부적절할 수 있음 → S4에서 노출 방식은 기존 UI 유지, 데이터만 백필
