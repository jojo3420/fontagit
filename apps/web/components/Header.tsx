import Link from "next/link";
import styles from "./Header.module.css";
import { ThemeToggle } from "./ThemeToggle";

export function Header() {
  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <Link href="/" className={styles.wordmark} aria-label="FontAgit 홈">
          Font<span className={styles.a}>A</span>git
        </Link>
        <span className={styles.ko}>폰트 아지트</span>
      </div>
      <nav className={styles.nav}>
        <Link href="/fonts">폰트</Link>
        <Link href="/trends">트렌드</Link>
        <Link href="/playground" className={styles.toolLink}>캔버스</Link>
        <Link href="/compare" className={styles.toolLink}>비교</Link>
        <Link href="/collections">컬렉션</Link>
        <Link href="/submit">등록</Link>
      </nav>
      <div className={styles.actions}>
        <ThemeToggle />
        <button type="button" className={styles.iconBtn} aria-label="검색">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
        </button>
      </div>
    </header>
  );
}
