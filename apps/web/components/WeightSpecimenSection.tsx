"use client";
import type { Font } from "@/types/font";
import {
  formatWeightLabel,
  resolveItalicSupport,
  type VariantCombination,
} from "@/lib/weightLabels";
import styles from "./WeightSpecimenSection.module.css";

export type ComboLoadStatus = "loading" | "loaded" | "failed";

export function comboKey(combo: VariantCombination): string {
  return `${combo.weight}-${combo.style}`;
}

const ITALIC_BADGE: Record<string, string> = {
  supported: "이탤릭 지원",
  unsupported: "이탤릭 미지원",
  unknown: "이탤릭 정보 미확인",
};

function rowLabel(combo: VariantCombination): string {
  const base = formatWeightLabel(combo.weight);
  return combo.style === "italic" ? `${base} Italic` : base;
}

/**
 * 지원 굵기 섹션(표시 전용). 견본 행은 combos(정규화 variants) 기준으로만
 * 그린다 — confirmedWeights로 행을 만들지 않는다(합성 견본 방지).
 */
export function WeightSpecimenSection({
  font,
  text,
  combos,
  statuses,
  fontFamily,
}: {
  font: Font;
  text: string;
  combos: VariantCombination[];
  statuses: Record<string, ComboLoadStatus>;
  fontFamily: string;
}) {
  const confirmed = font.confirmedWeights ?? null;
  const italic = resolveItalicSupport(font);
  const hasRows = combos.length > 0;

  return (
    <section className={styles.section} aria-label="지원 굵기">
      <div className={styles.header}>
        <h2 className={styles.title}>지원 굵기</h2>
        <span className={styles.badge}>{ITALIC_BADGE[italic.status]}</span>
      </div>
      <p className={styles.weightList}>
        {confirmed
          ? confirmed.map(formatWeightLabel).join(" - ")
          : "굵기 정보 미확인"}
      </p>
      {hasRows ? (
        <>
          {combos.map((combo) => {
            const status = statuses[comboKey(combo)] ?? "loading";
            return (
              <div key={comboKey(combo)} className={styles.row}>
                <span className={styles.rowLabel}>{rowLabel(combo)}</span>
                {status === "loading" && <div className={styles.skeleton} />}
                {status === "loaded" && (
                  <div
                    className={styles.rowSample}
                    style={{
                      fontFamily,
                      fontWeight: combo.weight,
                      fontStyle: combo.style,
                    }}
                  >
                    {text || " "}
                  </div>
                )}
                {status === "failed" && (
                  <span className={styles.rowFallback}>
                    견본을 불러오지 못했습니다
                  </span>
                )}
              </div>
            );
          })}
          <p className={styles.notice}>
            폰트가 지원하지 않는 글자는 대체 글꼴로 표시될 수 있습니다.
          </p>
        </>
      ) : (
        <p className={styles.rowFallback}>
          {font.sourceTier === "A" ? (
            "굵기별 견본 정보를 확인하지 못했습니다"
          ) : (
            <>
              이 폰트는 웹 견본을 제공하지 않습니다
              {font.officialUrl ? (
                <>
                  {" - "}
                  <a href={font.officialUrl} target="_blank" rel="noopener noreferrer">
                    공식 배포 페이지에서 확인
                  </a>
                </>
              ) : null}
            </>
          )}
        </p>
      )}
    </section>
  );
}
