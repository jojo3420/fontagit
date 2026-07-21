# 세션 핸드오프 — 2026-07-21 17:47 KST

> **모드**: superpowers-plan
> **Feature**: Tier A(Google Fonts) URL 백필 (#89)
> **이전 세션 종결 사유**: 컨텍스트 포화 (배포 2회 + 이슈 정리 + UI 디버깅 + 설계까지 진행) → 신선한 세션에서 구현 권장

## 한 줄 요약

#89 Tier A URL 백필의 설계를 적대적 검증까지 거쳐 확정-커밋했다(원설계 전제가 틀렸음을 발견해 목표 재정의). 다음 세션은 설계 문서의 **Phase 0 사전 검증 4건**을 먼저 수행한 뒤 구현(writing-plans)으로 넘어가면 된다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** — 컨텍스트 복원 순서:

1. **이 핸드오프 파일을 읽는다**
2. **설계 문서를 읽는다**: `docs/superpowers/specs/2026-07-21-tier-a-url-backfill-design.md` (핵심 산출물, Phase 0 착수 조건 포함)
3. **현재 상태 확인**: `git status && git log --oneline -6` (브랜치 develop, 작업트리 clean)
4. **아래 "다음 단계 → MUST"의 Phase 0부터 시작**

---

## 작업 컨텍스트

### 이번 세션이 한 일 (완료, 재개 불필요)

- v0.2.0 배포: develop→main 승격(PR #93)으로 /fonts 섹션 계층화 등 prod 반영
- /fonts 개요 모드 UI 버그 3건 hotfix: v0.2.1(PR #94, 머지+배포+develop 동기화 완료)
- GitHub 이슈 정리: 열린 이슈 22→19 (#91/#34/#36 닫기, #37/#62/#56 최신화)
- progress 일지 갱신(`333478b`)
- **#89 설계 + 적대적 검증(진행 중이던 작업 = 재개 대상)**

### #89 현재 상태

설계 문서 작성-커밋 완료(`e0d4873`). 적대적 검증(deep-reasoner)으로 원설계 전제가 틀렸음을 발견해 설계를 보정했다. **구현은 미착수.** Phase 0 사전 검증이 착수 조건.

### 사용자 제약 - 금지사항 (반드시 준수)

🔴 **반드시 (must)**:
- prod(실서비스) DB 직접 쓰기는 사용자 확인 필수 — dry-run + 사람 게이트 없이 자동 실행 금지
- 백필 단계에서 자동 verified 부여 금지 (거버넌스 자동승인 금지, [[project-font-audit-governance]])
- **Phase 0(사전 검증) 미완료 시 구현 착수 금지** (설계 문서 명시)

---

## 결정 사항 (Decisions) — 뒤집지 말 것 (변경 시 사용자 확인)

| # | 결정 | 근거 | 누가 |
|---|------|------|------|
| 1 | dev 먼저 백필→검증→prod 승격(2단계) | prod 직접 쓰기 위험, #90 OFL 승격과 동일 패턴 | 사용자 |
| 2 | 백필은 데이터만 채우고 승인 판정은 기존 감사 로직 재실행 | 거버넌스(자동승인 금지) 유지 | 사용자 |
| 3 | 별도 CLI 스크립트(`google_fonts_backfill`) | 일회성 작업, 감사 파이프라인과 분리 | 사용자 |
| 4 | foundry 필드 이번 범위 제외 | 후보 생성과 무관, download_url-license_source_url만 필요 | 사용자 |
| 5 | 목표를 "needs_review 도달(pending 탈출)"로 재정의, verified는 후속 | 적대적 검증: URL 백필만으론 verified 불가 | 검증 결과 |

## 적대적 검증 핵심 결과 (설계 전제 수정 근거)

| 가정 | 판정 | 근거 |
|------|------|------|
| URL만 채우면 pending→verified | **거짓** | `audit_runner.py:1642` — license 후보가 source="existing"이면 자동 needs_review 강제. verified 불가 |
| prod 쓰기 경로 존재 | **거짓** | `google_fonts_backfill` CLI 미구현, prod 쓰기는 Tier B 전용 noonnu_publish만. prod service-role 키 없음 |
| Tier A 128종 전부 OFL | **불명** | 라이선스 분포 미검증. Apache/UFL 섞이면 license URL 규칙 깨짐 |
| files["regular"]로 download_url | **참** | `models.py:8-19`, `test_client.py:29` |
| legal 감사 macOS 실행 가능 | **참** | `__main__.py:485` Linux 게이트는 metadata 전용 |

---

## 블로커 - 미해결 이슈 (Phase 0에서 해소해야 착수 가능)

| # | 이슈 | 영향 | 다음 시도 |
|---|------|------|----------|
| 1 | Tier A 128종 라이선스 분포 미검증 | license_source_url 규칙 확정 불가 | bootstrap-manifest.json Tier A를 google/fonts로 확인, OFL/Apache/UFL 비율 파악 |
| 2 | OFL verified 트랙(#88, 132종)과 Tier A pending(128종) 중복 미확인 | 실제 백필 대상 수 불확정 | 두 집합 교집합 조회(이미 verified면 제외) |
| 3 | needs_review→verified 승격 경로 미정 | 2차 목표 방법 불명 | ofl_verify 재사용 vs registry 등록 vs 사람검수 결정 |
| 4 | prod service-role 키 위치/config 필드명 미확인 | prod 승격 단계 구현 불가 | config.py + env SSoT([[ref-env-file-ssot]]) 확인 |
| 5 | license_source_url 최종 URL 형식 미확정 | 필드 매핑 확정 불가 | Phase 0-#1 라이선스 분포 확인 후 결정 |

---

## 다음 단계 (Next)

🔴 **MUST** (착수 조건 = Phase 0 사전 검증):
- [ ] Tier A 128종 라이선스 분포 확인 (블로커 #1)
- [ ] OFL verified 트랙(#88)과 중복 범위 확인 (블로커 #2)
- [ ] needs_review→verified 경로 결정 (블로커 #3)
- [ ] prod service-role 키 확인 (블로커 #4)

🟡 **SHOULD** (Phase 0 통과 후):
- [ ] writing-plans 스킬로 구현 계획 작성
- [ ] `google_fonts_backfill` CLI 구현 (dev): 조회→fetch_webfonts 매칭→필드 매핑→dry-run→PATCH
- [ ] family name 정규화 매칭 단위 테스트

🟢 **NICE-TO-DO**:
- [ ] #28 컬렉션 시드 (다른 착수 후보, 조사 완료 — 폰트 200종/컬렉션 10개, 큐레이션 브레인스토밍 필요)

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| 설계 문서 (#89) | `docs/superpowers/specs/2026-07-21-tier-a-url-backfill-design.md` |
| 재사용 유틸 (API 호출) | `apps/pipeline/src/fontagit_pipeline/client.py::fetch_webfonts` |
| API 응답 모델 | `apps/pipeline/src/fontagit_pipeline/models.py:8-19` (GoogleFontRaw.files) |
| 감사 후보/판정 로직 | `apps/pipeline/src/fontagit_pipeline/audit_runner.py` (~1395 _all_candidates, ~1642 license 판정, ~1808 _candidate_matches_target) |
| CLI 진입점 | `apps/pipeline/src/fontagit_pipeline/__main__.py` (font-audit-run ~846) |
| 감사 재실행 | `python -m fontagit_pipeline font-audit-run --stage legal --bootstrap output/audit/bootstrap-manifest.json` |
| 핸드오프 (이 파일) | `docs/superpowers/handoff/2026-07-21-1747-tier-a-url-backfill.md` |

---

## 검증 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| #89 설계 문서 | ✅ 작성-커밋 (`e0d4873`) | 적대적 검증 반영 |
| 적대적 검증 | ✅ 완료 (deep-reasoner) | 결함 3건 발견, 설계 보정 |
| Phase 0 사전 검증 | ⚠️ 미실행 | 착수 조건, 다음 세션 MUST |
| 구현 (CLI) | ⚠️ 미착수 | Phase 0 통과 후 |
| prod v0.2.1 배포 | ✅ 라이브 | fontagit.com 200, 별개 완료 작업 |

---

## 재개 프롬프트 (다음 세션에 그대로 복사-붙여넣기)

```
이전 세션의 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/superpowers/handoff/2026-07-21-1747-tier-a-url-backfill.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. 설계 문서(docs/superpowers/specs/2026-07-21-tier-a-url-backfill-design.md)를 읽는다
3. `git status` `git log --oneline -6`로 현재 상태 확인 (브랜치 develop)
4. 핸드오프의 "다음 단계 → MUST"(Phase 0 사전 검증 4건)부터 시작
5. 사용자 제약(prod 직접쓰기 확인 필수, 자동 verified 금지, Phase 0 미완료 시 착수 금지) 준수
6. 결정 사항 표(1~5)는 뒤집지 않음 (변경 시 사용자 확인)

Phase 0 사전 검증부터 시작하되, 4건 중 어디부터 할지 한 줄로 보고해주세요.
```

---

✅ 핸드오프 메모 작성 완료. 다음 세션은 위 재개 프롬프트로 시작.
