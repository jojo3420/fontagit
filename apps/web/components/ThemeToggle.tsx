"use client";
import { useEffect, useState } from "react";
import styles from "./ThemeToggle.module.css";

type Theme = "light" | "dark";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme");
    if (current === "dark" || current === "light") setTheme(current);
  }, []);

  function toggle() {
    // 초기 클릭 경쟁 방지: state가 아닌 실제 DOM data-theme를 기준으로 다음 값을 계산.
    const current = document.documentElement.getAttribute("data-theme");
    const next: Theme = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    setTheme(next);
    try {
      localStorage.setItem("theme", next);
    } catch {}
  }

  return (
    <button type="button" className={styles.btn} onClick={toggle} aria-label="다크모드 전환" aria-pressed={theme === "dark"}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M20 13a7 7 0 1 1-9-9 6 6 0 0 0 9 9Z" /></svg>
    </button>
  );
}
