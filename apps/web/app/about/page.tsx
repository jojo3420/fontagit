import type { Metadata } from "next";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "소개 - FontAgit",
  description: "FontAgit는 국내외 무료-유료 폰트를 검색하고 비교하는 폰트 아지트입니다",
  alternates: { canonical: "/about/" },
};

export default async function AboutPage() {
  return (
    <main className={styles.main}>
      <div className={styles.head}>
        <h1 className={styles.h1}>FontAgit 소개</h1>
        <p className={styles.lead}>국내외 무료-유료 폰트를 한눈에 보는 폰트 아지트</p>
      </div>

      <section className={styles.section}>
        <h2 className={styles.h2}>FontAgit란?</h2>
        <p className={styles.text}>
          FontAgit는 국내외 폰트를 효율적으로 검색하고 비교할 수 있는 서비스입니다.
          무료 폰트부터 유료 폰트까지 다양한 서체를 한 곳에서 찾아볼 수 있습니다.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>주요 기능</h2>
        <ul className={styles.list}>
          <li>
            <strong>폰트 검색:</strong> 글꼴명, 특징, 제작사 등으로 폰트를 검색합니다
          </li>
          <li>
            <strong>폰트 비교:</strong> 여러 폰트를 나란히 비교하여 특징을 파악합니다
          </li>
          <li>
            <strong>라이선스 정보:</strong> 각 폰트의 라이선스를 확인하고 공식 링크로 이동합니다
          </li>
          <li>
            <strong>트렌드:</strong> 주간 인기 폰트와 최신 등록 폰트를 확인합니다
          </li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>데이터 정책</h2>
        <ul className={styles.list}>
          <li>
            <strong>파일 미호스팅:</strong> FontAgit는 폰트 파일을 호스팅하지 않습니다
          </li>
          <li>
            <strong>공식 링크 원칙:</strong> 모든 폰트는 제작사 공식 페이지의 링크로 제공됩니다
          </li>
          <li>
            <strong>정보 확인:</strong> 폰트의 라이선스, 가격, 지원 언어 등을 공식 사이트에서 다시 확인하세요
          </li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>어디에 쓸까?</h2>
        <p className={styles.text}>
          FontAgit는 디자이너, 개발자, 기획자 등 폰트를 자주 사용하는 사람들을 위해
          만들어졌습니다. 원하는 특징의 폰트를 빠르게 찾고, 여러 폰트를 비교하며,
          최종적으로 공식 페이지에서 라이선스를 확인하고 다운로드할 수 있습니다.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>건의 및 오류 제보</h2>
        <p className={styles.text}>
          데이터 오류가 있거나 기능 제안이 있으시면 <a href="/contact">문의 페이지</a>를 통해
          알려주시기 바랍니다. 사용자의 피드백은 FontAgit를 더 나은 서비스로 만드는 데 큰 도움이 됩니다.
        </p>
      </section>
    </main>
  );
}
