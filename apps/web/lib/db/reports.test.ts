import { beforeEach, describe, expect, it, vi } from "vitest";
import { submitFontReport } from "./reports";
import { supabaseClient } from "./client";

const { mockRpc } = vi.hoisted(() => ({
  mockRpc: vi.fn(),
}));

vi.mock("./client", () => ({
  supabaseClient: {
    rpc: mockRpc,
  },
}));

describe("submitFontReport", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRpc.mockResolvedValue({ error: null });
  });

  it("허용된 신고 내용을 정리해 저장한다", async () => {
    await expect(
      submitFontReport({
        fontId: "font-id",
        reason: "copyright",
        detail: "  공식 배포처가 아닙니다  ",
        contact: "  reporter@example.com  ",
      })
    ).resolves.toBe(true);

    expect(supabaseClient.rpc).toHaveBeenCalledWith(
      "submit_font_report",
      {
        p_font_id: "font-id",
        p_reason: "copyright",
        p_detail: "공식 배포처가 아닙니다",
        p_contact: "reporter@example.com",
      }
    );
  });

  it("허용되지 않은 사유와 과도한 입력을 거부한다", async () => {
    await expect(
      submitFontReport({ fontId: null, reason: "arbitrary" })
    ).rejects.toThrow("유효한 신고 사유");
    await expect(
      submitFontReport({
        fontId: null,
        reason: "other",
        detail: "a".repeat(1001),
      })
    ).rejects.toThrow("1000자");
    await expect(
      submitFontReport({
        fontId: null,
        reason: "other",
        contact: "invalid-email",
      })
    ).rejects.toThrow("유효한 이메일");
  });

  it("DB 오류는 사용자용 실패 결과로 바꾼다", async () => {
    mockRpc.mockResolvedValue({ error: { message: "permission denied" } });

    await expect(
      submitFontReport({ fontId: null, reason: "other" })
    ).resolves.toBe(false);
  });
});
