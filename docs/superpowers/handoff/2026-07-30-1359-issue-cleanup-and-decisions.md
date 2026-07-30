# 세션 핸드오프 - 2026-07-30 13:59 KST

> **모드**: superpowers-plan (프로젝트 관례에 따라 `docs/superpowers/handoff/`에 저장)
> **Feature**: 이슈-브랜치 정리 + 미결정 2건 인계
> **이전 세션 종결 사유**: 사용자 인계 요청(결정 필요 항목 2건 대기)

## 한 줄 요약

최신 커밋 기준으로 GitHub 이슈를 최신화하고(#62 로드맵 갱신, 하위 이슈 11 -> 24개 연결, 신규 #152/#153 등록) 브랜치를 정리했다(`feat/noonnu-url-audit-task7` 합류 후 삭제, PR #151 머지되어 브랜치 삭제). **다음 세션은 사용자 결정이 필요한 2건(develop 처리 방침, #150 prod 쓰기 승인)부터 확인한 뒤 #150의 MUST를 진행한다.**

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** - 컨텍스트 복원 순서:

1. **이 핸드오프 파일을 읽는다** (`docs/superpowers/handoff/2026-07-30-1359-issue-cleanup-and-decisions.md`)
2. **직전 세션의 기술 재개점을 읽는다**: `docs/superpowers/handoff/2026-07-29-1135-noonnu-official-url-audit.md` (v2 스캔 결과, 미해결 갭, 핵심 파일 경로가 여기 있다)
3. **계획 문서를 읽는다**: `docs/superpowers/plans/2026-07-28-noonnu-official-url-audit.md` (미체크 22/50)
4. **현재 상태 확인**: `git status && git log --oneline -5 && gh issue view 150`
5. **아래 "미결정 사항"을 사용자에게 먼저 묻고**, 답을 받은 뒤 "다음 단계 -> MUST"를 시작한다

---

## 미결정 사항 (사용자 답변 대기, 최우선)

### 결정 1 - `develop` 브랜치를 어떻게 할 것인가

**질문**: main을 develop에 병합해 동기화를 유지할지, develop을 폐기할지.

**실측 근거**:

```
git cherry main develop  -> develop 고유 커밋 11개
git diff --stat main origin/develop -- apps/web -> 74 files, +455 -1279 (대부분 삭제)
```

- develop 고유 11개의 실체: 문서 커밋(progress 일지, 핸드오프, 듀얼 리뷰 리포트)과 squash로 main에 들어간 기능 커밋의 원본 형태(#104, #107, #117, #123)다. **main에 없는 실제 변경은 `.wrangler` 로컬 캐시 gitignore 1건(`d6f20de`)뿐**이다(main `.gitignore`에 `wrangler` 없음을 실측).
- 반대로 develop에는 main의 최신 산출물이 대거 빠져 있다: `noonnu_url_scan.py`, `audit_kogl.py`, `audit_manifest_preflight.py`, `tier_a_meta.py`, `CompareCanvas.tsx`, `DetailSpecimenPanel.*` 등 파이프라인-웹 파일 다수.
- 기능 PR base는 2026-07-27부터 main으로 바뀌었다(progress.md #118 항목). 즉 develop은 현재 아무도 쓰지 않는 레거시다.

**선택지**:
- (a) `git merge main` 후 develop 유지 - 충돌 처리 필요(progress.md 충돌 이력 있음), 유지 비용이 계속 든다
- (b) `.wrangler` gitignore 1건만 main에 체리픽하고 develop 폐기(원격 브랜치 삭제) - 정리 효과가 크다
- ⚠️ 자동으로 어느 쪽도 실행하지 않았다. 브랜치 폐기는 되돌리기 부담이 있어 사용자 판단 영역이다.

**추적 이슈**: #153

### 결정 2 - #150 prod 쓰기 승인 방식

**질문**: dev 정정까지 끝난 뒤 prod 적용을 언제, 어떤 패키지로 승인할지.

**전제(합의됨)**: prod 쓰기(INSERT/UPDATE/DDL)는 **실행 전 쿼리 전문을 사용자에게 보여 승인**받는다. 훅 차단은 2026-07-29에 제거됐으므로 사람 규율로만 지켜진다.

**승인 패키지에 담을 것**(계획 문서 합의):
변경 건수, 필드별 건수, 샘플 10건, 전체 slug 목록, 역방향 manifest(롤백용), 검증 쿼리.

**미결 지점**: `manual_review` 10건과 `nullify` 1건(`google-sans-flex`)을 prod 적용 1차에 포함할지, 164건만 먼저 적용할지.

---

## 작업 컨텍스트

### 사용자 원본 요청

> 최신 커밋내역을 기준으로 작업은 되었지만 깃헙 이슈는 정리되지 않은 내역 close 및 최신화 해죠. docs/progress/progress.md, https://github.com/jojo3420/fontagit/issues, #62 최신화 하기 (PR 내역도 함께 확인)

### 추가 지시 (중간)

> 1. 현재 작업브랜치 내용있다면 커밋 푸시 후 main, develop 최신화하기 그리고 관련된 branch 삭제처리하기(feat/noonnu-url-audit-task7)
> 2. 잔여작업은 issue 로 등록하기

### 사용자 제약 - 준수 사항

🔴 **반드시 (must)**:
- prod DB 쓰기는 쿼리 전문을 보여주고 승인받은 뒤 실행한다
- PR 머지는 항상 사용자 승인 후(이번 PR #151도 사용자가 직접 머지했다)
- codex 리뷰 실행은 기본적으로 사용자가 직접 한다(명시 요청 시에만 대신 실행)
- 브랜치 폐기-develop 병합처럼 되돌리기 부담이 있는 작업은 임의로 실행하지 않는다

---

## 이번 세션에 실제로 한 일

### 브랜치-원격 정리 (완료)

| 작업 | 실측 결과 |
|---|---|
| 로컬 `main` 미푸시 2커밋(문서) push | `3d94127..e7637cf` |
| `feat/noonnu-url-audit-task7`(5커밋)을 PR 브랜치에 fast-forward 후 push | `af70770..f6ae8e8` |
| `feat/noonnu-url-audit-task7` 로컬 삭제 | 완료(브랜치 목록에서 사라짐 확인) |
| PR #151 - 세션 중 사용자가 squash 머지 | main `0846cb1`, 2026-07-30 00:42 UTC |
| `feat/noonnu-url-audit-150` 로컬-원격 삭제 | 완료(원격 `- [deleted]` 출력 확인) |
| 작업트리 | clean, `main`이 `origin/main`과 동기(`0 0`) |

### 이슈 최신화 (완료)

- **#62 로드맵 본문 갱신**: 운영 기준선 v0.6.0 -> **v0.11.3**, 닫힌 #96/#104/#107/#114/#128 등을 완료 이력으로 이동, 오염 172종 경고 추가, 우선순위 재정렬
- **#62 하위 이슈 연결 11 -> 24개**: #115 #119 #120 #126 #129 #134 #138 #141 #142 #148 #150 #152 #153 추가(GraphQL `addSubIssue`, 전건 성공 응답 확인). 자동 진행률이 이제 실제 상태를 반영한다
- **#150 코멘트 2건**: v2 스캔 실측(정정 대상 `auto_fix_safe` 164건 확정) + 브랜치 합류 + PR #151 머지 정정
- **#148 코멘트**: 근본 수정은 PR #149로 완료, prod 데이터 172종이 아직 오염 상태라 **닫지 않음**(정정+재배포 후 실화면 확인해야 닫음)
- **#120 코멘트**: 수집 완료분/남은 항목(웹폰트 `@import` 수집 여부) 구분, UI 항목은 #152로 분리
- **신규 #152**: 폰트 상세 메타정보-견본 UI 고도화(#120 문제점 2/3/4), `enhancement`/`priority: medium`
- **신규 #153**: 브랜치 위생 정리 백로그, `priority: low`

### 닫을 수 있는 이슈는 없었다 (검증 결과)

"작업됐지만 미정리" 후보를 코드로 확인했더니 전부 미완이었다.

| 이슈 | 실측 |
|---|---|
| #138 검색결과 input 중복 | `apps/web/app/search/page.tsx`에 자체 input 여전히 존재 |
| #141 크롤러 결함 5종 | `apps/pipeline/src/fontagit_pipeline/audit_http.py`의 `_CURL_BASE`에 User-Agent(`-A`) 없음 |
| #115 / #119 / #126 / #129 | 해당 코드 변경 흔적 없음 |

이미 완료된 #96/#104/#107/#114/#128은 앞선 세션에서 닫혀 있었고, #62 본문만 옛 상태였다.

---

## 코드 변경 상태 (git)

### Uncommitted

없음(작업트리 clean). 이번 세션은 GitHub 이슈-브랜치 조작이 대부분이라 코드 변경이 없다.

### 이번 세션 관련 커밋 - 전부 main에 반영됨

| SHA | 내용 |
|---|---|
| `0846cb1` | PR #151 squash 머지 - 눈누 official_url 오염 전수 검증 도구(#150) |
| `f6ae8e8` | (PR #151에 포함) 재스캔 v2 결과 - `auto_fix_safe` 164건 확정 |
| `a45da8d` | (PR #151에 포함) 검증된 제작사 호스트 등록부로 자동 정정 범위 확장 |
| `e7637cf`, `a0cd889` | #150 계획-설계 문서 |

---

## 진행 중 작업의 실측 상태 (#150)

### v2 스캔 결과 (dev, 1,110종 전수, exit 0)

```
match 925 / mismatch 184 / no_link 1
keep 925 / auto_fix_safe 174 / manual_review 10 / nullify(보류) 1
오염: noonnu_account 172 (prod 실측 172와 일치)
```

오염 172종 조치 분포: `auto_fix_safe` **164** / `manual_review` 7(플랫폼 호스팅 의도적 제외) / `nullify` 1(`google-sans-flex`, 본문에 외부 링크 없음).

### 결정 사항 (뒤집지 말 것)

| # | 결정 | 근거 |
|---|---|---|
| 1 | `auto_fix_safe`는 AND 조건(앵커 근거 + 도메인 근거) | OR면 172종을 또 다른 잘못된 값으로 바꿀 위험 |
| 2 | 검증된 제작사 호스트 등록부 25개 도입 | 한글 제작사명이 영문 도메인과 매칭되지 않아 전부 manual_review로 떨어지던 문제 해소. 앵커 근거는 여전히 필수 |
| 3 | 오염 판정을 `auto_fix_safe` 판정보다 먼저 수행 | 두 값이 똑같이 오염돼도 `match`로 통과하던 구조(Codex 리뷰 Must-fix) |
| 4 | `nullify`는 이번 범위 밖 | `fonts.official_url`이 NOT NULL 제약이라 마이그레이션 0027이 별도로 필요 |
| 5 | #120은 수집 트래커, 화면 고도화는 #152 | 한 이슈에 수집-표시가 섞여 진행 상태를 읽을 수 없었음 |

⚠️ 재추출 값이 항상 정답은 아니다. `아임크리수진체`는 재추출 값이 `drive.google.com`인데 기존 `imcrefont.com`이 더 공식적이라 `manual_review`로 걸렸다.

---

## 블로커 - 미해결 이슈

| # | 이슈 | 영향 | 상태 |
|---|---|---|---|
| 1 | ⚠️ finding 적재 경로 미구현(#150 미해결 갭) | 정정 적용 차단 | 다음 세션 MUST |
| 2 | ⚠️ prod 172종 official_url 오염 유지 중 | 사용자 제보(#148) 증상이 실서비스에 살아 있음 | #150 완료까지 지속 |
| 3 | develop 처리 방침 미정 | 브랜치 위생(#153) 차단 | 사용자 결정 대기 |
| 4 | ⚠️ 정적 사이트라 DB만 고쳐서는 화면이 안 바뀜 | prod 적용 후 재배포 필수 | 절차에 포함 |

---

## 다음 단계 (Next)

🔴 **MUST**:
- [ ] 사용자에게 위 "미결정 사항" 2건 확인
- [ ] #150 finding 적재 경로 구현(정정 대상 `auto_fix_safe` 164건 확정 상태)
- [ ] dev 정정 적용 + 쓰기 후 재조회 실측
- [ ] 오염 172종 `license_verified`를 false로 강등(사용자 결정 사항)

🟡 **SHOULD**:
- [ ] prod 승인 패키지 작성(변경 건수, 필드별 건수, 샘플 10건, 전체 slug, 역방향 manifest, 검증 쿼리) 후 쿼리 전문 승인 요청
- [ ] prod 적용 + `scripts/deploy.sh` 재배포 -> fontagit.com 실화면에서 제작사 링크 확인 -> #148 닫기
- [ ] `manual_review` 10건 사람 판단
- [ ] 계획 문서 체크박스 재동기화(현재 미체크 22/50)
- [ ] progress.md에 이번 정리 세션 기록(`/progress`)

🟢 **NICE-TO-DO**:
- [ ] `NEXT_PUBLIC_SUPABASE_PASWORD` 키 개명(DB 비밀번호가 웹 번들 노출 접두사를 쓰고 있음)
- [ ] 오염 판정 호스트 목록이 `audit_noonnu.py`와 `noonnu_url_audit.py`에 중복 정의된 것 통합
- [ ] `_registrable_domain_label`이 Public Suffix List 미사용 휴리스틱(`com.au` 등 미처리)
- [ ] #153의 squash 병합 브랜치 정리(`cleaning-merged-branches` 절차)

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---|---|
| 이 핸드오프 | `docs/superpowers/handoff/2026-07-30-1359-issue-cleanup-and-decisions.md` |
| 직전 기술 재개점 | `docs/superpowers/handoff/2026-07-29-1135-noonnu-official-url-audit.md` |
| 계획 | `docs/superpowers/plans/2026-07-28-noonnu-official-url-audit.md` (미체크 22/50) |
| 설계 | `docs/superpowers/specs/2026-07-28-noonnu-official-url-audit-design.md` |
| 스캔 결과(v1, 호스트 32개 수렴표) | `docs/progress/2026-07-29-noonnu-url-scan-result.md` |
| 스캔 도구 | `apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py` |
| 감사 로직 | `apps/pipeline/src/fontagit_pipeline/noonnu_url_audit.py` |
| 수집기(PR #149 수정분) | `apps/pipeline/src/fontagit_pipeline/audit_noonnu.py` |
| 진행 일지 | `docs/progress/progress.md` |

---

## 검증 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| 브랜치 정리 | ✅ 완료 | `git branch --list feat/noonnu*` 비어 있음, 원격 `- [deleted]` 출력 |
| main-origin 동기 | ✅ 완료 | `git rev-list --left-right --count origin/main...main` -> `0 0` |
| 이슈 하위 연결 | ✅ 완료 | GraphQL 조회 `subIssues.totalCount = 24` |
| 이슈 코멘트-본문 | ✅ 완료 | 코멘트 URL 4건 반환 확인 |
| dev 정정 적용 | ⚠️ 미실행 | finding 적재 경로 미구현 |
| prod 정정 | ⚠️ 미실행 | 승인 패키지 미작성 |
| 웹 테스트-빌드 | ⚠️ 미실행 | 이번 세션 코드 변경 없음 |

---

## 재개 프롬프트

```
이전 세션의 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/superpowers/handoff/2026-07-30-1359-issue-cleanup-and-decisions.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. docs/superpowers/handoff/2026-07-29-1135-noonnu-official-url-audit.md (직전 기술 재개점)와
   docs/superpowers/plans/2026-07-28-noonnu-official-url-audit.md (계획, 미체크 22/50)를 읽는다
3. `git status && git log --oneline -5 && gh issue view 150`로 현재 상태 확인
4. 핸드오프의 "미결정 사항" 2건(develop 처리 방침, #150 prod 쓰기 승인 범위)을 먼저 사용자에게 묻는다
5. 답을 받은 뒤 "다음 단계 -> MUST"부터 시작한다
6. 사용자 제약을 반드시 준수한다: prod 쓰기는 쿼리 전문 승인 후 실행, PR 머지는 사용자 승인 후,
   브랜치 폐기 같은 되돌리기 부담 작업은 임의 실행 금지
7. "결정 사항" 표의 항목은 뒤집지 않는다(변경하려면 사용자 확인 필수)

진행 전에 핸드오프 파일을 읽었음을 확인하고, 미결정 2건을 어떤 형태로 물을지 한 줄로 보고해주세요.
```
