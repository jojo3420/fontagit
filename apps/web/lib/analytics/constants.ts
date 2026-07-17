/** 공개 환경 변수는 형식을 확인한 뒤에만 외부 스크립트에 사용한다. */
function readValidatedEnv(value: string | undefined, pattern: RegExp): string | undefined {
  const normalized = value?.trim();
  return normalized && pattern.test(normalized) ? normalized : undefined;
}

export const GA_ID = readValidatedEnv(process.env.NEXT_PUBLIC_GA_ID, /^G-[A-Z0-9]+$/);

export const GOOGLE_SITE_VERIFICATION =
  process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION?.trim() || undefined;

export const NAVER_SITE_VERIFICATION =
  process.env.NEXT_PUBLIC_NAVER_SITE_VERIFICATION?.trim() || undefined;

export const ADSENSE_CLIENT = readValidatedEnv(
  process.env.NEXT_PUBLIC_ADSENSE_CLIENT,
  /^ca-pub-\d+$/,
);

export const ADSENSE_SLOT = readValidatedEnv(process.env.NEXT_PUBLIC_ADSENSE_SLOT, /^\d+$/);

export const isAnalyticsEnabled = Boolean(GA_ID);
export const isAdSenseEnabled = Boolean(ADSENSE_CLIENT && ADSENSE_SLOT);
