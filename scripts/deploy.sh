#!/usr/bin/env bash
# fontagit 프로덕션 배포
# prod(.env.production) 데이터로 정적 빌드 → Cloudflare Pages(main 브랜치)로 배포.
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

# 1) 배포 출처 고정: 최신 origin/main과 같은 깨끗한 main만 허용
echo "==> [1/5] 배포 출처 확인"
git fetch origin --quiet
[ "$(git branch --show-current)" = "main" ] || {
  echo "ERROR: main 브랜치에서만 배포할 수 있음"
  exit 1
}
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || {
  echo "ERROR: HEAD가 origin/main과 다름"
  exit 1
}
[ -z "$(git status --porcelain --untracked-files=no)" ] || {
  echo "ERROR: 추적 파일 변경이 남아 있음"
  exit 1
}

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
