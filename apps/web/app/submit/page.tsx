import { SubmitForm } from "@/components/SubmitForm";
import styles from "./page.module.css";

export const metadata = { title: "폰트 등록 신청 - FontAgit" };

export default function SubmitPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.title}>폰트 등록 신청</h1>
      <p className={styles.lead}>만드신 폰트를 아지트에 소개해 주세요. 검토 후 등록됩니다.</p>
      <SubmitForm />
    </main>
  );
}
