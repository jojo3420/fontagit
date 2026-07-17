import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
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
