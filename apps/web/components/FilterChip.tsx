import styles from "./FilterChip.module.css";

type Props = { active?: boolean; children: React.ReactNode };

export function FilterChip({ active = false, children }: Props) {
  return <button type="button" className={styles.chip} aria-pressed={active}>{children}</button>;
}
