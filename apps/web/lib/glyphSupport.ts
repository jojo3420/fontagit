const MAX_GLYPHS = 50;

export interface GlyphSupportResult {
  char: string;
  supported: boolean;
}

export function normalizeText(text: string): string[] {
  const seen = new Set<string>();
  const result: string[] = [];

  for (const char of text) {
    if (/\s/u.test(char) || seen.has(char)) {
      continue;
    }

    seen.add(char);
    result.push(char);

    if (result.length >= MAX_GLYPHS) {
      break;
    }
  }

  return result;
}

export function comparePixelData(
  targetData: Uint8ClampedArray,
  fallbackData: Uint8ClampedArray,
  threshold = 50,
): boolean {
  if (targetData.length !== fallbackData.length) {
    return true;
  }

  let diffCount = 0;
  for (let index = 3; index < targetData.length; index += 4) {
    if (Math.abs(targetData[index] - fallbackData[index]) > 10) {
      diffCount += 1;
    }
  }

  return diffCount > threshold;
}

/** 서로 다른 두 대체 글꼴과 모두 다를 때만 지원 글리프로 판정한다. */
export function isGlyphSupported(
  targetWithFallbackA: Uint8ClampedArray,
  fallbackA: Uint8ClampedArray,
  targetWithFallbackB: Uint8ClampedArray,
  fallbackB: Uint8ClampedArray,
  threshold = 50,
): boolean {
  return (
    comparePixelData(targetWithFallbackA, fallbackA, threshold) &&
    comparePixelData(targetWithFallbackB, fallbackB, threshold)
  );
}

export function aggregateResults(results: GlyphSupportResult[]): {
  supported: string[];
  unsupported: string[];
} {
  const supported: string[] = [];
  const unsupported: string[] = [];

  for (const result of results) {
    (result.supported ? supported : unsupported).push(result.char);
  }

  return { supported, unsupported };
}

function renderTextToCanvas(text: string, fontFamily: string): Uint8ClampedArray {
  const canvas = document.createElement("canvas");
  canvas.width = 300;
  canvas.height = 100;

  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Canvas 2D context를 가져올 수 없습니다");
  }

  context.clearRect(0, 0, canvas.width, canvas.height);
  context.font = `48px ${fontFamily}`;
  context.fillStyle = "black";
  context.textBaseline = "top";
  context.fillText(text, 10, 10);

  return context.getImageData(0, 0, canvas.width, canvas.height).data;
}

/** 실제 폰트와 monospace/serif 대체 렌더링을 교차 비교한다. */
export function detectGlyphSupport(
  text: string,
  targetFontFamily: string,
): GlyphSupportResult[] {
  return normalizeText(text).map((char) => {
    try {
      const fallbackA = "monospace";
      const fallbackB = "serif";
      const targetWithFallbackA = renderTextToCanvas(
        char,
        `${targetFontFamily}, ${fallbackA}`,
      );
      const targetWithFallbackB = renderTextToCanvas(
        char,
        `${targetFontFamily}, ${fallbackB}`,
      );

      return {
        char,
        supported: isGlyphSupported(
          targetWithFallbackA,
          renderTextToCanvas(char, fallbackA),
          targetWithFallbackB,
          renderTextToCanvas(char, fallbackB),
        ),
      };
    } catch (error) {
      console.error(`글자 '${char}' 검사 중 오류:`, error);
      return { char, supported: false };
    }
  });
}
