#!/usr/bin/env bash
# metadata 감사 체인 무인 실행 (dev 전체 Tier B)
#
# Usage:
#   ./scripts/audit-chain.sh                    # 기본: 전체 체인 (baseline → bootstrap → apply → run → auto-approve → manifest build → manifest apply)
#   ./scripts/audit-chain.sh /path/to/output    # 산출물 디렉터리 지정
#   ./scripts/audit-chain.sh --run-id <uuid>    # 기존 run 재사용 (감사 이전 단계 스킵, auto-approve부터 시작)
#   ./scripts/audit-chain.sh --help             # 이 도움말
#
# 예상 소요시간:
#   - 전체 체인: 1,110종 × 요청당 1.5초 크롤 딜레이 = 약 1.5~3시간 (네트워크 지연 포함)
#   - --run-id로 기존 감사 재사용: manifest 생성~적용 = 약 5분
#
# 재시도 정책:
#   - HTTP 429/503은 audit_http.py에 지수 backoff 내장 (base 1s, max 30s, 최대 3회)
#   - 체인 수준 재시도 없음 (멱등하므로 전체 스크립트 재실행 가능)
#   - 중간 단계 exit code가 0이 아니면 즉시 중단
#
# 산출물 구조:
#   output/audit/full-run-{timestamp}/
#   ├── chain.log                        (전 단계 상세 로그)
#   ├── baseline.json                    (공개 기준선) + .sha256
#   ├── bootstrap-manifest.json          (크롤 대상 manifest) + .sha256
#   ├── audit-report.json                (감사 결과) + .sha256, audit-report.md
#   └── manifest/
#       ├── index.json                   (청크 메타데이터)
#       ├── chunk-001/
#       │   ├── forward.json + forward.sha256
#       │   └── reverse.json + reverse.sha256
#       ├── chunk-002/
#       │   ├── forward.json + forward.sha256
#       │   └── reverse.json + reverse.sha256
#       └── ...
#
# 복구 정책:
#   - 7단계 중단 시: ./scripts/audit-chain.sh --run-id <run_id>로 재실행
#   - 빌드부터 재수행되어 이미 적용된 항목은 자동 제외
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TIMESTAMP=$(date -u +"%Y%m%d-%H%M%SZ")
OUTPUT_DIR="apps/pipeline/output/audit/full-run-$TIMESTAMP"
REUSE_RUN_ID=""

print_usage() {
  cat <<'EOF'
metadata 감사 체인 무인 실행 (dev 전체 Tier B)

Usage:
  ./scripts/audit-chain.sh                    # 전체 체인 실행 (기본, ~1.5~3시간)
  ./scripts/audit-chain.sh /path/to/output    # 산출물 디렉터리 지정
  ./scripts/audit-chain.sh --run-id <uuid>    # 기존 run 재사용 (auto-approve부터 시작, ~5분)
  ./scripts/audit-chain.sh --help             # 이 도움말
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id)
      if [[ -z "${2:-}" ]]; then
        echo "ERROR: --run-id 뒤에 UUID 필요" >&2
        print_usage
        exit 1
      fi
      REUSE_RUN_ID="$2"
      shift 2
      ;;
    --help|-h)
      print_usage
      exit 0
      ;;
    -*)
      echo "ERROR: 알 수 없는 옵션: $1" >&2
      print_usage
      exit 1
      ;;
    *)
      OUTPUT_DIR="$1"
      shift
      ;;
  esac
done

log_step() {
  echo "==> [$1] $2"
}

log_success() {
  local msg="$1"
  local elapsed="${2:-}"
  if [[ -n "$elapsed" ]]; then
    echo "    ✓ $msg (소요시간: ${elapsed}초)"
  else
    echo "    ✓ $msg"
  fi
}

fail_step() {
  local step="$1"
  local msg="$2"
  local code="$3"
  echo "ERROR [$step]: $msg (exit code: $code) — 상세: $LOG_FILE" >&2
  exit "$code"
}

# docker 단계가 /repo 마운트 기준 상대경로를 쓰므로 저장소 내부 상대경로만 허용
case "$OUTPUT_DIR" in
  /*)
    echo "ERROR: 산출물 디렉터리는 저장소 루트 기준 상대경로여야 합니다: $OUTPUT_DIR" >&2
    exit 1
    ;;
esac

mkdir -p "$OUTPUT_DIR"
LOG_FILE="$ROOT/$OUTPUT_DIR/chain.log"
echo "산출물 디렉터리: $OUTPUT_DIR"
echo "상세 로그: $LOG_FILE"
echo ""

if [[ -n "$REUSE_RUN_ID" ]]; then
  log_step "RESUME" "기존 run 재사용: $REUSE_RUN_ID (auto-approve부터 시작)"
  RUN_ID="$REUSE_RUN_ID"
  skip_audit=1
else
  skip_audit=0
  RUN_ID=""
fi

baseline_file="$OUTPUT_DIR/baseline.json"
bootstrap_file="$OUTPUT_DIR/bootstrap-manifest.json"
report_file="$OUTPUT_DIR/audit-report.json"
manifest_dir="$OUTPUT_DIR/manifest"

# --- 1단계: Baseline export (dev service 기준선) ---
if [[ $skip_audit -eq 0 ]]; then
  log_step "1/7" "Baseline 내보내기 (dev-service)"
  start_time=$(date +%s)

  step_exit=0
  (cd apps/pipeline && uv run python -m fontagit_pipeline font-audit-export-baseline \
    --source dev-service \
    --out "$ROOT/$baseline_file") >>"$LOG_FILE" 2>&1 || step_exit=$?
  [[ $step_exit -eq 0 ]] || fail_step "1/7" "baseline export 실패" "$step_exit"

  baseline_sha256=$(tr -d '[:space:]' <"$baseline_file.sha256")
  log_success "baseline 내보내기 완료 (SHA256: ${baseline_sha256:0:8}...)" "$(($(date +%s) - start_time))"
fi

# --- 2단계: Bootstrap manifest 생성 ---
if [[ $skip_audit -eq 0 ]]; then
  log_step "2/7" "Bootstrap manifest 생성"
  start_time=$(date +%s)

  step_exit=0
  (cd apps/pipeline && uv run python -m fontagit_pipeline font-audit-bootstrap \
    --prod-snapshot "$ROOT/$baseline_file" \
    --out "$ROOT/$bootstrap_file") >>"$LOG_FILE" 2>&1 || step_exit=$?
  [[ $step_exit -eq 0 ]] || fail_step "2/7" "bootstrap manifest 생성 실패" "$step_exit"

  bootstrap_sha256=$(tr -d '[:space:]' <"$bootstrap_file.sha256")
  # load_bootstrap_targets 계약: 최상위 entries[], 대상 필드는 current
  tier_b_count=$(jq '[.entries[] | select(.current.source_tier == "B")] | length' "$bootstrap_file")
  if [[ -z "$tier_b_count" ]] || [[ "$tier_b_count" -le 0 ]]; then
    fail_step "2/7" "Tier B 대상 수 산출 실패 (tier_b_count=$tier_b_count)" 1
  fi
  log_success "Bootstrap manifest 생성 완료 (Tier B: ${tier_b_count}종, SHA256: ${bootstrap_sha256:0:8}...)" "$(($(date +%s) - start_time))"
fi

# --- 3단계: Bootstrap manifest 적용 (dev) ---
if [[ $skip_audit -eq 0 ]]; then
  log_step "3/7" "Bootstrap manifest 적용 (dev)"
  start_time=$(date +%s)

  step3_log="$OUTPUT_DIR/step3-bootstrap-apply.log"
  step_exit=0
  (cd apps/pipeline && uv run python -m fontagit_pipeline font-audit-bootstrap-apply \
    --manifest "$ROOT/$bootstrap_file" \
    --target dev \
    --confirm-hash "$bootstrap_sha256") >"$step3_log" 2>&1 || step_exit=$?
  cat "$step3_log" >>"$LOG_FILE"

  if [[ $step_exit -ne 0 ]]; then
    # apply_font_source_bootstrap은 1회성 시딩 RPC: 기존 provider key가 있으면 전체 거부한다
    if grep -q "provider key collision" "$step3_log"; then
      log_success "Bootstrap 이미 시드됨 — 적용 건너뜀 (provider key collision)"
    else
      fail_step "3/7" "bootstrap manifest 적용 실패" "$step_exit"
    fi
  else
    log_success "Bootstrap manifest 적용 완료" "$(($(date +%s) - start_time))"
  fi
fi

# --- 4단계: Audit run (metadata stage, Linux 게이트 때문에 docker 사용) ---
if [[ $skip_audit -eq 0 ]]; then
  log_step "4/7" "감사 실행 (metadata, ${tier_b_count}종 — 장시간 소요, 진행 로그: $LOG_FILE)"
  start_time=$(date +%s)

  step_exit=0
  docker run --rm \
    -v "$ROOT:/repo" \
    -w /repo/apps/pipeline \
    fontagit-pipeline:local \
    python -m fontagit_pipeline font-audit-run \
    --stage metadata \
    --bootstrap "/repo/$bootstrap_file" \
    --limit "$tier_b_count" \
    --out "/repo/$report_file" >>"$LOG_FILE" 2>&1 || step_exit=$?
  [[ $step_exit -eq 0 ]] || fail_step "4/7" "감사 실행 실패" "$step_exit"

  # write_audit_artifacts 계약: <out>.json / <out>.json.sha256 (out이 .json이면 그대로)
  report_sha256=$(tr -d '[:space:]' <"$report_file.sha256")
  RUN_ID=$(jq -r '.run_id' "$report_file")
  if [[ -z "$RUN_ID" ]] || [[ "$RUN_ID" == "null" ]]; then
    fail_step "4/7" "audit-report.json에서 run_id 추출 실패" 1
  fi
  log_success "감사 실행 완료 (run_id: ${RUN_ID:0:8}..., SHA256: ${report_sha256:0:8}...)" "$(($(date +%s) - start_time))"
fi

# --- 5단계: Auto-approve ---
log_step "5/7" "Findings 자동 승인 (run_id: ${RUN_ID:0:8}...)"
start_time=$(date +%s)

step_exit=0
(cd apps/pipeline && uv run python -m fontagit_pipeline font-audit-review auto-approve \
  --run-id "$RUN_ID") >>"$LOG_FILE" 2>&1 || step_exit=$?
[[ $step_exit -eq 0 ]] || fail_step "5/7" "auto-approve 실패" "$step_exit"

log_success "Findings 자동 승인 완료" "$(($(date +%s) - start_time))"

# --- 6단계: Manifest build (청크 분할) ---
log_step "6/7" "Manifest 빌드 (run_id: ${RUN_ID:0:8}..., chunk_size=100)"
start_time=$(date +%s)

mkdir -p "$manifest_dir"
step_exit=0
(cd apps/pipeline && uv run python -m fontagit_pipeline font-audit-manifest build \
  --run-id "$RUN_ID" \
  --chunk-size 100 \
  --out "$ROOT/$manifest_dir") >>"$LOG_FILE" 2>&1 || step_exit=$?
[[ $step_exit -eq 0 ]] || fail_step "6/7" "manifest build 실패" "$step_exit"

# index.json 확인
if [[ ! -f "$manifest_dir/index.json" ]]; then
  fail_step "6/7" "index.json 생성 실패" 1
fi

total_chunks=$(jq -r '.total_chunks' "$manifest_dir/index.json")
total_entries=$(jq -r '.total_entries' "$manifest_dir/index.json")
log_success "Manifest 빌드 완료 (청크: ${total_chunks}, 엔트리: ${total_entries})" "$(($(date +%s) - start_time))"

# --- 7단계: Manifest apply (청크 순차 적용) ---
log_step "7/7" "Manifest 적용 (dev, 청크 순차 적용)"
start_time=$(date +%s)

# 청크 디렉터리 순회 (chunk-001, chunk-002, ...)
chunk_count=0
chunk_success=0
for chunk_dir in "$manifest_dir"/chunk-[0-9][0-9][0-9]; do
  if [[ ! -d "$chunk_dir" ]]; then
    continue
  fi

  chunk_num=$(basename "$chunk_dir")
  forward_manifest="$chunk_dir/forward.json"
  forward_sha="$chunk_dir/forward.sha256"

  if [[ ! -f "$forward_manifest" ]] || [[ ! -f "$forward_sha" ]]; then
    echo "ERROR [7/7]: 청크 파일 누락 ($chunk_num)" >&2
    fail_step "7/7" "청크 파일 누락: $chunk_num" 1
  fi

  chunk_count=$((chunk_count + 1))
  forward_sha256=$(tr -d '[:space:]' <"$forward_sha")

  step_exit=0
  (cd apps/pipeline && uv run python -m fontagit_pipeline font-audit-manifest apply \
    --manifest "$ROOT/$forward_manifest" \
    --sha256 "$ROOT/$forward_sha" \
    --target dev \
    --confirm-hash "$forward_sha256") >>"$LOG_FILE" 2>&1 || step_exit=$?

  if [[ $step_exit -eq 0 ]]; then
    chunk_success=$((chunk_success + 1))
    echo "    ✓ $chunk_num 적용 완료 (SHA256: ${forward_sha256:0:8}...)"
  else
    echo "ERROR [7/7]: $chunk_num 적용 실패 (exit code: $step_exit)" >&2
    echo ""
    echo "[audit-chain] 부분 적용 상태: 청크 ${chunk_count}/${total_chunks} 실패. 이전 청크는 적용 유지됨." >&2
    echo "[audit-chain] 원인 수정 후 동일 명령 재실행 시 이미 적용된 청크는 멱등 처리된다." >&2
    echo ""
    echo "복구 방법:"
    echo "  ./scripts/audit-chain.sh --run-id ${RUN_ID}"
    exit "$step_exit"
  fi
done

if [[ $chunk_count -eq 0 ]]; then
  fail_step "7/7" "청크 디렉터리를 찾을 수 없습니다" 1
fi

log_success "Manifest 적용 완료 (${chunk_success}/${chunk_count} 청크 적용됨)" "$(($(date +%s) - start_time))"

echo ""
echo "✓ 감사 체인 완료"
echo "  산출물: $OUTPUT_DIR"
echo "  run_id: $RUN_ID"
echo "  manifest: $manifest_dir"
