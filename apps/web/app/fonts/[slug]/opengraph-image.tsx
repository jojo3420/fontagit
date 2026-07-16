import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { getAllSlugs, getFontBySlug } from "@/lib/data";

export const dynamic = "force-static";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const FONT_PATH = "node_modules/pretendard/dist/public/static/Pretendard-Bold.otf";

export async function generateStaticParams() {
  const slugs = await getAllSlugs();
  return slugs.map((slug) => ({ slug }));
}

export default async function FontOgImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const font = await getFontBySlug(slug);
  const nameKo = font?.nameKo ?? "FontAgit";
  const tierLabel = font?.tier === "paid" ? "유료" : "무료";
  const licenseText = `${tierLabel} - 공식 페이지에서 라이선스 확인`;
  const pretendardBold = await readFile(join(process.cwd(), FONT_PATH));

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "flex-start", justifyContent: "center", padding: 80, gap: 24, background: "#FAFAF8", fontFamily: "Pretendard" }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: "#2C5545" }}>
          FontAgit 폰트 상세
        </div>
        <div style={{ fontSize: 92, fontWeight: 800, color: "#1A1A1A", letterSpacing: "-0.03em" }}>
          {nameKo}
        </div>
        <div style={{ fontSize: 30, color: "#6B6B6B" }}>
          {licenseText}
        </div>
      </div>
    ),
    { ...size, fonts: [{ name: "Pretendard", data: pretendardBold, weight: 700, style: "normal" }] },
  );
}
