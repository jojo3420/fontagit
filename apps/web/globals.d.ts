/**
 * AdSense 글로벌 타입 선언
 */
declare global {
  interface Window {
    adsbygoogle?: Array<Record<string, unknown>> & { loaded?: boolean };
    dataLayer?: unknown[];
  }
}

export {};
