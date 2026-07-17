"use client";

import { useState } from "react";
import { submitFontReport } from "@/lib/db/reports";
import styles from "./report-form.module.css";

interface ReportFormProps {
  fontId: string;
  fontName: string;
}

type ReportReason = "copyright" | "misinformation" | "inappropriate" | "other";

export function ReportForm({ fontId, fontName }: ReportFormProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedReason, setSelectedReason] = useState<ReportReason | "">("");
  const [detail, setDetail] = useState("");
  const [contact, setContact] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<"idle" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage("");

    try {
      const success = await submitFontReport({
        fontId,
        reason: selectedReason as string,
        detail: detail || undefined,
        contact: contact || undefined,
      });

      if (success) {
        setSubmitStatus("success");
        setSelectedReason("");
        setDetail("");
        setContact("");
        setTimeout(() => {
          setIsOpen(false);
          setSubmitStatus("idle");
        }, 2000);
      } else {
        setSubmitStatus("error");
        setErrorMessage("신고 제출에 실패했습니다. 잠시 후 다시 시도해주세요.");
      }
    } catch (error) {
      setSubmitStatus("error");
      if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("알 수 없는 오류가 발생했습니다.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const isFormValid = selectedReason !== "";

  if (!isOpen) {
    return (
      <div className={styles.triggerWrapper}>
        <button onClick={() => setIsOpen(true)} className={styles.triggerButton}>
          신고
        </button>
      </div>
    );
  }

  return (
    <div className={styles.overlay} onClick={() => !isSubmitting && setIsOpen(false)}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>{fontName} 신고</h2>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            disabled={isSubmitting}
            className={styles.closeButton}
            aria-label="닫기"
          >
            ×
          </button>
        </div>

        {submitStatus === "success" ? (
          <div className={styles.successMessage}>
            <p>신고가 접수되었습니다.</p>
            <p className={styles.successDetail}>운영자가 48시간 내 검토하겠습니다.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.form}>
            <div className={styles.formGroup}>
              <label htmlFor="reason" className={styles.label}>
                신고 사유 <span className={styles.required}>*</span>
              </label>
              <select
                id="reason"
                value={selectedReason}
                onChange={(e) => {
                  setSelectedReason(e.target.value as ReportReason);
                  setSubmitStatus("idle");
                }}
                disabled={isSubmitting}
                className={styles.select}
              >
                <option value="">선택해주세요</option>
                <option value="copyright">저작권 침해</option>
                <option value="misinformation">잘못된 정보</option>
                <option value="inappropriate">부적절한 콘텐츠</option>
                <option value="other">기타</option>
              </select>
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="detail" className={styles.label}>
                상세 설명 <span className={styles.optional}>(선택)</span>
              </label>
              <textarea
                id="detail"
                value={detail}
                onChange={(e) => {
                  setDetail(e.target.value);
                  setSubmitStatus("idle");
                }}
                disabled={isSubmitting}
                maxLength={1000}
                placeholder="신고 내용을 입력해주세요 (최대 1000자)"
                className={styles.textarea}
              />
              <div className={styles.charCount}>
                {detail.length}/1000
              </div>
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="contact" className={styles.label}>
                연락처 <span className={styles.optional}>(선택)</span>
              </label>
              <input
                id="contact"
                type="email"
                value={contact}
                onChange={(e) => {
                  setContact(e.target.value);
                  setSubmitStatus("idle");
                }}
                disabled={isSubmitting}
                placeholder="example@email.com"
                className={styles.input}
              />
            </div>

            {submitStatus === "error" && (
              <div className={styles.errorMessage}>
                {errorMessage}
              </div>
            )}

            <div className={styles.footer}>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                disabled={isSubmitting}
                className={styles.cancelButton}
              >
                취소
              </button>
              <button
                type="submit"
                disabled={!isFormValid || isSubmitting}
                className={styles.submitButton}
              >
                {isSubmitting ? "제출 중..." : "신고"}
              </button>
            </div>

            <p className={styles.info}>
              ℹ️ 신고 후 운영자가 48시간 내에 검토하고 조치하겠습니다.
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
