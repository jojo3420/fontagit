"use client";

import React, { useEffect, useId, useRef, useState } from "react";
import { ADFIT_LOADER_SRC } from "@/lib/analytics/constants";
import styles from "./AdFitUnit.module.css";

interface AdFitUnitProps {
  unit: string;
  width: number;
  height: number;
  label?: boolean;
}

/** 개별 AdFit 광고 단위를 렌더해야 하는지 판정 */
function shouldRenderAdFit(unit: string): boolean {
  return unit.length > 0 && process.env.NODE_ENV !== "development";
}

/** AdFit data-ad-onfail용 전역 콜백 함수명 생성 */
function adfitOnfailName(id: string): string {
  return `adfitOnfail_${id.replace(/[^a-zA-Z0-9]/g, "")}`;
}

/**
 * 카카오 AdFit 광고 컴포넌트
 * 광고가 로드되지 않으면 컨테이너가 자동으로 collapse됨
 */
export function AdFitUnit({ unit, width, height, label }: AdFitUnitProps): React.ReactNode {
  const id = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(true);
  const callbackName = adfitOnfailName(id);

  // onfail 콜백 등록 (no-ad 시 자동 collapse)
  useEffect(() => {
    const globalObj = typeof window !== "undefined" ? window : undefined;
    if (!globalObj) return;

    ((globalObj as unknown) as Record<string, (arg: unknown) => void>)[callbackName] = () => {
      setActive(false);
    };

    return () => {
      delete ((globalObj as unknown) as Record<string, unknown>)[callbackName];
    };
  }, [callbackName]);

  // 스크립트 주입 (로더 로드)
  useEffect(() => {
    if (!shouldRenderAdFit(unit) || !containerRef.current) return;

    const currentContainer = containerRef.current;
    const script = document.createElement("script");
    script.async = true;
    script.src = ADFIT_LOADER_SRC;
    currentContainer.appendChild(script);

    return () => {
      if (currentContainer?.contains(script)) {
        currentContainer.removeChild(script);
      }
    };
  }, [unit]);

  if (!shouldRenderAdFit(unit) || !active) {
    return null;
  }

  return (
    <div ref={containerRef} className={styles.container} style={{ minHeight: height }}>
      <ins
        className="kakao_ad_area"
        style={{ display: "none", width: "100%", height }}
        data-ad-unit={unit}
        data-ad-width={width}
        data-ad-height={height}
        data-ad-onfail={callbackName}
      />
      {label && <div className={styles.label}>광고</div>}
    </div>
  );
}
