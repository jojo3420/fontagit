"use client";

import { useState } from "react";
import { fonts } from "@/data/fonts";
import { familyOf } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./CompareBoard.module.css";

const SAMPLE =
  "좋은 폰트는 말을 걸지 않고 뜻을 전한다. ABCabc 0123";
const OPTIONS = fonts.filter((f) => f.tier === "free");
const DEFAULT_SLOTS = ["pretendard", "gowun-batang", "black-han-sans"];

export function CompareBoard() {
  const [text, setText] = useState("아지트");
  const [slots, setSlots] = useState<string[]>(DEFAULT_SLOTS);
  const shown = text || " ";

  function change(index: number, slug: string) {
    setSlots((prev) => prev.map((v, i) => (i === index ? slug : v)));
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h1 className={styles.title}>폰트 비교</h1>
        <span className={styles.subtitle}>
          같은 문장으로 나란히 놓고 결정하세요
        </span>
      </div>
      <div className={styles.inputRow}>
        <span className={styles.inputLabel}>문장</span>
        <input
          className={styles.input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="아지트"
          aria-label="비교 문장 입력"
        />
      </div>
      <div className={styles.board}>
        {slots.map((slug, i) => {
          const f = fonts.find((x) => x.slug === slug)!;
          const family = familyOf(f.fontKey);
          return (
            <div key={i} className={styles.col}>
              <div className={styles.colHead}>
                <select
                  className={styles.select}
                  value={slug}
                  onChange={(e) => change(i, e.target.value)}
                  aria-label={`${i + 1}번 폰트 선택`}
                >
                  {OPTIONS.map((o) => (
                    <option key={o.slug} value={o.slug}>
                      {o.nameKo}
                    </option>
                  ))}
                </select>
                <TierChip tier={f.tier} />
              </div>
              <div
                className={styles.specimen}
                style={{ fontFamily: family }}
              >
                {shown}
              </div>
              <div
                className={styles.sample}
                style={{ fontFamily: family }}
              >
                {SAMPLE}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
