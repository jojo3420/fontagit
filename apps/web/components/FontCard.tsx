import type { Font } from "@/types/font";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import { LicenseBadge } from "./LicenseBadge";
import styles from "./FontCard.module.css";

interface FontCardProps {
  font: Font;
}

export function FontCard({ font }: FontCardProps) {
  const weightCount = font.availableWeights.length;

  return (
    <article className={styles.card}>
      <div className={styles.specimen} style={{ fontFamily: fontKeyToVar[font.fontKey] }}>
        한글
      </div>
      <div className={styles.content}>
        <h3 className={styles.name}>{font.nameKo}</h3>
        <p className={styles.meta}>
          <span>{font.foundry}</span>
          <span>{weightCount}가지 굵기</span>
          <span>{font.moves.toLocaleString()}회 이동</span>
        </p>
        <div className={styles.foot}>
          <TierChip tier={font.tier} />
          <LicenseBadge commercial={font.license.commercial} />
        </div>
      </div>
    </article>
  );
}
