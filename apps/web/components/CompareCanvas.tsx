"use client";
import { useState } from "react";
import Link from "next/link";
import { fonts } from "@/data/fonts";
import { familyOf } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./CompareCanvas.module.css";

const DEFAULT_TEXT = "다람쥐 헌 쳇바퀴에 타고파 1234 !@#$";
const PRESETS = [DEFAULT_TEXT, "당신의 폰트 아지트", "가나다라 ABC 0123", "The quick brown fox"];
const OPTIONS = fonts.filter((f) => f.tier === "free");
const DEFAULT_HERO = "pretendard";
const DEFAULT_GRID = OPTIONS.filter((f) => f.slug !== DEFAULT_HERO).map((f) => f.slug);

export function CompareCanvas() {
  const [text, setText] = useState(DEFAULT_TEXT);
  const [heroSlug, setHeroSlug] = useState(DEFAULT_HERO);
  const [gridSlugs, setGridSlugs] = useState<string[]>(DEFAULT_GRID);
  const shown = text || " ";
  const hero = OPTIONS.find((f) => f.slug === heroSlug);

  const changeGrid = (index: number, slug: string) =>
    setGridSlugs((prev) => prev.map((v, i) => (i === index ? slug : v)));

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h2 id="compare-heading" className={styles.title}>폰트 비교</h2>
        <span className={styles.subtitle}>같은 문장을 모든 폰트에 나란히 놓고 결정하세요</span>
      </div>
      <div className={styles.inputRow}>
        <svg className={styles.icon} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 7h16M4 12h10M4 17h13" /></svg>
        <input className={styles.input} value={text} onChange={(e) => setText(e.target.value)} placeholder={DEFAULT_TEXT} aria-label="비교 문장 입력" />
        <button type="button" className={styles.clear} onClick={() => setText("")}>지우기</button>
      </div>
      <div className={styles.presets}>
        {PRESETS.map((p) => (
          <button type="button" key={p} className={styles.preset} onClick={() => setText(p)}>{p}</button>
        ))}
      </div>
      {hero && (
        <div className={styles.hero}>
          <div className={styles.heroLabel}>
            <select className={styles.select} value={heroSlug} onChange={(e) => setHeroSlug(e.target.value)} aria-label="대표 폰트 선택">
              {OPTIONS.map((o) => (
                <option key={o.slug} value={o.slug}>{o.nameKo}</option>
              ))}
            </select>
            <div className={styles.heroRight}>
              <TierChip tier={hero.tier} />
              <Link href={`/fonts/${hero.slug}`} className={styles.cellDetail}>상세</Link>
              <span className={styles.heroSize}>96px</span>
            </div>
          </div>
          <div className={styles.heroSpecimen} data-testid="hero-specimen" style={{ fontFamily: familyOf(hero.fontKey) }}>{shown}</div>
        </div>
      )}
      <div className={styles.gridHead}>무료 폰트 나란히 보기 <span className={styles.count}>- 대표 1 + {gridSlugs.length}종</span></div>
      <div className={styles.grid}>
        {gridSlugs.map((slug, i) => {
          const f = OPTIONS.find((x) => x.slug === slug);
          if (!f) return null;
          return (
            <div key={i} className={styles.cell}>
              <div className={styles.cellHead}>
                <select className={styles.select} value={slug} onChange={(e) => changeGrid(i, e.target.value)} aria-label={`${i + 1}번 폰트 선택`}>
                  {OPTIONS.map((o) => (
                    <option key={o.slug} value={o.slug}>{o.nameKo}</option>
                  ))}
                </select>
                <div className={styles.cellRight}>
                  <TierChip tier={f.tier} />
                  <Link href={`/fonts/${f.slug}`} className={styles.cellDetail}>상세</Link>
                </div>
              </div>
              <div className={styles.cellSpecimen} style={{ fontFamily: familyOf(f.fontKey) }}>{shown}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
