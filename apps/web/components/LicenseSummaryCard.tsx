import type { Font } from "@/types/font";
import {
  commercialLabel, webfontLabel, redistributionLabel,
  commercialState, webfontState, redistributionState,
  deriveSellerHost, type LicenseState,
} from "@/lib/license";
import styles from "./LicenseSummaryCard.module.css";

const STATE_ICON: Record<LicenseState, string> = { ok: "✓", cond: "!", no: "✕" };

/** 라이선스 요약 사이드바 카드. 폰트 하나의 라이선스/구매 정보를 렌더 */
export function LicenseSummaryCard({ font }: { font: Font }) {
  const isPaid = font.tier === "paid";
  const host = deriveSellerHost(font.officialUrl);
  const rows: { label: string; value: string; state: LicenseState }[] = [
    { label: "상업적 사용", value: commercialLabel(font.license.commercial), state: commercialState(font.license.commercial) },
    { label: "웹폰트", value: webfontLabel(font.license.webfont), state: webfontState(font.license.webfont) },
    { label: "재배포", value: redistributionLabel(font.license.redistribution), state: redistributionState(font.license.redistribution) },
  ];
  const notice = isPaid
    ? "조건은 판매처 정책에 따릅니다. 구매 전 라이선스 범위를 확인하세요."
    : "무료 라이선스라도 사용 전 조건을 확인하세요.";
  const ctaLabel = isPaid ? "구매하러 가기" : "공식 페이지에서 내려받기";
  const price = isPaid && font.priceFrom ? `₩${font.priceFrom.toLocaleString()}~` : null;

  return (
    <aside className={styles.card}>
      <h2 className={styles.title}>라이선스 요약</h2>
      <p className={styles.sub}>{font.license.type} {String.fromCharCode(183)} 확인일 {font.license.verifiedAt}</p>
      <ul className={styles.rows}>
        {rows.map((r) => (
          <li key={r.label} className={styles.row}>
            <span className={`${styles.icon} ${styles[r.state]}`} aria-hidden>{STATE_ICON[r.state]}</span>
            <span className={styles.rowLabel}>{r.label}</span>
            <span className={`${styles.rowValue} ${styles[r.state]}`}>{r.value}</span>
          </li>
        ))}
      </ul>
      <p className={styles.notice}>{notice}</p>
      <a className={styles.cta} href={font.officialUrl} target="_blank" rel="noreferrer">
        <span>{ctaLabel}</span>
        {price && <span className={styles.price}>{price}</span>}
      </a>
      {host && <p className={styles.seller}>이동 → {host}</p>}
    </aside>
  );
}
