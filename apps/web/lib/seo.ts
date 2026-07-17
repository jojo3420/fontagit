/**
 * SEO 설정 및 헬퍼 함수
 */

export const BASE_URL = "https://fontagit.com";

export const SITE_NAME = "FontAgit";
export const SITE_DESCRIPTION = "한국 웹폰트를 한눈에 - 무료-유료 서체 비교, 라이선스, 유사 폰트 추천";

export function getSiteUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${BASE_URL}${normalized}`;
}
