"use client";
import { FilterChip } from "./FilterChip";
import styles from "./SubmitForm.module.css";

export function SubmitForm() {
  return (
    <form className={styles.form} onSubmit={(e) => e.preventDefault()}>
      <label className={styles.field}>
        <span className={styles.label}>폰트 이름 <span className={styles.req}>*</span></span>
        <input className={styles.input} type="text" placeholder="예: 아지트 고딕" />
      </label>
      <div className={styles.row}>
        <label className={styles.field}>
          <span className={styles.label}>제작자 <span className={styles.req}>*</span></span>
          <input className={styles.input} type="text" placeholder="이름/팀" />
        </label>
        <label className={styles.field}>
          <span className={styles.label}>분류</span>
          <select className={styles.input} defaultValue="고딕">
            <option>고딕</option>
            <option>명조</option>
            <option>손글씨</option>
            <option>장식</option>
          </select>
        </label>
      </div>
      <label className={styles.field}>
        <span className={styles.label}>공식 페이지 URL <span className={styles.req}>*</span></span>
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
      <button type="submit" className={styles.submit}>신청 보내기</button>
    </form>
  );
}
