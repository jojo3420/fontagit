import type { Metadata } from "next";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "개인정보처리방침 - FontAgit",
  description: "FontAgit의 개인정보처리방침, 쿠키 정책, 데이터 수집 안내",
};

export default async function PrivacyPage() {
  return (
    <main className={styles.main}>
      <div className={styles.head}>
        <h1 className={styles.h1}>개인정보처리방침</h1>
        <p className={styles.lead}>FontAgit의 개인정보 보호 방침을 안내합니다.</p>
      </div>

      <section className={styles.section}>
        <h2 className={styles.h2}>1. 개인정보 수집 항목</h2>
        <p className={styles.text}>
          FontAgit는 다음과 같은 정보를 수집합니다:
        </p>
        <ul className={styles.list}>
          <li>익명화된 클릭 집계 데이터 (폰트 조회 통계)</li>
          <li>검색 로그 (검색어, 검색 시간)</li>
          <li>신고 데이터 (사유, 상세 설명, 선택 입력한 이메일)</li>
          <li>사용자 기기 정보 (브라우저, OS, 화면 크기)</li>
        </ul>
        <p className={styles.text}>
          서비스 이용만으로 이름, 이메일, 전화번호를 요구하지 않습니다.
          다만 신고 결과 회신이 필요한 사용자는 이메일을 선택해서 입력할 수 있습니다.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>2. 쿠키 및 추적 기술</h2>
        <p className={styles.text}>
          FontAgit는 사용자 경험 개선 및 통계 분석을 위해 쿠키 및 로컬 스토리지를 사용합니다.
        </p>
        <ul className={styles.list}>
          <li>
            <strong>테마 설정:</strong> 라이트/다크 모드 선택 저장
          </li>
          <li>
            <strong>분석:</strong> Google Analytics 4(GA4)를 통한 방문자 통계 수집
          </li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>3. Google Analytics 4 (GA4)</h2>
        <p className={styles.text}>
          FontAgit는 서비스 품질 개선을 위해 Google Analytics 4를 사용합니다.
        </p>
        <ul className={styles.list}>
          <li>페이지 뷰, 사용자 행동 등 익명화된 통계를 수집합니다</li>
          <li>개인을 특정할 수 있는 데이터는 수집하지 않습니다</li>
          <li>Google의 개인정보 보호정책을 따릅니다 (https://policies.google.com/privacy)</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>4. Google AdSense</h2>
        <p className={styles.text}>
          FontAgit는 Google AdSense를 통해 광고를 표시합니다.
        </p>
        <ul className={styles.list}>
          <li>Google AdSense는 타사 쿠키를 사용하여 광고를 표시합니다</li>
          <li>사용자의 관심사에 맞춰 맞춤 광고를 제공할 수 있습니다</li>
          <li>Google의 개인정보 보호정책을 따릅니다</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>5. 데이터 보관 및 삭제</h2>
        <p className={styles.text}>
          수집된 분석 데이터는 일반적으로 14개월 동안 보관됩니다. 쿠키는 브라우저 설정을 통해 언제든 삭제할 수 있습니다.
          신고 데이터는 운영자 검토와 후속 대응에 필요한 기간 동안 보관합니다.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>6. 운영자 정보</h2>
        <p className={styles.text}>
          {/* TODO: 운영자명 */}
          <br />
          {/* TODO: 연락처 (이메일) */}
          <br />
          {/* TODO: 사업자등록번호 */}
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>7. 개인정보처리방침 시행일</h2>
        <p className={styles.text}>
          {/* TODO: 시행일 */}
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>8. 문의</h2>
        <p className={styles.text}>
          개인정보와 관련된 문의가 있으시면 <a href="/contact">문의 페이지</a>를 통해 연락주시기 바랍니다.
        </p>
      </section>
    </main>
  );
}
