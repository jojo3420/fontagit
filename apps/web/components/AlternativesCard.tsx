import Link from "next/link";
import type { Font } from "@/types/font";
import { familyOf } from "@/lib/fonts";
import styles from "./AlternativesCard.module.css";

/** 유료 폰트의 비슷한 무료 대안 카드. items가 비면 렌더하지 않음 */
export function AlternativesCard({ category, items }: { category: string; items: Font[] }) {
  if (items.length === 0) return null;
  return (
    <aside className={styles.card}>
      <h2 className={styles.title}>비슷한 무료 대안 {items.length}개</h2>
      <p className={styles.sub}>분위기가 가까운 무료 {category}입니다</p>
      <ul className={styles.list}>
        {items.map((f) => (
          <li key={f.slug} className={styles.item}>
            <Link href={`/fonts/${f.slug}`} className={styles.name} style={{ fontFamily: familyOf(f.fontKey) }}>
              {f.nameKo}
            </Link>
            <span className={styles.badge}>무료</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
