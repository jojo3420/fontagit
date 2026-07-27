"use client";

import { useState } from "react";
import { fonts } from "@/data/fonts";
import { familyOf } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./CompareCanvas.module.css";

const DEFAULT_TEXT = "다람쥐 헌 쳇바퀴에 타고파 1234 !@#$";
const DEFAULT_HERO = "pretendard";
const DEFAULT_GRID = [
  "pretendard",
  "black-han-sans",
  "jua",
  "do-hyeon",
  "gowun-batang",
  "nanum-myeongjo",
  "kirang-haerang",
  "gaegu",
];

const OPTIONS = fonts;

export function CompareCanvas() {
  const [text, setText] = useState(DEFAULT_TEXT);
  const [heroSlug, setHeroSlug] = useState(DEFAULT_HERO);
  const [gridSlugs, setGridSlugs] = useState<string[]>(DEFAULT_GRID);

  const hero = OPTIONS.find((f) => f.slug === heroSlug);
  const gridFonts = gridSlugs
    .map((slug) => OPTIONS.find((f) => f.slug === slug))
    .filter((f): f is typeof OPTIONS[0] => !!f);

  const changeGrid = (index: number, slug: string) => {
    setGridSlugs((prev) => prev.map((v, i) => (i === index ? slug : v)));
  };

  return (
    <div className={styles.container}>
      <h2 id="compare-heading" className={styles.title}>폰트 비교</h2>

      {/* 입력 섹션 */}
      <div className={styles.inputRow}>
        <input
          className={styles.input}
          aria-label="비교 문장 입력"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="비교할 문장을 입력하세요"
        />
        <button
          className={styles.clear}
          onClick={() => setText(DEFAULT_TEXT)}
          aria-label="기본 문장으로 초기화"
        >
          초기화
        </button>
      </div>

      {/* 대표 폰트 영역 */}
      <div className={styles.heroSection}>
        <div className={styles.heroLabel}>
          <h3>대표 폰트</h3>
        </div>
        <div className={styles.heroRight}>
          <select
            className={styles.select}
            aria-label="대표 폰트 선택"
            value={heroSlug}
            onChange={(e) => setHeroSlug(e.target.value)}
          >
            {OPTIONS.map((font) => (
              <option key={font.slug} value={font.slug}>
                {font.nameKo}
              </option>
            ))}
          </select>
          {hero && (
            <div className={styles.heroInfo}>
              <TierChip tier={hero.tier} />
              <a href={`/fonts/${heroSlug}`} aria-label="상세">
                상세
              </a>
            </div>
          )}
        </div>
      </div>

      {/* 대표 견본 */}
      <div
        className={styles.heroSize}
        style={{ fontFamily: familyOf(hero?.fontKey ?? null) }}
        data-testid="hero-specimen"
      >
        {text}
      </div>

      {/* 그리드 영역 */}
      <div className={styles.gridSection}>
        {gridFonts.map((font, index) => (
          <div key={index} className={styles.gridCell}>
            <select
              className={styles.select}
              aria-label={`${index + 1}번 선택`}
              value={font.slug}
              onChange={(e) => changeGrid(index, e.target.value)}
            >
              {OPTIONS.map((f) => (
                <option key={f.slug} value={f.slug}>
                  {f.nameKo}
                </option>
              ))}
            </select>
            <div
              className={styles.gridSpecimen}
              style={{ fontFamily: familyOf(font.fontKey) }}
            >
              {text}
            </div>
            <div className={styles.gridInfo}>
              <TierChip tier={font.tier} />
              <a href={`/fonts/${font.slug}`} aria-label="상세">
                상세
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
