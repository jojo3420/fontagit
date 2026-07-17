/**
 * Google Analytics 및 검색 엔진 연동 설정
 * 모든 값은 NEXT_PUBLIC_* env 변수로 주입되며, 값이 없으면 기능이 비활성화된다.
 */

/**
 * GA4 Measurement ID
 * https://support.google.com/analytics/answer/12270356 참고
 */
export const GA_ID = process.env.NEXT_PUBLIC_GA_ID;

/**
 * Google Search Console 메타태그 값
 * Google Search Console에서 도메인 소유권 확인 시 사용
 */
export const GOOGLE_SITE_VERIFICATION = process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION;

/**
 * Naver Search Advisor 메타태그 값
 * Naver Search Advisor에서 도메인 소유권 확인 시 사용
 */
export const NAVER_SITE_VERIFICATION = process.env.NEXT_PUBLIC_NAVER_SITE_VERIFICATION;

/**
 * Google AdSense Publisher ID
 * pub-XXXXXXXXXXXXXXXX 형식
 */
export const ADSENSE_CLIENT = process.env.NEXT_PUBLIC_ADSENSE_CLIENT;

/**
 * 측정/광고 기능 활성 여부 (디버그/테스트용)
 */
export const isAnalyticsEnabled = Boolean(GA_ID);
export const isAdSenseEnabled = Boolean(ADSENSE_CLIENT);
