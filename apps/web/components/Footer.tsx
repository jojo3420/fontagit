import Link from "next/link";
import styles from "./Footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <span className={styles.tagline}>당신의 폰트 아지트. 오늘도 좋은 서체 찾으시길.</span>
      <div className={styles.links}>
        <Link href="/fonts">폰트</Link>
        <Link href="/trends">트렌드</Link>
      </div>
    </footer>
  );
}
