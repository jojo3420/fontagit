"use client";

import { PAIRINGS, type ComparePreset } from "@/data/pairings";
import { fonts } from "@/data/fonts";
import { familyOf } from "@/lib/fonts";
import styles from "./PairingPresets.module.css";

export function PairingPresets({ onSelect }: { onSelect: (preset: ComparePreset) => void }) {
  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h2 id="pairing-heading" className={styles.title}>페어링 추천</h2>
        <span className={styles.hint}>제목과 본문, 어울리는 조합을 바로 비교해 보세요</span>
      </div>
      <div className={styles.cards}>
        {PAIRINGS.map((p) => {
          const hero = fonts.find((f) => f.slug === p.heroSlug);
          const body = fonts.find((f) => f.slug === p.bodySlug);
          if (!hero || !body) return null;
          return (
            <button
              type="button"
              key={p.id}
              className={styles.card}
              onClick={() => onSelect({ heroSlug: p.heroSlug, gridSlugs: [p.bodySlug] })}
            >
              <span className={styles.sample} style={{ fontFamily: familyOf(hero.fontKey) }}>
                {p.title}
              </span>
              <span className={styles.desc}>
                {hero.nameKo} + {body.nameKo} — {p.description}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
