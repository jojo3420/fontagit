import { Button } from "@/components/Button";
import styles from "./not-found.module.css";

export default function NotFound() {
  return (
    <main className={styles.main}>
      <div className={styles.container}>
        <h1 className={styles.h1}>404</h1>
        <p className={styles.message}>길을 잘못 드셨어요. 아지트 입구로 모실게요.</p>
        <Button href="/">홈으로 돌아가기</Button>
      </div>
    </main>
  );
}
