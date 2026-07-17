"use client";
import { useState } from "react";
import Link from "next/link";
import { fonts } from "@/data/fonts";
import { familyOf } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./PlaygroundCanvas.module.css";

const PRESETS = ["다람쥐 헌 쳇바퀴에 타고파", "당신의 폰트 아지트", "가나다라 ABC 0123", "The quick brown fox"];
const HERO = fonts.find((f) => f.slug === "pretendard")!;
const GRID = fonts.filter((f) => f.tier === "free" && f.slug !== HERO.slug);

export function PlaygroundCanvas() {
  const [text, setText] = useState("아지트");
  const shown = text || " ";
  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h1 className={styles.title}>타입 캔버스</h1>
        <span className={styles.subtitle}>아무 글자나 입력하면 모든 폰트가 그 글자로 바뀝니다</span>
      </div>
      <div className={styles.inputRow}>
        <svg className={styles.icon} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 7h16M4 12h10M4 17h13" /></svg>
        <input className={styles.input} value={text} onChange={(e) => setText(e.target.value)} placeholder="아지트" aria-label="캔버스 입력" />
        <button type="button" className={styles.clear} onClick={() => setText("")}>지우기</button>
      </div>
      <div className={styles.presets}>
        {PRESETS.map((p) => (
          <button type="button" key={p} className={styles.preset} onClick={() => setText(p)}>{p}</button>
        ))}
      </div>
      <div className={styles.hero}>
        <div className={styles.heroLabel}>
          <span>대표 - {HERO.nameKo} - 96px</span>
        </div>
        <div className={styles.heroSpecimen} style={{ fontFamily: familyOf(HERO.fontKey) }}>{shown}</div>
      </div>
      <div className={styles.gridHead}>무료 폰트에서 보기 <span className={styles.count}>- 대표 1 + {GRID.length}종</span></div>
      <div className={styles.grid}>
        {GRID.map((f) => (
          <div key={f.slug} className={styles.cell}>
            <div className={styles.cellHead}>
              <span className={styles.cellName}>{f.nameKo}</span>
              <div className={styles.cellRight}>
                <TierChip tier={f.tier} />
                <Link href={`/fonts/${f.slug}`} className={styles.cellDetail}>상세</Link>
              </div>
            </div>
            <div className={styles.cellSpecimen} style={{ fontFamily: familyOf(f.fontKey) }}>{shown}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
