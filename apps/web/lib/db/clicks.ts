import { supabaseClient } from "./client";

/**
 * 공식 링크 이동 클릭 기록 (fire-and-forget, 스펙 슬라이스3).
 * 실패/지연이 페이지 이동을 막으면 안 되므로 아무것도 반환하지 않고 오류를 삼킨다.
 */
export function recordClick(slug: string): void {
  if (!slug) {
    return;
  }

  void Promise.resolve(supabaseClient.rpc("record_click", { p_slug: slug }))
    .then(({ error }) => {
      if (error) {
        console.error("[clicks] record_click failed:", error);
      }
    })
    .catch((err: unknown) => {
      console.error("[clicks] record_click failed:", err);
    });
}
