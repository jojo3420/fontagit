import type { Metadata } from "next";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "면책 조항 - FontAgit",
  description: "FontAgit의 법적 면책 조항 및 책임 제한",
};

export default async function DisclaimerPage() {
  return (
    <main className={styles.main}>
      <div className={styles.head}>
        <h1 className={styles.h1}>면책 조항</h1>
        <p className={styles.lead}>FontAgit 서비스 이용 시 법적 책임에 관한 안내</p>
      </div>

      <section className={styles.section}>
        <h2 className={styles.h2}>1. 서비스 현황 제공</h2>
        <p className={styles.text}>
          FontAgit는 본 서비스를 "있는 그대로(as-is)" 제공합니다.
          <strong>서비스가 안전함, 무결함, 또는 문제없음을 보증하지 않습니다.</strong>
          데이터의 정확성, 완전성, 최신성에 대해 어떠한 보장도 하지 않습니다.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>2. 라이선스 정보 안내</h2>
        <p className={styles.text}>
          FontAgit에 표시된 라이선스 정보는 <strong>확인일 기준 참고 정보</strong>입니다.
        </p>
        <ul className={styles.list}>
          <li>라이선스 정보는 변경될 수 있습니다</li>
          <li>폰트 사용 전 반드시 각 폰트의 공식 페이지에서 라이선스를 다시 확인하세요</li>
          <li>
            <strong>최종 라이선스 확인의 책임은 사용자에게 있습니다</strong>
          </li>
          <li>라이선스 미확인으로 인한 법적 문제는 FontAgit가 책임지지 않습니다</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>3. 제3자 콘텐츠</h2>
        <p className={styles.text}>
          FontAgit는 제3자 폰트 제작사의 정보를 참고용으로 제공합니다.
        </p>
        <ul className={styles.list}>
          <li>폰트 파일, 설명, 이미지 등은 각 제작사의 저작물입니다</li>
          <li>FontAgit는 제3자 콘텐츠의 정확성을 보장하지 않습니다</li>
          <li>외부 사이트 링크로 인한 손실은 FontAgit가 책임지지 않습니다</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>4. 저작권 신고</h2>
        <p className={styles.text}>
          FontAgit에 저작권 위반 콘텐츠가 있다고 생각하시면 <a href="/contact">문의 페이지</a>를 통해 신고하세요.
        </p>
        <ul className={styles.list}>
          <li>신고 시 폰트명, 문제 설명, 신고자 이메일을 포함해주세요</li>
          <li>신고 후 <strong>48시간 이내</strong>에 검토하고 필요시 보류 조치합니다</li>
          <li>신고자의 정보는 해당 저작권자와만 공유됩니다</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>5. 서비스 중단</h2>
        <p className={styles.text}>
          FontAgit는 사전 공지 없이 서비스를 중단하거나 기능을 변경할 수 있습니다.
          이로 인한 손실은 FontAgit가 책임지지 않습니다.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>6. 책임 제한</h2>
        <p className={styles.text}>
          FontAgit 이용 중 발생한 다음과 같은 손실에 대해서는 책임을 지지 않습니다:
        </p>
        <ul className={styles.list}>
          <li>데이터 손실, 손상, 유실</li>
          <li>서비스 이용 불가로 인한 손실</li>
          <li>제3자 콘텐츠 사용으로 인한 손실</li>
          <li>라이선스 미확인으로 인한 법적 분쟁</li>
          <li>기타 간접적, 부수적, 결과적 손실</li>
        </ul>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>7. 변경 및 업데이트</h2>
        <p className={styles.text}>
          본 면책 조항은 언제든 변경될 수 있습니다. 변경사항은 공지 없이 적용될 수 있으므로
          정기적으로 확인하시기 바랍니다.
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>문의</h2>
        <p className={styles.text}>
          본 면책 조항에 대한 문의는 <a href="/contact">문의 페이지</a>를 통해 주시기 바랍니다.
        </p>
      </section>
    </main>
  );
}
