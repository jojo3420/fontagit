import Link from "next/link";
import type { Font } from "@/types/font";
import { familyOf } from "@/lib/fonts";
import { getSpecimenText } from "@/lib/specimen";
import { TierChip } from "./TierChip";
import styles from "./FontCard.module.css";

/** 폰트 목록 카드(디자인 1f). 견본 + 폰트명 + 티어 배지 */
export function FontCard({ font }: { font: Font }) {
  return (
    <Link href={`/fonts/${font.slug}`} className={styles.card}>
      <div className={styles.specimen} style={{ fontFamily: familyOf(font.fontKey) }}>
        {getSpecimenText(font.subsets, false).split(" ").slice(0, 2).join(" ")}<br />
        {getSpecimenText(font.subsets, false).split(" ").slice(2, 4).join(" ")}
      </div>
      <div className={styles.foot}>
        <h3 className={styles.name}>{font.nameKo}</h3>
        <TierChip tier={font.tier} />
      </div>
    </Link>
  );
}
