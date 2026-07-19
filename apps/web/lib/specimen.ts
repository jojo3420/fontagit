import type { ScriptStatus, SourceTier } from "@/types/font";

/** 폰트 언어별 팬그램(견본 문구) */

const KOREAN_PANGRAM = "다람쥐 헌 쳇바퀴에 타고파";
const ENGLISH_PANGRAM = "The quick brown fox jumps over the lazy dog";
const MIXED_CHECK_TEXT = "가나다 ABCabc 12345";

interface SpecimenLanguageInput {
  subsets: string[];
  scriptStatus?: ScriptStatus;
  sourceTier?: SourceTier;
}

export type SpecimenLanguage = "korean" | "english" | "mixed";

/** 검증된 문자 범위만 사용한다. sourceTier는 언어 근거로 사용하지 않는다. */
export function resolveSpecimenLanguage(font: SpecimenLanguageInput): SpecimenLanguage {
  if (font.scriptStatus !== "verified") return "mixed";
  if (font.subsets.includes("korean")) return "korean";
  if (font.subsets.includes("latin")) return "english";
  return "mixed";
}

/** 언어에 맞는 팬그램 선택 */
export function getSpecimenText(
  font: SpecimenLanguageInput,
  includeEnglish: boolean = false
): string {
  const language = resolveSpecimenLanguage(font);
  if (language === "mixed") return MIXED_CHECK_TEXT;

  const isKorean = language === "korean";
  const baseText = isKorean ? KOREAN_PANGRAM : ENGLISH_PANGRAM;

  if (isKorean && includeEnglish) {
    return `${baseText} ABCabc 12345`;
  } else if (!isKorean && includeEnglish) {
    return `${baseText} 0123`;
  }

  return baseText;
}

/** SpecimenBox 컴포넌트용 기본 텍스트 */
export function getDefaultSpecimenText(font: SpecimenLanguageInput): string {
  const language = resolveSpecimenLanguage(font);
  if (language === "korean") return KOREAN_PANGRAM;
  if (language === "english") return ENGLISH_PANGRAM;
  return MIXED_CHECK_TEXT;
}
