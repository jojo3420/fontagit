"use client";

import Script from "next/script";
import { GA_ID } from "@/lib/analytics/constants";

/**
 * Google Analytics 4 로더
 * NEXT_PUBLIC_GA_ID가 설정된 경우에만 gtag 스크립트를 로드한다.
 * output:'export' 정적 내보내기에서도 클라이언트 스크립트로 동작한다.
 */
export function GoogleAnalytics(): React.ReactNode {
  if (!GA_ID) {
    return null;
  }

  return (
    <>
      {/* GA4 gtag.js 로더 */}
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
        strategy="afterInteractive"
      />
      {/* GA 초기화 */}
      <Script
        id="google-analytics"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', '${GA_ID}', {
              page_path: window.location.pathname,
            });
          `,
        }}
      />
    </>
  );
}
