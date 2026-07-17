import { SubmitForm } from "@/components/SubmitForm";
import styles from "./page.module.css";

export const metadata = { title: "폰트 등록 신청 - FontAgit" };

export default function SubmitPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.title}>폰트 등록 신청</h1>
      <p className={styles.lead}>만드신 폰트를 아지트에 소개해 주세요. 검토 후 등록됩니다.</p>
      <div className={styles.info}>
        <p><strong>필수 항목:</strong> 폰트 이름, 공식 페이지 URL</p>
        <p>기타 정보는 폰트 프로필 완성도를 높여줍니다. 특히 크레딧 정보는 제작자 표기에 그대로 반영됩니다.</p>
      </div>
      <SubmitForm />
    </main>
  );
}
