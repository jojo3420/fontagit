import styles from "./FilterChip.module.css";

type Props = {
  active?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
};

export function FilterChip({ active = false, children, onClick }: Props) {
  return (
    <button
      type="button"
      className={styles.chip}
      aria-pressed={active}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
