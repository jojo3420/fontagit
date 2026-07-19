import type { Font } from "@/types/font";
import { getSpecimenText } from "@/lib/specimen";
import styles from "./Specimen.module.css";

export function Specimen({
  fontFamily,
  font,
  weights,
  substitute,
}: {
  fontFamily: string;
  font: Font;
  weights: number[];
  substitute?: boolean;
}) {
  const sizes = [24, 18];
  return (
    <div className={styles.wrap}>
      {substitute && <div className={styles.note}>실제 유료 서체가 아닌 대체 견본입니다.</div>}
      {sizes.map((s) => (
        <div key={s}>
          <span className={styles.line} style={{ fontFamily, fontSize: s, fontWeight: weights[Math.min(Math.floor((s - 18) / 6), weights.length - 1)] }}>{getSpecimenText(font, true)}</span>
        </div>
      ))}
      <div className={styles.cap}>지원 굵기: {weights.join(", ")}</div>
    </div>
  );
}
