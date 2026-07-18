import Link from "next/link";
import type { Font } from "@/types/font";
import { getSpecimenText } from "@/lib/specimen";
import { LazyFontPreview } from "./LazyFontPreview";
import { TierChip } from "./TierChip";
import styles from "./FontCard.module.css";

/** 폰트 목록 카드(디자인 1f). 견본 + 폰트명 + 티어 배지 */
export function FontCard({ font }: { font: Font }) {
  const words = getSpecimenText(font, false).split(" ");
  const line1 = words.slice(0, 2).join(" ");
  const line2 = words.slice(2, 4).join(" ");

  return (
    <Link href={`/fonts/${font.slug}`} className={styles.card}>
      <LazyFontPreview font={font} className={styles.specimen}>
        {line1}<br />
        {line2}
      </LazyFontPreview>
      <div className={styles.foot}>
        <h3 className={styles.name}>{font.nameKo}</h3>
        <TierChip tier={font.tier} />
      </div>
    </Link>
  );
}
