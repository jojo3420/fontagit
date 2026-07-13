import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const dynamic = "force-static";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "FontAgit 폰트 아지트";

const FONT_PATH = "node_modules/pretendard/dist/public/static/Pretendard-Bold.otf";

export default async function OgImage() {
  const pretendardBold = await readFile(join(process.cwd(), FONT_PATH));
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 20, background: "#FAFAF8", fontFamily: "Pretendard" }}>
        <div style={{ fontSize: 84, fontWeight: 800, color: "#1A1A1A", letterSpacing: "-0.03em" }}>
          FontAgit
        </div>
        <div style={{ fontSize: 30, color: "#6B6B6B" }}>당신의 폰트 아지트</div>
      </div>
    ),
    { ...size, fonts: [{ name: "Pretendard", data: pretendardBold, weight: 700, style: "normal" }] },
  );
}
