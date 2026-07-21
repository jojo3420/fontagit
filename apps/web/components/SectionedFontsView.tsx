"use client";

import { useState, useDeferredValue } from "react";
import { TypeCanvasBar } from "./TypeCanvasBar";
import { SectionOverview } from "./SectionOverview";
import styles from "./SectionedFontsView.module.css";
import type { Font } from "@/types/font";

interface SectionedFontsViewProps {
  /** 섹션별로 표시할 폰트 배열 */
  fonts: Font[];
}

/**
 * 타입 캔버스 상태를 소유하고 입력 문구를 deferred value로 감싼 섹션 폰트 뷰
 *
 * TypeCanvasBar에서 입력한 문구를 useDeferredValue로 감싸서
 * SectionOverview의 previewText로 전달하여 대량 카드 리렌더 성능 최적화.
 */
export function SectionedFontsView({ fonts }: SectionedFontsViewProps) {
  const [text, setText] = useState<string>("");
  const deferredText = useDeferredValue(text);

  return (
    <div className={styles.wrapper}>
      <TypeCanvasBar value={text} onChange={setText} />
      <SectionOverview fonts={fonts} previewText={deferredText} />
    </div>
  );
}
