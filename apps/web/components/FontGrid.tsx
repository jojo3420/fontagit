import type { Font } from "@/types/font";
import { FontCard } from "./FontCard";
import styles from "./FontGrid.module.css";

interface FontGridProps {
  fonts: Font[];
}

export function FontGrid({ fonts }: FontGridProps) {
  return (
    <div className={styles.grid}>
      {fonts.map((font) => (
        <FontCard key={font.slug} font={font} />
      ))}
    </div>
  );
}
