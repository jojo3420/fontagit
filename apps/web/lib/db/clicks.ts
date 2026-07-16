import { supabaseClient } from "./client";

export function recordClick(slug: string): void {
  if (!slug) return;

  supabaseClient
    .rpc("record_click", { p_slug: slug })
    .then(() => {
      // fire-and-forget: 성공해도 아무것도 하지 않음
    })
    .catch(() => {
      // 모든 오류(RPC 실패, 네트워크 예외)를 삼킨다
    });
}
