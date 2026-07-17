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

# 1) prod Supabase 값 주입 (dev 덮어쓰기 방지)
[ -f "$ENV_PROD" ] || { echo "ERROR: $ENV_PROD 없음"; exit 1; }
set -a; source "$ENV_PROD"; set +a
echo "==> [1/4] prod(.env.production) 값으로 빌드"

# 2) 정적 빌드
pnpm --filter web build
[ -d "$OUT_DIR" ] || { echo "ERROR: $OUT_DIR 생성 안 됨(빌드 실패)"; exit 1; }

# 3) Pages 배포 토큰 로드 (.env.local의 CF_TOKEN)
CF_TOKEN="$(grep -E '^CF_TOKEN=' "$ENV_LOCAL" 2>/dev/null | head -1 | cut -d= -f2- || true)"
CF_TOKEN="${CF_TOKEN%$'\r'}"
CF_TOKEN="${CF_TOKEN%\"}"; CF_TOKEN="${CF_TOKEN#\"}"
CF_TOKEN="${CF_TOKEN%\'}"; CF_TOKEN="${CF_TOKEN#\'}"
[ -n "$CF_TOKEN" ] || { echo "ERROR: $ENV_LOCAL 에 CF_TOKEN 없음(Cloudflare Pages 토큰)"; exit 1; }

# 4) production(main 브랜치) 배포
echo "==> [2/4] Cloudflare Pages 배포 (project=$PROJECT, branch=main)"
CLOUDFLARE_API_TOKEN="$CF_TOKEN" CLOUDFLARE_ACCOUNT_ID="$ACCOUNT_ID" \
  npx --yes "$WRANGLER" pages deploy "$OUT_DIR" \
    --project-name "$PROJECT" --branch main --commit-dirty=true

# 5) 스모크 체크 (공용 리졸버로 라이브 확인, 실패해도 배포는 완료로 간주)
echo "==> [3/4] 스모크 체크"
IP="$(dig +short fontagit.com @1.1.1.1 2>/dev/null | head -1 || true)"
if [ -n "$IP" ]; then
  CODE="$(curl -s -o /dev/null -w '%{http_code}' -L --max-time 15 --resolve fontagit.com:443:"$IP" https://fontagit.com/ 2>/dev/null || true)"
  echo "    https://fontagit.com -> ${CODE:-무응답}"
fi

echo "==> [4/4] 완료: https://fontagit.com/"
