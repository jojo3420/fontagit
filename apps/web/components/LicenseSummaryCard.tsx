import type { Font } from "@/types/font";
import {
  commercialLabel, webfontLabel, redistributionLabel,
  commercialState, webfontState, redistributionState,
  auditPermissionLabel, auditPermissionState,
  attributionLabel, attributionState,
  deriveSellerHost, type LicenseState,
} from "@/lib/license";
import { OfficialLinkCta } from "./OfficialLinkCta";
import styles from "./LicenseSummaryCard.module.css";

const STATE_ICON: Record<LicenseState, string> = { ok: "✓", cond: "!", no: "✕", unknown: "?" };

const LICENSE_HELP = {
  commercial: "광고-상품-웹사이트-영상 등 상업 활동의 결과물에 폰트를 사용할 수 있는지 뜻해요.",
  modify: "글자 모양이나 폰트 파일을 바꿔 파생 폰트를 만들 수 있는지 뜻해요.",
  redistribute: "폰트 파일 자체를 다른 사람에게 다시 제공할 수 있는지 뜻해요.",
  embedding: "폰트 파일을 PDF-전자책-앱 같은 문서나 프로그램 안에 포함할 수 있는지 뜻해요.",
  fontSale: "폰트 파일 자체를 단독 상품으로 판매할 수 있는지 뜻해요. 폰트를 사용한 결과물 판매와는 달라요.",
  attribution: "폰트 사용이나 파일 배포 시 제작자-라이선스 정보를 밝혀야 하는지 확인하는 항목이에요.",
  webfont: "웹사이트에서 폰트 파일을 불러와 화면 글꼴로 사용할 수 있는지 뜻해요.",
} as const;

type LicenseHelpKey = keyof typeof LICENSE_HELP;

type LicenseRow = {
  label: string;
  value: string;
  state: LicenseState;
  helpKey: LicenseHelpKey;
};

/** 라이선스 요약 사이드바 카드. 폰트 하나의 라이선스/구매 정보를 렌더 */
export function LicenseSummaryCard({ font }: { font: Font }) {
  const isPaid = font.tier === "paid";
  const audit = font.licenseAudit;
  const isLegacy = !audit || audit.sourceMode === "legacy";
  const legacyRows: LicenseRow[] = [
    { label: "상업적 사용", value: commercialLabel(font.license.commercial), state: commercialState(font.license.commercial), helpKey: "commercial" },
    { label: "웹폰트", value: webfontLabel(font.license.webfont), state: webfontState(font.license.webfont), helpKey: "webfont" },
    { label: "재배포", value: redistributionLabel(font.license.redistribution), state: redistributionState(font.license.redistribution), helpKey: "redistribute" },
  ];
  const verifiedRows: LicenseRow[] = audit?.status === "verified" ? [
    { label: "상업적 사용", value: auditPermissionLabel(audit.commercial), state: auditPermissionState(audit.commercial), helpKey: "commercial" },
    { label: "수정", value: auditPermissionLabel(audit.modify), state: auditPermissionState(audit.modify), helpKey: "modify" },
    { label: "재배포", value: auditPermissionLabel(audit.redistribute), state: auditPermissionState(audit.redistribute), helpKey: "redistribute" },
    { label: "임베딩", value: auditPermissionLabel(audit.embedding), state: auditPermissionState(audit.embedding), helpKey: "embedding" },
    { label: "폰트 판매", value: auditPermissionLabel(audit.fontSale), state: auditPermissionState(audit.fontSale), helpKey: "fontSale" },
    { label: "출처 표기", value: attributionLabel(audit.attribution), state: attributionState(audit.attribution), helpKey: "attribution" },
  ] : [];
  const rows = isLegacy ? legacyRows : verifiedRows;
  const notice = isPaid
    ? "조건은 판매처 정책에 따릅니다. 구매 전 라이선스 범위를 확인하세요."
    : "무료 라이선스라도 사용 전 조건을 확인하세요.";
  const ctaLabel = isPaid
    ? "구매하러 가기"
    : font.downloadSourceKind === "archive"
      ? "다운로드 페이지로 이동(아카이브 제공)"
      : font.downloadSourceKind === "public"
        ? "공개 출처에서 내려받기"
        : "공식 페이지에서 내려받기";
  const price = isPaid && font.priceFrom ? `₩${font.priceFrom.toLocaleString()}~` : null;
  const legacyHref = font.legacyOfficialUrl ?? font.officialUrl;
  const downloadHref = isLegacy
    ? legacyHref
    : audit?.status === "verified" && font.downloadStatus === "verified"
      ? font.downloadUrl
      : null;
  const host = deriveSellerHost(downloadHref ?? "");
  const checkedAt = isLegacy ? font.license.verifiedAt : audit?.checkedAt;
  const sourceLabel = audit?.sourceKind === "official" ? "제작사 공식 출처" : "공공기관 출처";

  return (
    <aside className={styles.card}>
      <h2 className={styles.title}>라이선스 요약</h2>
      <p className={styles.sub}>{font.license.type || "조건 확인 중"}{checkedAt ? ` ${String.fromCharCode(183)} 확인일 ${checkedAt}` : ""}</p>
      {!isLegacy && audit?.status !== "verified" ? (
        <p className={styles.review} role="status">라이선스 재확인 필요</p>
      ) : (
        <ul className={styles.rows}>
          {rows.map((r) => {
            const helpId = `license-help-${font.slug}-${r.helpKey}`;
            return (
              <li key={r.label} className={styles.row}>
                <span className={`${styles.icon} ${styles[r.state]}`} aria-hidden>{STATE_ICON[r.state]}</span>
                <span className={styles.labelHelp}>
                  <span className={styles.rowLabel}>{r.label}</span>
                  <button
                    type="button"
                    className={styles.helpTrigger}
                    aria-label={`${r.label} 설명`}
                    aria-describedby={helpId}
                  >
                    i
                  </button>
                  <span id={helpId} role="tooltip" className={styles.tooltip}>
                    {LICENSE_HELP[r.helpKey]}
                  </span>
                </span>
                <span className={`${styles.rowValue} ${styles[r.state]}`}>{r.value}</span>
              </li>
            );
          })}
        </ul>
      )}
      {!isLegacy && audit?.summary && <p className={styles.summary}>{audit.summary}</p>}
      {font.downloadStatus === "broken" && <p className={styles.review}>다운로드 링크 확인 불가</p>}
      <p className={styles.notice}>{notice}</p>
      {downloadHref && (
        <OfficialLinkCta slug={font.slug} href={downloadHref} className={styles.cta}>
          <span>{ctaLabel}</span>
          {price && <span className={styles.price}>{price}</span>}
        </OfficialLinkCta>
      )}
      {host && <p className={styles.seller}>이동 → {host}</p>}
      <div className={styles.links}>
        {font.foundryUrl && <a href={font.foundryUrl} target="_blank" rel="noopener noreferrer">제작사 홈페이지</a>}
        {!isLegacy && audit?.sourceUrl && <a href={audit.sourceUrl} target="_blank" rel="noopener noreferrer">{sourceLabel} - 원문 보기</a>}
      </div>
    </aside>
  );
}
