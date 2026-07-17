/**
 * Canvas 기반 글리프 지원 감지 유틸리티
 *
 * 폰트가 특정 글자를 지원하는지 판정합니다.
 * 알고리즘: 동일 글자를 지정 폰트와 폴백 폰트로 각각 렌더링한 후
 * Canvas 픽셀 데이터를 비교해 글리프가 다르면 지원, 같으면 미지원으로 판정합니다.
 *
 * 한계:
 * - 폰트 로드 타이밍: document.fonts.ready 이후 호출 필수
 * - 폴백 오탐: 지정 폰트와 폴백 폰트가 우연히 같은 글리프를 가지면 미지원으로 판정될 수 있음
 * - Canvas 성능: 많은 글자 검사 시 성능 저하
 */

/**
 * 렌더링 결과 데이터
 */
interface RenderResult {
  /** 렌더링된 캔버스의 픽셀 데이터 */
  data: Uint8ClampedArray;
  /** 렌더링된 텍스트의 너비 */
  width: number;
}

/**
 * 글자별 지원 여부
 */
export interface GlyphSupportResult {
  /** 검사된 글자 */
  char: string;
  /** 지원 여부 */
  supported: boolean;
}

/**
 * 순수 함수: 중복 제거 및 정규화
 *
 * @param text - 입력 텍스트
 * @returns 정규화된 고유 글자 배열
 */
export function normalizeText(text: string): string[] {
  // 공백 제거 및 각 글자를 배열로 변환
  const trimmed = text.trim();
  if (!trimmed) return [];

  // 중복 제거 (순서 유지)
  const seen = new Set<string>();
  const result: string[] = [];

  for (const char of trimmed) {
    if (!seen.has(char)) {
      seen.add(char);
      result.push(char);
    }
  }

  return result;
}

/**
 * 순수 함수: 글리프 피델리티 비교
 *
 * Canvas 픽셀 데이터 두 개를 비교해 글리프가 다른지 판정합니다.
 * 임계값(threshold) 이상의 픽셀이 다르면 "다른 글리프"로 판정합니다.
 *
 * @param targetData - 지정 폰트로 렌더링한 픽셀 데이터
 * @param fallbackData - 폴백 폰트로 렌더링한 픽셀 데이터
 * @param threshold - 다른 픽셀 개수 임계값 (기본값: 50)
 * @returns true이면 글리프가 다름(지원), false이면 같음(미지원)
 */
export function comparePixelData(
  targetData: Uint8ClampedArray,
  fallbackData: Uint8ClampedArray,
  threshold: number = 50
): boolean {
  if (targetData.length !== fallbackData.length) {
    return true; // 크기가 다르면 다른 글리프
  }

  let diffCount = 0;
  // Alpha 채널만 비교 (R, G, B는 렌더링 환경에 따라 다를 수 있음)
  for (let i = 3; i < targetData.length; i += 4) {
    if (Math.abs(targetData[i] - fallbackData[i]) > 10) {
      diffCount++;
    }
  }

  return diffCount > threshold;
}

/**
 * 순수 함수: 검사 결과 집계
 *
 * 글자별 지원 여부 배열을 입력받아 지원하는 글자와 미지원 글자를 분류합니다.
 *
 * @param results - 글자별 지원 여부 배열
 * @returns 지원/미지원 글자 객체
 */
export function aggregateResults(
  results: GlyphSupportResult[]
): { supported: string[]; unsupported: string[] } {
  const supported: string[] = [];
  const unsupported: string[] = [];

  for (const result of results) {
    if (result.supported) {
      supported.push(result.char);
    } else {
      unsupported.push(result.char);
    }
  }

  return { supported, unsupported };
}

/**
 * Canvas를 사용해 텍스트를 렌더링하고 픽셀 데이터를 반환합니다.
 *
 * 이 함수는 Canvas API에 의존하므로 브라우저 환경에서만 실행 가능합니다.
 *
 * @param text - 렌더링할 텍스트
 * @param fontFamily - CSS font-family 값
 * @param fontSize - 폰트 크기 (픽셀)
 * @returns 렌더링 결과
 */
function renderTextToCanvas(
  text: string,
  fontFamily: string,
  fontSize: number = 48
): RenderResult {
  const canvas = document.createElement("canvas");
  canvas.width = 300;
  canvas.height = 100;

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Canvas 2D context를 가져올 수 없습니다");
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.font = `${fontSize}px ${fontFamily}`;
  ctx.fillStyle = "black";
  ctx.textBaseline = "top";
  ctx.fillText(text, 10, 10);

  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  return {
    data: imageData.data,
    width: ctx.measureText(text).width,
  };
}

/**
 * Canvas 기반 글리프 지원 감지
 *
 * @param text - 검사할 텍스트
 * @param targetFontFamily - 검사 대상 폰트 CSS family
 * @param fallbackFontFamily - 폴백 폰트 CSS family (기본값: system-ui)
 * @returns 글자별 지원 여부 배열
 */
export function detectGlyphSupport(
  text: string,
  targetFontFamily: string,
  fallbackFontFamily: string = "system-ui, sans-serif"
): GlyphSupportResult[] {
  const chars = normalizeText(text);
  if (chars.length === 0) {
    return [];
  }

  const results: GlyphSupportResult[] = [];

  for (const char of chars) {
    try {
      // 지정 폰트로 렌더링
      const targetResult = renderTextToCanvas(char, targetFontFamily);
      // 폴백 폰트로 렌더링
      const fallbackResult = renderTextToCanvas(char, fallbackFontFamily);

      // 픽셀 데이터 비교
      const supported = comparePixelData(targetResult.data, fallbackResult.data);

      results.push({ char, supported });
    } catch (error) {
      // 렌더링 실패 시 미지원으로 처리
      console.error(`글자 '${char}' 검사 중 오류:`, error);
      results.push({ char, supported: false });
    }
  }

  return results;
}
