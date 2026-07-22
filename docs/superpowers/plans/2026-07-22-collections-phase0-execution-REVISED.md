# 컬렉션 0단계 Task 2~3 실행 경로 확정 (REVISED)

> **상태**: 실코드 검증 완료. 6단계 파이프라인 정확 매핑 + 3대 갭(assert_safe 게이트, 메타데이터 승인 경로, manifest 조립 CLI) 해결설계 포함. 원본 plan과 실제 코드 배선의 어긋남 명시.

---

## 원본 plan 대비 변경점

| 항목 | 원본 | 실제 코드 | 영향 |
|------|------|---------|------|
| **Step 1: prod 기준선** | `--source prod-public`로 추측 | `main_audit_export_baseline` 확인됨 | ✅ 맞음 |
| **Step 2: bootstrap** | `main_audit_bootstrap` 추측 | ✅ 확인됨 | ✅ 맞음 |
| **Step 3: 감사 실행** | `main_audit_run --stage metadata` | ✅ 확인됨 | ✅ 맞음 |
| **Step 3 게이트** | 미언급 | `assert_safe()` 검사: needs_review/target > 10% 시 exit 3 | ⚠️ **갭 3** |
| **Step 4: 승인** | "metadata finding을 approve" | `approve_finding` 메서드가 SupabaseAuditStore에 없음 (InMemoryAuditStore만) | ⚠️ **갭 4** |
| **Step 5: manifest 조립** | `build_manifest` 존재 | CLI 서브커맨드 없음 (함수만 존재) | ⚠️ **갭 5** |
| **Step 6: 적용** | `main_audit_manifest_apply` | ✅ 확인됨 | ✅ 맞음 |

---

## 6단계 파이프라인 확정

### Step 1: prod 기준선 스냅샷 생성
**함수**: `main_audit_export_baseline` (`__main__.py:395`)  
**명령어**:
```bash
python -m fontagit_pipeline font-audit-export-baseline \
  --source prod-public \
  --out output/audit/prod-baseline.json
```
**자격증명**: `SUPABASE_URL` + `SUPABASE_ANON_KEY` (공개 읽기)  
**입력**: 없음 (prod 공개 API에서 모든 폰트 조회)  
**산출**: `prod-baseline.json` (모든 폰트의 ID, slug, 기본값)  
**검증**: 
- 반환 exit code 0
- `prod-baseline.json` 파일 생성됨
- 파일에 1,240개 폰트 기록

---

### Step 2: bootstrap-manifest 생성
**함수**: `main_audit_bootstrap` (`__main__.py:429`)  
**명령어**:
```bash
python -m fontagit_pipeline font-audit-bootstrap \
  --prod-snapshot output/audit/prod-baseline.json \
  --out output/audit/bootstrap-manifest.json
```
**입력**:
- `--prod-snapshot`: Step 1 산출
- `output/tier-a.json`: 존재함 (공식 출처)
- `output/tier-b-noonnu-seed.json`: 존재함 (눈누 seed)

**산출**: `bootstrap-manifest.json` (source_key 매핑: matched/unmatched/conflicts)  
**검증**:
- exit code 0
- manifest 완성도 로그 확인

---

### Step 3: 감사 실행 (metadata stage)
**함수**: `main_audit_run` (`__main__.py:465`)  
**명령어**:
```bash
docker run --rm \
  -e SUPABASE_DEV_URL -e SUPABASE_DEV_SECRET_KEY \
  -v $(pwd):/repo -w /repo/apps/pipeline \
  fontagit-pipeline:local \
  python -m fontagit_pipeline font-audit-run \
    --stage metadata \
    --bootstrap output/audit/bootstrap-manifest.json \
    --limit 50 \
    --out output/audit/pilot-metadata.json
```

> ⚠️ **마운트-venv 주의(MF1)**: `-v $(pwd):/repo`는 이 PR의 Dockerfile 수정(venv를 `/opt/venv`로 이전)이 전제다. venv가 `/repo/apps/pipeline/.venv`에 있으면 이 마운트가 가려 파이프라인이 깨진다(실측 확인). `/opt/venv`면 마운트에도 살아남고 editable 설치라 호스트 최신 소스를 읽는다. 보수적 대안: repo 전체 대신 `-v $(pwd)/apps/pipeline/output:/repo/apps/pipeline/output`만 마운트 + 이미지 재빌드(dry-run으로 검증됨).

**자격증명**:
- `SUPABASE_DEV_URL`: dev 클라우드 RPC URL
- `SUPABASE_DEV_SECRET_KEY`: dev service role secret

**입력**:
- `--bootstrap`: Step 2 산출 (target 리스트)
- `--limit N`: 파일럿 50 또는 전체 1110

**산출**: `audit/pilot-metadata.json` (audit report)  
**내부 동작**:
1. bootstrap에서 N개 타겟 선택 (`select_pilot`)
2. Linux 확인 (mac이면 Docker 필수) ← **코드 gate: `sys.platform.startswith("linux")`**
3. 각 타겟마다 `run_metadata_audit` 호출:
   - 눈누 메타데이터 크롤 (Task C backoff 적용)
   - `compare_metadata` 호출 → findings 생성
   - **핵심**: tags/weights finding은 `auto_applicable=False` 고정 ← **갭 3 원인**
4. dev DB에 run/snapshots/findings 저장 (Content-Profile: fontagit 필수)
5. `report.assert_safe()` 호출
   - **⚠️ GATE**: `needs_review_count / target_count > 0.10` → `AuditGateError` 발생
   - 메타데이터는 tags/weights가 모두 needs_review → 전체 50개 중 대부분 needs_review
   - 예상: 50 * 90% = 45 needs_review → 45/50 = 90% > 10% → GATE 실패

**검증**:
- exit code 0 (또는 3 if assert_safe fails)
- `pilot-metadata.json` 생성됨

---

### Step 3.5: assert_safe 게이트 문제 & 해결 ⚠️ **갭 3**

**문제**:
```python
def assert_safe(self) -> None:
    if self.needs_review_count / self.target_count > 0.10:
        raise AuditGateError("pilot review ratio exceeds 10%")
```

메타데이터 감사에서:
- tags/weights finding은 `auto_applicable=False` (파일:  `audit_metadata.py:365`)
- `auto_applicable=False` → 기본값 "pending" 상태 → 결과적으로 needs_review 카운트
- 실제 비율: 파일럿 50 기준 약 40~50개 needs_review (80~100%)
- 현재 게이트는 10% 초과 시 차단 → 메타데이터 스테이지에서 항상 실패

**해결 방안** (최소-안전 변경):

> ⚠️ **폐기된 초안(임계값 50% 상향)**: needs_review가 80~100%로 예상되므로 50%로 올려도 여전히 차단된다. 게다가 한 폰트에서 tags-weights finding이 각각 나오면 needs_review 분자가 대상 폰트 수를 넘을 수도 있다. 임의 비율 완화는 근거도 없고 문제도 해결 못 함(Codex Should-fix 지적, 동의).

**채택안: metadata stage는 needs_review 비율 게이트를 SKIP하고, 실제 위험 지표(수집 실패 비율)로 판정**
- 근거: needs_review는 metadata에서 **설계된 정상 결과**(`auto_applicable=False` 정책)이지 위험 신호가 아니다. 위험 신호는 "크롤 실패/비정상 finding"(broken/error)이다.
- 변경(`audit_runner.py` assert_safe):
  - `target_count > 0`, `pending_count == 0` 체크는 유지.
  - metadata stage: needs_review 비율 검사 **건너뜀**. 대신 `broken_count / target_count > 임계값`(예: 0.10)이면 차단(실제 수집 실패율 기준).
  - legal/script stage: 기존 10% needs_review 게이트 유지.
- ⚠️ **구현 전 확인 필수**: `auto_applicable=False` finding이 실제로 어떤 status로 집계되는지(`pending` vs `needs_review`). 만약 `pending`으로 잡히면 `pending_count == 0` 체크가 먼저 터지므로, 그 카운트 정의(`audit_runner.py`의 counts 산출부)도 함께 확인해 metadata의 정상 needs_review가 pending으로 오분류되지 않게 한다.
- 검증: 기존 legal/script 게이트 테스트 유지 + metadata에서 needs_review 100%여도 통과하되 broken 과다면 차단하는 테스트 추가.

---

### Step 4: 메타데이터 finding 승인 & manifest 조립 ⚠️ **갭 4, 5**

**문제**:
1. **갭 4**: `approve_finding(finding_id)` 메서드가 SupabaseAuditStore에 없음
   - 현재: `InMemoryAuditStore`에만 구현 (`audit_store.py:144`)
   - 메타데이터 findings를 DB에서 "approved" 상태로 업데이트할 방법 없음

2. **갭 5**: `build_manifest` 함수는 있지만 CLI가 없음
   - 함수 시그니처: `build_manifest(run, approved_findings, current_rows) → ManifestBundle`
   - 입력 요구: run (dict), approved_findings (status="approved" finding들), current_rows (evidence_snapshots 조인)
   - 호출처: 테스트 fixture만 (`test_audit_manifest.py`)

**해결 설계**:

#### 4.1: SupabaseAuditStore에 approve_finding 추가
**파일**: `audit_store.py` (SupabaseAuditStore 클래스 내)

**메서드**:
```python
def approve_finding(self, finding_id: UUID) -> None:
    """메타데이터/스크립트 finding을 DB에서 approved로 표시한다."""
    self._schema.table("font_audit_findings").update(
        {
            "status": "approved",
            "reviewed_by": "system-metadata-approval",  # 또는 CLI --reviewed-by
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
    ).eq("id", str(finding_id)).execute()
```

**주의**: 
- approved 상태는 manifest build 입력으로만 사용 (fonts 테이블 수정 아님)
- 작은 변경 (메서드 추가만)

#### 4.2: manifest build CLI 서브커맨드 추가
**파일**: `__main__.py` (font-audit-manifest 하위)

**명령어**:
```bash
python -m fontagit_pipeline font-audit-manifest build \
  --run-id <UUID> \
  --stage metadata \
  --out output/audit/pilot-manifest/ \
  --approved
```

**CLI 구현 스텝**:
1. Supabase에서 run, approved findings, current rows 조회
   - run: `font_audit_runs` where id=run_id
   - approved findings: `font_audit_findings` where run_id=run_id AND status="approved"
   - current rows: `fonts` with joined `evidence_snapshots`
2. `build_manifest(run_dict, approved_findings, current_rows)` 호출
3. `write_manifest_bundle(bundle, out)` 호출
4. 결과: `out/forward.json` + `forward.sha256` 등

**새 DB 조회 메서드** (SupabaseAuditStore에 추가):
```python
def get_run_with_findings(self, run_id: UUID, stage: str) -> tuple[dict, list[dict]]:
    """run과 approved findings를 한 번에 조회한다."""
    # font_audit_runs에서 run 조회
    # font_audit_findings에서 status="approved" 조회
    # fonts + evidence_snapshots 조인 조회
    pass
```

---

### Step 5: dev 적용 (파일럿)
**함수**: `main_audit_manifest_apply` (`__main__.py:589`)  
**명령어**:
```bash
python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/audit/pilot-manifest/forward.json \
  --sha256 output/audit/pilot-manifest/forward.sha256 \
  --target dev \
  --confirm-hash <sha256 값>
```

**자격증명**: `SUPABASE_DEV_URL` + `SUPABASE_DEV_SECRET_KEY` (service role)  
**검증**:
- exit code 0
- RPC `apply_font_audit_manifest` 성공
- `dev fonts` 테이블에 tags/weights 업데이트됨 (SELECT 확인)

---

### Step 6: 전체 1,110종 실행 및 dev 반영
Step 3~5를 `--limit 1110`으로 반복.

---

## 갭별 최소 해결안

### 갭 3: assert_safe 게이트 (metadata needs_review 차단)
**파일**: `apps/pipeline/src/fontagit_pipeline/audit_runner.py:225~235`  
**변경**:
```python
def assert_safe(self) -> None:
    if self.target_count == 0:
        raise AuditGateError("target count must be greater than zero")
    if self.pending_count:
        raise AuditGateError("pending remains")
    
    # metadata stage는 needs_review 비율이 높을 수 있음 (auto_applicable=False 정책)
    threshold = 0.50 if self.stage == "metadata" else 0.10
    if self.target_count and self.needs_review_count / self.target_count > threshold:
        raise AuditGateError(f"review ratio exceeds {threshold*100:.0f}%")
```

**테스트**:
- `test_audit_runner.py`에 새 테스트 추가:
  - metadata stage, needs_review 50% 케이스 → assert_safe 통과
  - legal stage, needs_review 11% 케이스 → assert_safe 실패

**커밋**: `fix: metadata stage assert_safe 임계값 50%로 상향`

---

### 갭 4: SupabaseAuditStore.approve_finding 추가 (⚠️ 검수 게이트 보존 필수)

> **거버넌스 원칙(자동 일괄 승인 금지)**: 프로젝트 정책상 tags/weights finding은 `auto_applicable=False` 검수 게이트를 거친다([[project-font-audit-governance]]). 따라서 approve는 **명시적으로 지정된 finding-id 1건씩**만, **검증 후 조건부**로 처리한다. "run의 모든 finding 일괄 approved"는 게이트 우회이므로 금지.

**파일**: `apps/pipeline/src/fontagit_pipeline/audit_store.py`

**추가 메서드** (검증 + 조건부 전이):
```python
def approve_finding(self, finding_id: UUID, *, reviewed_by: str, stage: str) -> None:
    """명시적으로 선택된 finding 1건을 검증 후 승인한다. dev 환경 only.

    검증: finding이 존재하고, stage 일치, field_name in {tags, weights},
    현재 status='needs_review' 여야 함. 위반 시 예외.
    전이: status='needs_review' AND id=finding_id 조건부 UPDATE로만 approved
    (조건 불충족 시 0건 갱신 → 재실행/동시성 안전).
    """
    row = self._schema.table("font_audit_findings").select(
        "id, stage, field_name, status"
    ).eq("id", str(finding_id)).limit(1).execute().data
    if not row:
        raise ValueError("finding이 존재하지 않습니다")
    f = row[0]
    if f["stage"] != stage or f["field_name"] not in {"tags", "weights"}:
        raise ValueError("승인 대상이 아닌 finding(stage/field 불일치)")
    if f["status"] != "needs_review":
        raise ValueError(f"needs_review 상태만 승인 가능(현재 {f['status']})")
    updated = self._schema.table("font_audit_findings").update(
        {"status": "approved", "reviewed_by": reviewed_by,
         "reviewed_at": datetime.now(UTC).isoformat()},
    ).eq("id", str(finding_id)).eq("status", "needs_review").execute().data
    if not updated:
        raise ValueError("조건부 승인 실패(상태가 바뀌었을 수 있음)")
```

**주의**:
- `reviewed_by`는 CLI 인자(`--reviewed-by`)로 실제 검수자 식별자를 받는다. 하드코딩된 "system" 문자열로 사람 검수를 위장하지 않는다. 운영자가 검수 목록을 보고 승인하는 흐름(list → 선택 → approve)을 전제.
- 승인은 **build CLI와 분리된 명시 단계**. build CLI(갭 5)는 이미 approved인 finding만 조회-조립하며, 스스로 승인하지 않는다.

**테스트**:
- `test_audit_store.py`: needs_review finding 승인 → approved 확인 / 이미 approved면 예외 / field_name이 허용 밖이면 예외 / stage 불일치 예외

**커밋**: `feat: SupabaseAuditStore.approve_finding (검증+조건부 전이, 검수 게이트 보존)`

---

### 갭 5: font-audit-manifest build CLI 추가
**파일**: 
- `apps/pipeline/src/fontagit_pipeline/__main__.py` (서브커맨드 추가)
- `apps/pipeline/src/fontagit_pipeline/audit_manifest.py` (필요시 헬퍼)
- `apps/pipeline/src/fontagit_pipeline/audit_store.py` (DB 조회 메서드)

**Step 1: DB 조회 메서드 추가** (audit_store.py)
```python
def get_run_for_manifest(self, run_id: UUID) -> dict[str, object]:
    """manifest build용 run 정보를 조회한다."""
    data = self._schema.table("font_audit_runs").select("*").eq("id", str(run_id)).limit(1).execute().data
    # 검증 & 반환

def get_approved_findings_for_run(self, run_id: UUID) -> list[dict[str, object]]:
    """해당 run의 모든 approved finding을 조회한다."""
    data = self._schema.table("font_audit_findings").select("*").eq("run_id", str(run_id)).eq("status", "approved").execute().data
    # 검증 & 반환

def get_current_fonts_with_snapshots(self, run_id: UUID) -> list[dict[str, object]]:
    """fonts + evidence_snapshots 조인으로 manifest build용 current_rows 생성."""
    # RPC 또는 여러 쿼리 조합으로 joined data 반환
```

**Step 2: main_audit_manifest_build 함수** (__main__.py)
```python
def main_audit_manifest_build(args: argparse.Namespace) -> int:
    """승인 findings와 현재값을 manifest로 조립한다."""
    from fontagit_pipeline.audit_manifest import ManifestError, build_manifest, write_manifest_bundle
    from fontagit_pipeline.audit_store import SupabaseAuditStore
    from fontagit_pipeline.config import load_audit_settings
    
    try:
        settings = load_audit_settings()
        dev_url, dev_secret = settings.dev_write_credentials()
        store = SupabaseAuditStore.from_dev_credentials(dev_url, dev_secret)
        
        run_dict = store.get_run_for_manifest(args.run_id)
        approved_findings = store.get_approved_findings_for_run(args.run_id)
        current_rows = store.get_current_fonts_with_snapshots(args.run_id)
        
        if not approved_findings:
            raise ManifestError("run에 approved finding이 없습니다")
        
        bundle = build_manifest(run_dict, approved_findings, current_rows)
        paths = write_manifest_bundle(bundle, args.out)
        
    except (ManifestError, OSError, ValueError) as exc:
        logger.error("manifest build 실패: %s", exc)
        return 3
    
    logger.info("manifest 생성 완료: %s", args.out)
    return 0
```

**Step 3: 서브커맨드 파싱 추가** (__main__.py, manifest_subparsers)
```python
manifest_build_parser = manifest_subparsers.add_parser("build")
manifest_build_parser.add_argument("--run-id", type=UUID, required=True, help="감사 run ID")
manifest_build_parser.add_argument("--out", type=Path, required=True, help="manifest 출력 디렉토리")
manifest_build_parser.set_defaults(func=main_audit_manifest_build)
```

**명령어**:
```bash
python -m fontagit_pipeline font-audit-manifest build \
  --run-id <run-uuid> \
  --out output/audit/pilot-manifest/
```

**테스트**:
- `test_audit_manifest.py`에 `test_build_cli_from_approved_findings()` 추가
- audit-run 산출 → approve_finding loop → build CLI → manifest 파일 생성 검증

**커밋**: `feat: font-audit-manifest build CLI (metadata 승인 → manifest 변환)`

---

## Vertical Slice Task 분해

### Task 1: assert_safe 게이트 완화 (30분)
**목표**: metadata stage의 needs_review 비율 > 10% 차단 제거  
**변경**: `audit_runner.py:231` stage별 조건 분기  
**검증**: 기존 legal 게이트 + 새 metadata 테스트 green

### Task 2: SupabaseAuditStore.approve_finding (20분)
**목표**: metadata findings를 approved 상태로 DB 업데이트  
**변경**: `audit_store.py`에 메서드 추가  
**검증**: unit test

### Task 3: audit_store DB 조회 헬퍼 (60분)
**목표**: manifest build용 run/findings/current_rows 조회  
**변경**: `audit_store.py`에 3개 메서드 추가 (RPC 또는 query 조합)  
**검증**: integration test (dev DB)

### Task 4: font-audit-manifest build CLI (90분)
**목표**: approved findings → manifest 파일 생성  
**변경**: `__main__.py`, `audit_manifest.py` (필요시)  
**검증**: unit test + docker integration test

### Task 5: Docker 이미지 & 파일럿 (90분)
**목표**: 도커에서 50종 end-to-end 실행  
**변경**: Task A~C 커밋 기준, 추가 변경 없음  
**검증**: 파일럿 50종 태그/가중치 dev 업데이트 확인

---

## 완료 기준

- [ ] **갭 3**: assert_safe 조정 + 테스트 green
- [ ] **갭 4**: approve_finding 메서드 + 테스트 green
- [ ] **갭 5**: build CLI + end-to-end 테스트 green
- [ ] **파일럿**: 도커에서 50종 metadata 감사 → manifest → dev apply 성공
- [ ] **전체**: 1,110종 dev 반영, tags 채움률 70%+, weights 90%+

---

## 미해결/후속

- **Task 3 RPC vs Query**: dev DB에서 현재값 조회 방식 (RPC vs 다중 select) 결정 필요
- **prod 승인 게이트**: dev 검증 완료 후 prod 적용 시 추가 approved-hash/approval-id 게이트 설계
- **B단계**: 채워진 metadata로 규칙 엔진 + 자동 컬렉션 materialize

---

## 확인 필요 항목

1. ⚠️ `get_current_fonts_with_snapshots()`: evidence_snapshots 조인 RPC 여부 (현재 SQL 불명)
2. ⚠️ Docker 환경에서 Dev secret key 주입 방식 (--env-file vs export)
3. ⚠️ manifest build 시 font_id 중복 처리 (현재 before/after 검증 로직)
