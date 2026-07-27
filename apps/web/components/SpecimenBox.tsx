"use client";
import { useState } from "react";
import type { Font } from "@/types/font";
import { getDefaultSpecimenText } from "@/lib/specimen";
import { resolveFontPreview } from "@/lib/fontPreview";
import { LazyFontPreview } from "./LazyFontPreview";
import styles from "./SpecimenBox.module.css";

/**
 * 견본 박스. 대형 견본 텍스트를 fontFamily로 렌더한다.
 * editable=true면 하단 입력이 견본을 실시간 갱신(무료 폰트).
 * caption이 있으면 견본 아래 회색 주석 표시(유료 대체 견본 안내).
 * text/onTextChange를 주면 controlled로 동작(상세 화면 문장 공유).
 * stylesheetManaged=true면 시트 로드는 부모 책임(중복 요청 방지).
 */
export function SpecimenBox({
  font,
  editable,
  initialText,
  caption,
  text: controlledText,
  onTextChange,
  stylesheetManaged = false,
}: {
  font: Font;
  editable: boolean;
  initialText?: string;
  caption?: string;
  text?: string;
  onTextChange?: (text: string) => void;
  stylesheetManaged?: boolean;
}) {
  const [innerText, setInnerText] = useState(
    initialText ?? getDefaultSpecimenText(font)
  );
  const isControlled = controlledText !== undefined;
  const text = isControlled ? controlledText : innerText;
  const setText = (next: string) => {
    if (!isControlled) setInnerText(next);
    onTextChange?.(next);
  };
  return (
    <div className={styles.box}>
      {stylesheetManaged ? (
        <div
          className={styles.sample}
          style={{ fontFamily: resolveFontPreview(font).fontFamily }}
        >
          {text || " "}
        </div>
      ) : (
        <LazyFontPreview font={font} className={styles.sample}>
          {text || " "}
        </LazyFontPreview>
      )}
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
