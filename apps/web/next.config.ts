import type { NextConfig } from "next";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  output: "export",
  turbopack: {
    root: webRoot,
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
