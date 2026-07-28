"use client";

import { useState } from "react";
import type { ComparePreset } from "@/data/pairings";
import { PairingPresets } from "./PairingPresets";
import { CompareLazy } from "./CompareLazy";
import styles from "./HomeCompareSection.module.css";

export function HomeCompareSection() {
  const [preset, setPreset] = useState<ComparePreset | undefined>(undefined);

  const handleSelect = (next: ComparePreset) => {
    setPreset(next);
    document.getElementById("compare")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <>
      <section className={styles.pairingSection} aria-labelledby="pairing-heading">
        <div className={styles.container}>
          <PairingPresets onSelect={handleSelect} />
        </div>
      </section>
      <section id="compare" className={styles.compareSection} aria-labelledby="compare-heading">
        <div className={styles.container}>
          <CompareLazy placeholder={<div className={styles.comparePlaceholder} />} preset={preset} />
        </div>
      </section>
    </>
  );
}
