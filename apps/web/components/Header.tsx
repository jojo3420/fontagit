import Link from "next/link";
import styles from "./Header.module.css";
import { ThemeToggle } from "./ThemeToggle";
import { HeaderSearch } from "./HeaderSearch";

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
        <Link href="/#compare" className={styles.toolLink}>비교</Link>
        <Link href="/collections">컬렉션</Link>
        <Link href="/submit">등록</Link>
      </nav>
      <div className={styles.actions}>
        <ThemeToggle />
        <HeaderSearch />
      </div>
    </header>
  );
}
