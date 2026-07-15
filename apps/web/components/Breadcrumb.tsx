import Link from "next/link";
import styles from "./Breadcrumb.module.css";

/** 브레드크럼 항목. 마지막 항목은 href 없이 현재 위치로 표시 */
export type BreadcrumbItem = { label: string; href?: string };

/** 상단 경로 표시. 구분자는 › */
export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className={styles.wrap} aria-label="경로">
      {items.map((item, i) => (
        <span key={i} className={styles.item}>
          {item.href ? (
            <Link href={item.href} className={styles.link}>{item.label}</Link>
          ) : (
            <span className={styles.current}>{item.label}</span>
          )}
          {i < items.length - 1 && <span className={styles.sep} aria-hidden>›</span>}
        </span>
      ))}
    </nav>
  );
}
