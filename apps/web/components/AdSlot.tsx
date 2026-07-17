"use client";

import { useEffect } from "react";
import { ADSENSE_CLIENT } from "@/lib/analytics/constants";
import styles from "./AdSlot.module.css";

/**
 * Google AdSense 광고 슬롯
 * - NEXT_PUBLIC_ADSENSE_CLIENT 있을 때만 adsbygoogle 스크립트 로드
 * - min-height로 높이 예약하여 CLS(Cumulative Layout Shift) 방지
 * - env 없으면 빈 박스만 렌더 (레이아웃 안정성)
 * - 광고 라이트 정책: 성장기 최소 노출
 */
export function AdSlot() {
  useEffect(() => {
    if (ADSENSE_CLIENT && window.adsbygoogle) {
      try {
        // adsbygoogle 광고 푸시 (next/script 이후에만 실행)
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      } catch (e) {
        // 광고 푸시 실패 무음 처리 (network/adblock 등)
        // 예외를 던지지 않음 - 광고 실패가 서비스 가용성을 깨뜨리면 안 됨
      }
    }
  }, []);

  return (
    <div className={styles.container}>
      {ADSENSE_CLIENT ? (
        <ins
          className="adsbygoogle"
          style={{ display: "block" }}
          data-ad-client={ADSENSE_CLIENT}
          data-ad-slot="TODO_PLACE_AD_SLOT_ID"
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

