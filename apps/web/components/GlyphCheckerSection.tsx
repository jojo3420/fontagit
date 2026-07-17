"use client";

import { useState } from "react";
import type { Font, FontKey } from "@/types/font";
import { GlyphChecker } from "./GlyphChecker";
import styles from "./GlyphCheckerSection.module.css";

interface GlyphCheckerSectionProps {
  /** 검사 대상 폰트 목록 (일반적으로 free tier 폰트들) */
  fonts: Font[];
}

/**
 * 글자 지원 검사 섹션
 *
 * 사용자가 폰트를 선택하고 글자를 입력해서
 * 해당 폰트에서 글자가 지원되는지 검사할 수 있는 섹션입니다.
 */
export function GlyphCheckerSection({ fonts }: GlyphCheckerSectionProps) {
  const [selectedFontSlug, setSelectedFontSlug] = useState(
    fonts[0]?.slug || ""
  );

  const selectedFont = fonts.find((f) => f.slug === selectedFontSlug);

  if (!selectedFont) {
    return null;
  }

  return (
    <section className={styles.section}>
      <div className={styles.header}>
        <h2 className={styles.title}>글자 지원 검사</h2>
        <p className={styles.description}>
          특정 폰트에서 글자가 지원되는지 검사합니다.
        </p>
      </div>

      <div className={styles.fontSelector}>
        <label htmlFor="font-select" className={styles.label}>
          폰트 선택
        </label>
        <select
          id="font-select"
          className={styles.select}
          value={selectedFontSlug}
          onChange={(e) => setSelectedFontSlug(e.target.value)}
        >
          {fonts.map((font) => (
            <option key={font.slug} value={font.slug}>
              {font.nameKo}
              {font.fontKey === "pretendard"
                ? " (로컬 폰트)"
                : font.tier === "paid"
                  ? " (유료)"
                  : ""}
            </option>
          ))}
        </select>
      </div>

      <GlyphChecker
        fontKey={selectedFont.fontKey}
        fontName={selectedFont.nameKo}
        tier={selectedFont.tier}
      />
    </section>
  );
}
