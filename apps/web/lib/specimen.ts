/** 폰트 언어별 팬그램(견본 문구) */

const KOREAN_PANGRAM = "다람쥐 헌 쳇바퀴에 타고파";
const ENGLISH_PANGRAM = "The quick brown fox jumps over the lazy dog";

/** 폰트의 subsets 목록을 보고 한글/영문 판별 */
export function isKoreanFont(subsets: string[]): boolean {
  return subsets.includes("korean");
}

/** 언어에 맞는 팬그램 선택 */
export function getSpecimenText(
  subsets: string[],
  includeEnglish: boolean = false
): string {
  const isKorean = isKoreanFont(subsets);
  const baseText = isKorean ? KOREAN_PANGRAM : ENGLISH_PANGRAM;

  if (isKorean && includeEnglish) {
    return `${baseText} ABCabc 12345`;
  } else if (!isKorean && includeEnglish) {
    return `${baseText} 0123`;
  }

  return baseText;
}

/** SpecimenBox 컴포넌트용 기본 텍스트 */
export function getDefaultSpecimenText(subsets: string[]): string {
  return isKoreanFont(subsets) ? KOREAN_PANGRAM : ENGLISH_PANGRAM;
}
