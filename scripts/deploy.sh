#!/usr/bin/env bash
# fontagit 프로덕션 배포
# Usage:
#   ./scripts/deploy.sh                    # main 브랜치에서 배포 (기본)
#   ./scripts/deploy.sh --branch develop   # 지정한 브랜치에서 배포
#   ./scripts/deploy.sh --new-tag v1.0.0   # 새 태그 생성 후 배포 (main에서만)
#   ./scripts/deploy.sh --tag v1.0.0       # 기존 태그에서 배포
#
# prod(.env.production) 데이터로 정적 빌드 → Cloudflare Pages로 배포.
# .env.local(dev Supabase)이 .env.production을 덮어쓰는 함정을 막기 위해,
# prod 값을 process env로 먼저 주입해 우선순위를 뒤집는다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT="fontagit"
ACCOUNT_ID="2686c11634da0d924f089b7e56a9e227"
ENV_PROD="apps/web/.env.production"
ENV_LOCAL="apps/web/.env.local"
OUT_DIR="apps/web/out"
WRANGLER="wrangler@4"

# 인자 파싱
TARGET_BRANCH="main"
NEW_TAG=""
DEPLOY_TAG=""

print_usage() {
  cat <<'EOF'
fontagit 프로덕션 배포

Usage:
  ./scripts/deploy.sh                    # main 브랜치에서 배포 (기본)
  ./scripts/deploy.sh <ref>              # ref가 브랜치면 브랜치 배포, 태그면 태그 배포(자동 판별)
  ./scripts/deploy.sh --branch <name>    # 지정 브랜치에서 배포
  ./scripts/deploy.sh --new-tag <ver>    # 새 태그 생성 후 배포 (main에서만)
  ./scripts/deploy.sh --tag <ver>        # 기존 태그에서 배포
  ./scripts/deploy.sh --help             # 이 도움말

옵션:
  <ref>                 옵션 없이 브랜치명 또는 태그명 전달 시 존재 여부로 자동 판별
  --branch <name>       지정한 브랜치에서 배포 (미리 체크아웃되어 있어야 함)
  --new-tag <ver>        semver 태그 생성 후 배포 (v1.0.0 형식, main에서만)
  --tag <ver>            기존 태그에서 배포
  --help                 이 도움말 출력

예시:
  ./scripts/deploy.sh staging            # staging이 브랜치면 브랜치 배포
  ./scripts/deploy.sh v1.0.0             # v1.0.0이 태그면 태그 배포
  ./scripts/deploy.sh --branch staging   # staging 브랜치에서 배포
  ./scripts/deploy.sh --new-tag v1.2.0   # 새 태그 v1.2.0 생성 후 배포
  ./scripts/deploy.sh --tag v1.0.0       # 기존 v1.0.0 태그에서 배포
EOF
}

BRANCH_FLAG_SET=""
BARE_REF=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      if [[ -z "${2:-}" ]]; then
        echo "ERROR: --branch 뒤에 브랜치 이름 필요"
        print_usage
        exit 1
      fi
      TARGET_BRANCH="$2"
      BRANCH_FLAG_SET="1"
      shift 2
      ;;
    --new-tag)
      if [[ -z "${2:-}" ]]; then
        echo "ERROR: --new-tag 뒤에 버전 필요"
        print_usage
        exit 1
      fi
      NEW_TAG="$2"
      shift 2
      ;;
    --tag)
      if [[ -z "${2:-}" ]]; then
        echo "ERROR: --tag 뒤에 버전 필요"
        print_usage
        exit 1
      fi
      DEPLOY_TAG="$2"
      shift 2
      ;;
    --help|-h)
      print_usage
      exit 0
      ;;
    -*)
      echo "ERROR: 알 수 없는 옵션: $1"
      print_usage
      exit 1
      ;;
    *)
      if [[ -n "$BARE_REF" ]]; then
        echo "ERROR: 위치 인자는 하나만 허용: $1"
        print_usage
        exit 1
      fi
      BARE_REF="$1"
      shift
      ;;
  esac
done

# 옵션 상호 배타성 검증
OPTION_COUNT=0
[[ -n "$NEW_TAG" ]] && ((OPTION_COUNT++))
[[ -n "$DEPLOY_TAG" ]] && ((OPTION_COUNT++))
[[ -n "$BRANCH_FLAG_SET" ]] && ((OPTION_COUNT++))

if [[ $OPTION_COUNT -gt 1 ]]; then
  echo "ERROR: --branch, --new-tag, --tag는 동시 지정 불가"
  print_usage
  exit 1
fi

if [[ -n "$BARE_REF" && $OPTION_COUNT -gt 0 ]]; then
  echo "ERROR: '$BARE_REF' 위치 인자는 --branch/--new-tag/--tag와 동시 사용 불가"
  print_usage
  exit 1
fi

# 위치 인자 자동 판별: 존재하는 브랜치면 브랜치 배포, 존재하는 태그면 태그 배포
if [[ -n "$BARE_REF" ]]; then
  IS_BRANCH=""
  IS_TAG=""
  git show-ref --verify --quiet "refs/heads/$BARE_REF" && IS_BRANCH="1"
  git ls-remote --tags origin "refs/tags/$BARE_REF" 2>/dev/null | grep -q . && IS_TAG="1"

  if [[ -n "$IS_BRANCH" && -n "$IS_TAG" ]]; then
    echo "ERROR: '$BARE_REF'는 브랜치와 태그 양쪽에 존재함 — --branch 또는 --tag로 명시하라"
    exit 1
  elif [[ -n "$IS_BRANCH" ]]; then
    TARGET_BRANCH="$BARE_REF"
    BRANCH_FLAG_SET="1"
  elif [[ -n "$IS_TAG" ]]; then
    DEPLOY_TAG="$BARE_REF"
  else
    echo "ERROR: '$BARE_REF'는 존재하는 브랜치도 태그도 아님. 새 태그를 만들려면 --new-tag $BARE_REF 사용"
    exit 1
  fi
fi

# 1) 배포 출처 고정: 최신 origin/main과 같은 깨끗한 main만 허용
echo "==> [1/5] 배포 출처 확인"
git fetch origin --quiet

# 작업 트리 깨끗함 검증 (모든 배포 방식)
[ -z "$(git status --porcelain --untracked-files=no)" ] || {
  echo "ERROR: 추적 파일 변경이 남아 있음"
  exit 1
}

# 새 태그 생성인 경우: main에서만 허용
if [[ -n "$NEW_TAG" ]]; then
  [ "$(git branch --show-current)" = "main" ] || {
    echo "ERROR: 새 태그는 main 브랜치에서만 생성 가능 (현재: $(git branch --show-current))"
    exit 1
  }
  [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || {
    echo "ERROR: HEAD가 origin/main과 다름 (새 태그 생성 전 push 필요)"
    exit 1
  }

  # 버전 형식 검증 (semver, v 접두사)
  if ! [[ "$NEW_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: 버전은 v[0-9]+.[0-9]+.[0-9]+ 형식 필요 (예: v1.0.0)"
    exit 1
  fi

  # 태그 중복 검사
  if git rev-parse "$NEW_TAG" >/dev/null 2>&1; then
    echo "ERROR: 태그 $NEW_TAG가 이미 존재함 (덮어쓰기 금지)"
    exit 1
  fi

  echo "==> 새 태그 생성: $NEW_TAG"
  git tag "$NEW_TAG"
  git push origin "$NEW_TAG"
fi

# 기존 태그에서 배포인 경우: 태그 검증
if [[ -n "$DEPLOY_TAG" ]]; then
  git ls-remote --tags origin "refs/tags/$DEPLOY_TAG" | grep -q . || {
    echo "ERROR: 태그 $DEPLOY_TAG가 origin에 없음"
    exit 1
  }
  git fetch origin --quiet "refs/tags/$DEPLOY_TAG:refs/tags/$DEPLOY_TAG" 2>/dev/null || true

  # 태그 배포: 임시 체크아웃 후 빌드, 완료 후 원래 상태 복원
  ORIGINAL_BRANCH="$(git branch --show-current)"
  echo "==> 태그 $DEPLOY_TAG로 임시 전환"
  git checkout "$DEPLOY_TAG" --quiet
  trap "echo '==> 원래 상태 복원: $ORIGINAL_BRANCH'; git checkout '$ORIGINAL_BRANCH' --quiet" EXIT
else
  # 브랜치 배포 (--branch 또는 기본값 main)
  [ "$(git branch --show-current)" = "$TARGET_BRANCH" ] || {
    echo "ERROR: $TARGET_BRANCH 브랜치에서만 배포할 수 있음 (현재: $(git branch --show-current))"
    exit 1
  }
  [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/$TARGET_BRANCH)" ] || {
    echo "ERROR: HEAD가 origin/$TARGET_BRANCH와 다름"
    exit 1
  }
fi

# 2) prod Supabase 값 주입 및 dev 연결 차단
[ -f "$ENV_PROD" ] || { echo "ERROR: $ENV_PROD 없음"; exit 1; }
set -a; source "$ENV_PROD"; set +a
PROD_SUPABASE_URL="${NEXT_PUBLIC_SUPABASE_URL:-}"
DEV_SUPABASE_URL="$(grep -E '^NEXT_PUBLIC_SUPABASE_URL=' "$ENV_LOCAL" 2>/dev/null | head -1 | cut -d= -f2- || true)"
DEV_SUPABASE_URL="${DEV_SUPABASE_URL%$'\r'}"
DEV_SUPABASE_URL="${DEV_SUPABASE_URL%\"}"; DEV_SUPABASE_URL="${DEV_SUPABASE_URL#\"}"
DEV_SUPABASE_URL="${DEV_SUPABASE_URL%\'}"; DEV_SUPABASE_URL="${DEV_SUPABASE_URL#\'}"
[ -n "$PROD_SUPABASE_URL" ] || { echo "ERROR: $ENV_PROD 에 NEXT_PUBLIC_SUPABASE_URL 없음"; exit 1; }
[ -n "$DEV_SUPABASE_URL" ] || { echo "ERROR: $ENV_LOCAL 에 개발 NEXT_PUBLIC_SUPABASE_URL 없음"; exit 1; }
[ "$PROD_SUPABASE_URL" != "$DEV_SUPABASE_URL" ] || {
  echo "ERROR: 운영 Supabase URL이 개발 URL과 같음"
  exit 1
}
echo "==> [2/5] prod(.env.production) 값으로 빌드"

# 3) 정적 빌드
pnpm --filter web build
[ -d "$OUT_DIR" ] || { echo "ERROR: $OUT_DIR 생성 안 됨(빌드 실패)"; exit 1; }
command -v xmllint >/dev/null 2>&1 || { echo "ERROR: sitemap XML 검증용 xmllint 없음"; exit 1; }
xmllint --noout "$OUT_DIR/sitemap.xml"
pnpm --filter web verify:seo

# 4) Pages 배포 토큰 로드 (.env.local의 CF_TOKEN)
CF_TOKEN="$(grep -E '^CF_TOKEN=' "$ENV_LOCAL" 2>/dev/null | head -1 | cut -d= -f2- || true)"
CF_TOKEN="${CF_TOKEN%$'\r'}"
CF_TOKEN="${CF_TOKEN%\"}"; CF_TOKEN="${CF_TOKEN#\"}"
CF_TOKEN="${CF_TOKEN%\'}"; CF_TOKEN="${CF_TOKEN#\'}"
[ -n "$CF_TOKEN" ] || { echo "ERROR: $ENV_LOCAL 에 CF_TOKEN 없음(Cloudflare Pages 토큰)"; exit 1; }

# 5) production(main 브랜치) 배포
echo "==> [3/5] Cloudflare Pages 배포 (project=$PROJECT, branch=main)"
CLOUDFLARE_API_TOKEN="$CF_TOKEN" CLOUDFLARE_ACCOUNT_ID="$ACCOUNT_ID" \
  npx --yes "$WRANGLER" pages deploy "$OUT_DIR" \
    --project-name "$PROJECT" --branch main

# 6) 스모크 체크
echo "==> [4/5] 스모크 체크"
IP="$(dig +short fontagit.com @1.1.1.1 2>/dev/null | head -1 || true)"
[ -n "$IP" ] || { echo "ERROR: fontagit.com 운영 IP 확인 실패"; exit 1; }
CODE="$(curl -s -o /dev/null -w '%{http_code}' -L --max-time 15 --resolve fontagit.com:443:"$IP" https://fontagit.com/ 2>/dev/null || true)"
[ "$CODE" = "200" ] || { echo "ERROR: 운영 스모크 체크 실패 (HTTP ${CODE:-무응답})"; exit 1; }
echo "    https://fontagit.com -> 200"

echo "==> [5/5] 완료: https://fontagit.com/"
