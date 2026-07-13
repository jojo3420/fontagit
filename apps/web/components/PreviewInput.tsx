"use client";
import { useState } from "react";
import styles from "./PreviewInput.module.css";

export function PreviewInput({ fontFamily }: { fontFamily: string }) {
  const [text, setText] = useState("입력해 보세요");
  return (
    <div className={styles.wrap}>
      <div className={styles.sample} style={{ fontFamily }}>{text || " "}</div>
      <input className={styles.input} value={text} onChange={(e) => setText(e.target.value)} placeholder="미리볼 문장을 입력하세요" aria-label="미리보기 입력" />
    </div>
  );
}
