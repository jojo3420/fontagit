import type { Metadata } from "next";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "문의 - FontAgit",
  description: "FontAgit에 문의하기",
};

export default async function ContactPage() {
  return (
    <main className={styles.main}>
      <div className={styles.head}>
        <h1 className={styles.h1}>문의</h1>
        <p className={styles.lead}>FontAgit에 피드백, 제안, 오류 제보를 해주세요</p>
      </div>

      <section className={styles.section}>
        <h2 className={styles.h2}>일반 문의</h2>
        <p className={styles.text}>
          기능 제안, 데이터 오류, 기타 문의는 아래 이메일로 보내주시기 바랍니다.
        </p>
        <p className={styles.textHighlight}>
          📧 {/* TODO: 문의 이메일 주소 */}
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>저작권 신고</h2>
        <p className={styles.text}>
          폰트 정보에 저작권 문제가 있다고 생각하시면 아래 이메일로 신고해주시기 바랍니다.
        </p>
        <ul className={styles.list}>
          <li>신고 시 다음 정보를 포함해주세요: 폰트명, 문제 설명, 이메일</li>
          <li>신고 후 48시간 이내에 해당 정보를 검토하고 필요시 보류 조치합니다</li>
        </ul>
        <p className={styles.textHighlight}>
          📧 {/* TODO: 저작권 신고 이메일 주소 */}
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>피드백</h2>
        <p className={styles.text}>
          FontAgit을 사용하면서 느낀 점, 개선 의견, 새로운 기능 제안 등
          어떤 피드백이든 환영합니다. 모든 의견은 서비스 개선에 소중하게 사용됩니다.
        </p>
        <p className={styles.textHighlight}>
          📧 {/* TODO: 피드백 이메일 주소 */}
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>응답 시간</h2>
        <p className={styles.text}>
          일반적으로 문의 후 2~3 영업일 이내에 회신드립니다.
          긴급한 사항은 제목에 [긴급]을 표기해주시기 바랍니다.
        </p>
      </section>
    </main>
  );
}
