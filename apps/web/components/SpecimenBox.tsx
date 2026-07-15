"use client";
import { useState } from "react";
import styles from "./SpecimenBox.module.css";

const DEFAULT_TEXT = "다람쥐 헌 쳇바퀴에 타고파";

/**
 * 견본 박스. 대형 견본 텍스트를 fontFamily로 렌더한다.
 * editable=true면 하단 입력이 견본을 실시간 갱신(무료 폰트).
 * caption이 있으면 견본 아래 회색 주석 표시(유료 대체 견본 안내).
 */
export function SpecimenBox({
  fontFamily,
  editable,
  initialText,
  caption,
}: {
  fontFamily: string;
  editable: boolean;
  initialText?: string;
  caption?: string;
}) {
  const [text, setText] = useState(initialText ?? DEFAULT_TEXT);
  return (
    <div className={styles.box}>
      <div className={styles.sample} style={{ fontFamily }}>{text || " "}</div>
      {caption && <p className={styles.caption}>{caption}</p>}
      {editable && (
        <input
          className={styles.input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="미리볼 문장을 입력하세요"
          aria-label="미리보기 입력"
        />
      )}
    </div>
  );
}
