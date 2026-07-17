"use client";
import { useState } from "react";
import { FilterChip } from "./FilterChip";
import { submitFontSubmission } from "@/lib/db/submissions";
import styles from "./SubmitForm.module.css";

type FormState = "idle" | "loading" | "success" | "error";

export function SubmitForm() {
  const [formState, setFormState] = useState<FormState>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const [fontName, setFontName] = useState("");
  const [maker, setMaker] = useState("");
  const [category, setCategory] = useState("고딕");
  const [officialUrl, setOfficialUrl] = useState("");
  const [licenseNote, setLicenseNote] = useState("");
  const [submitterContact, setSubmitterContact] = useState("");
  const [credit, setCredit] = useState("");

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormState("loading");
    setErrorMessage("");

    try {
      const success = await submitFontSubmission({
        fontName,
        category,
        maker,
        officialUrl,
        licenseNote,
        submitterContact,
        credit,
      });

      if (success) {
        setFormState("success");
        setFontName("");
        setMaker("");
        setCategory("고딕");
        setOfficialUrl("");
        setLicenseNote("");
        setSubmitterContact("");
        setCredit("");

        setTimeout(() => setFormState("idle"), 3000);
      } else {
        setFormState("error");
        setErrorMessage("신청 전송에 실패했습니다. 잠시 후 다시 시도해주세요.");
      }
    } catch (err) {
      setFormState("error");
      setErrorMessage(
        err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다."
      );
    }
  }

  return (
    <>
      <form className={styles.form} onSubmit={handleSubmit}>
        <label className={styles.field}>
          <span className={styles.label}>폰트 이름 <span className={styles.req}>*</span></span>
          <input
            className={styles.input}
            type="text"
            placeholder="예: 아지트 고딕"
            value={fontName}
            onChange={(e) => setFontName(e.target.value)}
            maxLength={100}
            required
            disabled={formState === "loading"}
          />
        </label>
        <div className={styles.row}>
          <label className={styles.field}>
            <span className={styles.label}>제작자</span>
            <input
              className={styles.input}
              type="text"
              placeholder="이름/팀"
              value={maker}
              onChange={(e) => setMaker(e.target.value)}
              maxLength={100}
              disabled={formState === "loading"}
            />
          </label>
          <label className={styles.field}>
            <span className={styles.label}>분류</span>
            <select
              className={styles.input}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              disabled={formState === "loading"}
            >
              <option>고딕</option>
              <option>명조</option>
              <option>손글씨</option>
              <option>장식</option>
            </select>
          </label>
        </div>
        <label className={styles.field}>
          <span className={styles.label}>공식 페이지 URL <span className={styles.req}>*</span></span>
          <input
            className={styles.input}
            type="url"
            placeholder="https://"
            value={officialUrl}
            onChange={(e) => setOfficialUrl(e.target.value)}
            maxLength={500}
            required
            disabled={formState === "loading"}
          />
        </label>
        <div className={styles.field}>
          <span className={styles.label}>라이선스</span>
          <div className={styles.chips}>
            <FilterChip
              active={licenseNote === "무료"}
              onClick={() => setLicenseNote("무료")}
            >
              무료
            </FilterChip>
            <FilterChip
              active={licenseNote === "유료"}
              onClick={() => setLicenseNote("유료")}
            >
              유료
            </FilterChip>
            <FilterChip
              active={licenseNote === "조건부"}
              onClick={() => setLicenseNote("조건부")}
            >
              조건부
            </FilterChip>
          </div>
        </div>
        <label className={styles.field}>
          <span className={styles.label}>신청자 연락처 (이메일)</span>
          <input
            className={styles.input}
            type="email"
            placeholder="your@email.com"
            value={submitterContact}
            onChange={(e) => setSubmitterContact(e.target.value)}
            maxLength={100}
            disabled={formState === "loading"}
          />
        </label>
        <label className={styles.field}>
          <span className={styles.label}>크레딧 (제작자 표기)</span>
          <input
            className={styles.input}
            type="text"
            placeholder="예: 디자이너 이름 © 2024"
            value={credit}
            onChange={(e) => setCredit(e.target.value)}
            maxLength={500}
            disabled={formState === "loading"}
          />
        </label>
        <button
          type="submit"
          className={styles.submit}
          disabled={formState === "loading" || formState === "success"}
        >
          {formState === "loading" ? "전송 중..." : "신청 보내기"}
        </button>
      </form>

      {formState === "success" && (
        <div className={styles.message} data-type="success">
          신청이 접수되었습니다. 검토 후 반영됩니다.
        </div>
      )}

      {formState === "error" && (
        <div className={styles.message} data-type="error">
          {errorMessage}
        </div>
      )}
    </>
  );
}
