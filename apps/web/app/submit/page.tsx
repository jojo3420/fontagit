import { Metadata } from "next";
import { SubmitForm } from "@/components/SubmitForm";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "폰트 등록 신청 - FontAgit",
};

export default function SubmitPage() {
  return (
    <main className={styles.main}>
      <SubmitForm />
    </main>
  );
}
