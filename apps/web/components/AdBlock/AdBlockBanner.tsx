"use client";

import { useEffect, useState } from "react";
import styles from "./AdBlockBanner.module.css";

/**
 * 애드블록 감지 배너
 * - 광고 로드 실패 감지 시 정중한 안내 배너 표시
 * - 사용자가 닫기 가능
 * - 강제 차단이 아닌 정중한 권유 수준
 */
export function AdBlockBanner(): React.ReactNode {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // adsbygoogle가 로드되지 않았거나 광고 푸시 실패 감지
    const checkAdBlock = () => {
      if (
        typeof window !== "undefined" &&
        (!window.adsbygoogle || (window.adsbygoogle && window.adsbygoogle.loaded === false))
      ) {
        // 짧은 지연 후 확인 (광고 로드 완료 대기)
        setTimeout(() => {
          if (!window.adsbygoogle || window.adsbygoogle.loaded === false) {
            setIsVisible(true);
          }
        }, 2000);
      }
    };

    checkAdBlock();
  }, []);

  if (!isVisible) {
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
