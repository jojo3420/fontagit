"use client";

import styles from "./TypeCanvasBar.module.css";

interface TypeCanvasBarProps {
  /** 입력창의 현재 값 */
  value: string;
  /** 입력값이 변경될 때 호출되는 콜백 함수 */
  onChange: (value: string) => void;
  /** 입력창의 placeholder 텍스트 */
  placeholder?: string;
}

/**
 * 타입 캔버스 입력 바
 *
 * 사용자가 문구를 입력할 수 있는 제어 컴포넌트입니다.
 * 입력값은 부모 컴포넌트에서 관리합니다.
 */
export function TypeCanvasBar({
  value,
  onChange,
  placeholder = "문구를 입력하세요",
}: TypeCanvasBarProps) {
  const handleReset = (): void => {
    onChange("");
  };

  return (
    <div className={styles.container}>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.currentTarget.value)}
        placeholder={placeholder}
        className={styles.input}
        aria-label="폰트 견본 텍스트 입력"
      />
      <button type="button" onClick={handleReset} className={styles.resetButton}>
        초기화
      </button>
    </div>
  );
}
