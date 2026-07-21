"use client";

import { useState, useCallback } from "react";
import type { FontKey } from "@/types/font";
import { canvasFamilyOf } from "@/lib/fonts";
import { detectGlyphSupport,
  aggregateResults,
  isGlyphCheckSupported, } from "@/lib/glyphSupport";
import type { GlyphSupportResult } from "@/lib/glyphSupport";
import styles from "./GlyphChecker.module.css";

interface GlyphCheckerProps {
  /** 현재 선택된 폰트의 FontKey */
  fontKey: FontKey | null;
  /** 폰트의 이름 (UI 표시용) */
  fontName: string;
  /** 폰트의 tier (웹폰트 지원 여부 판정용) */
  tier: "free" | "paid";
}

/**
 * 글자 포함 검사 컴포넌트
 *
 * 사용자가 입력한 글자가 선택된 폰트에서 지원되는지 Canvas 기반 글리프 감지로 판정합니다.
 * - Tier "free" 웹폰트: 실제 검사 수행
 * - Tier "paid" 또는 로컬 폰트: 검사 불가 안내
 */
export function GlyphChecker({ fontKey, fontName, tier }: GlyphCheckerProps) {
  const [inputText, setInputText] = useState("");
  const [results, setResults] = useState<GlyphSupportResult[]>([]);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Tier A(웹폰트) 판정: 구글폰트 free tier만 지원
  const isWebfontAvailable =
    isGlyphCheckSupported(fontKey, tier);

  const handleCheck = useCallback(async () => {
    if (!inputText.trim()) {
      setError("검사할 글자를 입력해주세요");
      setResults([]);
      return;
    }

    if (!isWebfontAvailable) {
      setError("이 폰트는 글자 지원 확인을 제공하지 않습니다");
      setResults([]);
      return;
    }

    setIsChecking(true);
    setError(null);

    try {
      const targetFamily = canvasFamilyOf(fontKey);
      if (!targetFamily) {
        throw new Error("검사할 폰트를 찾을 수 없습니다");
      }

      // Canvas 검사 전에 실제 생성된 폰트 이름으로 다운로드를 요청한다.
      if (document.fonts) {
        const loadedFaces = await document.fonts.load(`48px ${targetFamily}`);
        if (loadedFaces.length === 0) {
          throw new Error("폰트를 불러오지 못했습니다");
        }
      }

      const detectionResults = detectGlyphSupport(inputText, targetFamily);

      setResults(detectionResults);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다";
      setError(`검사 중 오류: ${message}`);
      setResults([]);
    } finally {
      setIsChecking(false);
    }
  }, [inputText, isWebfontAvailable, fontKey]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputText(e.target.value);
    setResults([]);
    setError(null);
  };

  const handleClear = () => {
    setInputText("");
    setResults([]);
    setError(null);
  };

  // 결과 통계
  const aggregated = aggregateResults(results);
  const totalChecked = results.length;
  const supportCount = aggregated.supported.length;

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>글자 지원 검사</h3>

      {!isWebfontAvailable && (
        <div className={styles.alert}>
          <p>
            <strong>{fontName}</strong>은(는) 글자 지원 확인 기능을 제공하지
            않습니다.
          </p>
          <p className={styles.alertSubtext}>
            {tier === "paid" ? "유료 폰트는 웹폰트를 제공하지 않습니다" : ""}
            {fontKey === "pretendard" ? "로컬 폰트는 글리프 검사를 지원하지 않습니다" : ""}
          </p>
        </div>
      )}

      {isWebfontAvailable && (
        <>
          <div className={styles.inputGroup}>
            <input
              type="text"
              className={styles.input}
              placeholder="검사할 글자를 입력하세요 (예: 한글, ABC, 漢字, ①②③)"
              value={inputText}
              onChange={handleInputChange}
              maxLength={100}
              disabled={isChecking}
              aria-label="글자 검사 입력"
            />
            <button
              type="button"
              className={styles.button}
              onClick={handleCheck}
              disabled={isChecking || !inputText.trim()}
              aria-label="글자 지원 검사"
            >
              {isChecking ? "검사 중..." : "검사"}
            </button>
            <button
              type="button"
              className={styles.clearButton}
              onClick={handleClear}
              disabled={isChecking || !inputText}
              aria-label="입력 초기화"
            >
              지우기
            </button>
          </div>

          {error && <div className={styles.error}>{error}</div>}

          {results.length > 0 && (
            <div className={styles.results}>
              <div className={styles.summary}>
                <span className={styles.badge}>
                  전체: <strong>{totalChecked}</strong>
                </span>
                <span className={`${styles.badge} ${styles.supported}`}>
                  지원: <strong>{supportCount}</strong>
                </span>
                <span className={`${styles.badge} ${styles.unsupported}`}>
                  미지원: <strong>{totalChecked - supportCount}</strong>
                </span>
              </div>

              <div className={styles.charGrid}>
                {results.map(({ char, supported }) => (
                  <div
                    key={char}
                    className={`${styles.charItem} ${
                      supported
                        ? styles.charItemSupported
                        : styles.charItemUnsupported
                    }`}
                    title={
                      supported
                        ? `'${char}' - 지원됨`
                        : `'${char}' - 미지원 (폴백)`
                    }
                  >
                    <span className={styles.char}>{char}</span>
                    <span className={styles.status}>
                      {supported ? "✓" : "✗"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
