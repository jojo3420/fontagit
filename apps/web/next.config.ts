import type { NextConfig } from "next";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = dirname(fileURLToPath(import.meta.url));
// pnpm 워크스페이스는 의존성을 저장소 루트 store로 심링크하므로,
// turbopack 컴파일 경계는 앱 디렉터리가 아니라 모노레포 루트여야 한다.
const monorepoRoot = join(webRoot, "..", "..");

const nextConfig: NextConfig = {
  output: "export",
  turbopack: {
    root: monorepoRoot,
  },
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
  experimental: {
    // 일시적 게이트웨이 오류(502/503) 시 페이지 생성 재시도
    staticGenerationRetryCount: 3,
  },
};

export default nextConfig;
