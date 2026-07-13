import Link from "next/link";
import styles from "./Button.module.css";

type Props = { variant?: "primary" | "secondary"; href?: string; children: React.ReactNode };

export function Button({ variant = "primary", href, children }: Props) {
  const cls = `${styles.btn} ${styles[variant]}`;
  if (href) return <Link className={cls} href={href}>{children}</Link>;
  return <button type="button" className={cls}>{children}</button>;
}
