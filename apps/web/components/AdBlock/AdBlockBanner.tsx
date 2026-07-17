"use client";

import { useEffect, useState } from "react";
import { isAdSenseEnabled } from "@/lib/analytics/constants";
import styles from "./AdBlockBanner.module.css";

/** AdSense를 켠 환경에서만 광고 차단 안내를 표시한다. */
export function AdBlockBanner(): React.ReactNode {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (!isAdSenseEnabled) {
      return;
    }

    const timer = window.setTimeout(() => {
      if (!window.adsbygoogle || window.adsbygoogle.loaded === false) {
        setIsVisible(true);
      }
    }, 3000);

    return () => window.clearTimeout(timer);
  }, []);

  if (!isAdSenseEnabled || !isVisible) {
    return null;
  }

  return (
    <div className={styles.banner} role="complementary" aria-label="광고 차단 감지">
      <div className={styles.content}>
        <p className={styles.message}>
          애드블록을 사용 중이신 것으로 보입니다. 광고 수익은 서비스 유지에 큰 도움이 됩니다.
        </p>
        <button
          className={styles.closeButton}
          onClick={() => setIsVisible(false)}
          aria-label="배너 닫기"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
