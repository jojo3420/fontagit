import Link from "next/link";
import styles from "./Footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.topRow}>
        <span className={styles.tagline}>당신의 폰트 아지트 </span>
        <div className={styles.links}>
          <Link href="/fonts">폰트</Link>
          <Link href="/trends">트렌드</Link>
          <Link href="/privacy">개인정보처리방침</Link>
          <Link href="/about">소개</Link>
          <Link href="/contact">문의</Link>
          <Link href="/disclaimer">면책</Link>
        </div>
      </div>
      <p className={styles.disclaimer}>
        라이선스 정보는 확인일 기준 참고용이며 최종 확인은 각 제작사 공식 페이지에서 하세요.
      </p>
    </footer>
  );
}
