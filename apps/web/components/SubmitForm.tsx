"use client";

import { FilterChip } from "@/components/FilterChip";
import styles from "./SubmitForm.module.css";

export function SubmitForm() {
  return (
    <form className={styles.form} onSubmit={(e) => e.preventDefault()}>
      <h1 className={styles.title}>폰트를 FontAgit에 등록하세요</h1>
      <p className={styles.subtitle}>
        검토를 거쳐 FontAgit에 추가되고, 찾는 사람들에게 소개됩니다.
      </p>

      <label className={styles.field}>
        <span className={styles.label}>
          폰트 이름 <span className={styles.req}>*</span>
        </span>
        <input
          className={styles.input}
          type="text"
          placeholder="예: Noto Sans Korean"
        />
      </label>

      <label className={styles.field}>
        <span className={styles.label}>
          설명 <span className={styles.req}>*</span>
        </span>
        <textarea
          className={styles.textarea}
          placeholder="폰트의 특징, 용도, 디자인 철학 등을 설명해주세요."
        />
      </label>

      <label className={styles.field}>
        <span className={styles.label}>
          제작자 <span className={styles.req}>*</span>
        </span>
        <input className={styles.input} type="text" placeholder="이름 또는 팀" />
      </label>

      <label className={styles.field}>
        <span className={styles.label}>
          이메일 <span className={styles.req}>*</span>
        </span>
        <input
          className={styles.input}
          type="email"
          placeholder="contact@example.com"
        />
      </label>

      <label className={styles.field}>
        <span className={styles.label}>
          공식 페이지 URL <span className={styles.req}>*</span>
        </span>
        <input className={styles.input} type="url" placeholder="https://" />
      </label>

      <div className={styles.field}>
        <span className={styles.label}>라이선스</span>
        <div className={styles.chips}>
          <FilterChip active>무료</FilterChip>
          <FilterChip>유료</FilterChip>
          <FilterChip>조건부</FilterChip>
        </div>
      </div>

      <button type="submit" className={styles.submit}>
        신청 보내기
      </button>
    </form>
  );
}
