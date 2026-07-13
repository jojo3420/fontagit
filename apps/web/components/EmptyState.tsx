import Link from "next/link";
import styles from "./EmptyState.module.css";

interface EmptyStateProps {
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
}

export function EmptyState({
  title,
  description,
  actionHref,
  actionLabel,
}: EmptyStateProps) {
  return (
    <div className={styles.wrap}>
      <div className={styles.title}>{title}</div>
      <p className={styles.desc}>{description}</p>
      {actionHref && actionLabel && (
        <Link href={actionHref} className={styles.action}>
          {actionLabel}
        </Link>
      )}
    </div>
  );
}
