"use client";

import { useEffect } from "react";
import {
  ADSENSE_CLIENT,
  ADSENSE_SLOT,
  isAdSenseEnabled,
} from "@/lib/analytics/constants";
import styles from "./AdSlot.module.css";

/**
 * Google AdSense 광고 슬롯
 * - 유효한 AdSense 게시자 ID와 광고 단위 ID가 있을 때만 광고 로드
 * - min-height로 높이 예약하여 CLS(Cumulative Layout Shift) 방지
 * - 설정이 없으면 빈 박스만 렌더 (레이아웃 안정성)
 * - 광고 라이트 정책: 성장기 최소 노출
 */
export function AdSlot() {
  useEffect(() => {
    if (!isAdSenseEnabled) {
      return;
    }

    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;

      if (window.adsbygoogle) {
        window.clearInterval(timer);
        try {
          window.adsbygoogle.push({});
        } catch {
          // 광고 실패가 서비스 기능을 막지 않도록 조용히 종료한다.
        }
      } else if (attempts >= 20) {
        window.clearInterval(timer);
      }
    }, 250);

    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className={styles.container}>
      {isAdSenseEnabled ? (
        <ins
          className="adsbygoogle"
          style={{ display: "block" }}
          data-ad-client={ADSENSE_CLIENT}
          data-ad-slot={ADSENSE_SLOT}
          data-ad-format="auto"
          data-full-width-responsive="true"
        />
      ) : (
        <div className={styles.placeholder} role="status" aria-label="광고 영역">
          {/* env 미설정 시 빈 예약 박스 */}
        </div>
      )}
    </div>
  );
}
