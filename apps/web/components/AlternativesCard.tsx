import type { Font } from "@/types/font";
import { TierChip } from "@/components/TierChip";
import styles from "./AlternativesCard.module.css";

interface AlternativesCardProps {
  category: string;
  items: Font[];
}

export function AlternativesCard({ category, items }: AlternativesCardProps) {
  if (items.length === 0) return null;

  return (
    <div className={styles.card}>
      <h3 className={styles.title}>비슷한 무료 대안 {items.length}개</h3>
      <p className={styles.subtitle}>분위기가 가까운 무료 {category}입니다</p>
      <div className={styles.items}>
        {items.map((item) => (
          <div key={item.slug} className={styles.item}>
            <span className={styles.name}>{item.nameKo}</span>
            <TierChip tier="free" />
          </div>
        ))}
      </div>
    </div>
  );
}
