"use client";

import { useState } from "react";
import { fonts } from "@/data/fonts";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./CompareBoard.module.css";

const SAMPLE =
  "좋은 폰트는 말을 걸지 않고 뜻을 전한다. ABCabc 0123";
const OPTIONS = fonts.filter((f) => f.tier === "free");
const DEFAULT_SLOTS = ["pretendard", "gowun-batang", "black-han-sans"];

export function CompareBoard() {
  const [text, setText] = useState("아지트");
  const [slots, setSlots] = useState<string[]>(DEFAULT_SLOTS);

  const handleTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setText(e.currentTarget.value);
  };

  const handleFontChange = (index: number, newSlug: string) => {
    setSlots((prev) => {
      const updated = [...prev];
      updated[index] = newSlug;
      return updated;
    });
  };

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h1 className={styles.title}>폰트 비교</h1>
        <p className={styles.subtitle}>문장을 입력해 3개 폰트를 비교해보세요.</p>
      </div>

      <div className={styles.inputRow}>
        <label className={styles.inputLabel}>문장</label>
        <input
          type="text"
          placeholder="아지트"
          aria-label="비교 문장 입력"
          value={text}
          onChange={handleTextChange}
          className={styles.input}
        />
      </div>

      <div className={styles.board}>
        {slots.map((slug, index) => {
          const f = fonts.find((x) => x.slug === slug)!;
          const family = fontKeyToVar[f.fontKey];

          return (
            <div key={index} className={styles.col}>
              <div className={styles.colHead}>
                <div>
                  <div className={styles.nameEn}>{f.nameEn}</div>
                  <div className={styles.nameKo}>{f.nameKo}</div>
                </div>
                <TierChip tier={f.tier} />
              </div>

              <select
                aria-label={`${index + 1}번 폰트 선택`}
                value={slug}
                onChange={(e) => handleFontChange(index, e.currentTarget.value)}
                className={styles.select}
              >
                {OPTIONS.map((opt) => (
                  <option key={opt.slug} value={opt.slug}>
                    {opt.nameKo}
                  </option>
                ))}
              </select>

              <div
                className={styles.specimen}
                style={{ fontFamily: family }}
              >
                {text || SAMPLE}
              </div>

              <div className={styles.sample} style={{ fontFamily: family }}>
                {SAMPLE}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
