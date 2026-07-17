import { beforeEach, describe, expect, it, vi } from "vitest";
import { supabaseClient } from "./client";
import { submitFontSubmission, validateFontSubmission } from "./submissions";

const { mockRpc } = vi.hoisted(() => ({
  mockRpc: vi.fn(),
}));

vi.mock("./client", () => ({
  supabaseClient: {
    rpc: mockRpc,
  },
}));

describe("validateFontSubmission", () => {
  it("필수값과 허용된 선택값을 받는다", () => {
    expect(
      validateFontSubmission({
        fontName: "  아지트 고딕  ",
        category: "고딕",
        officialUrl: "  https://example.com/font  ",
        licenseNote: "무료",
        submitterContact: "  maker@example.com  ",
      }),
    ).toBeNull();
  });

  it("폰트 이름과 공식 URL은 반드시 요구한다", () => {
    expect(
      validateFontSubmission({ fontName: "", category: "고딕", officialUrl: "https://a.com" }),
    ).toBe("폰트 이름을 입력해주세요");
    expect(
      validateFontSubmission({ fontName: "폰트", category: "고딕", officialUrl: "" }),
    ).toBe("공식 페이지 URL을 입력해주세요");
  });

  it("잘못된 분류, 라이선스, URL, 이메일과 과도한 길이를 거부한다", () => {
    const base = { fontName: "폰트", category: "고딕", officialUrl: "https://example.com" };

    expect(validateFontSubmission({ ...base, category: "임의값" })).toBe("유효한 분류를 선택해주세요");
    expect(validateFontSubmission({ ...base, licenseNote: "임의값" })).toBe("유효한 라이선스를 선택해주세요");
    expect(validateFontSubmission({ ...base, officialUrl: "javascript:alert(1)" })).toBe(
      "http 또는 https 공식 URL을 입력해주세요",
    );
    expect(validateFontSubmission({ ...base, submitterContact: "not-an-email" })).toBe(
      "유효한 이메일 주소를 입력해주세요",
    );
    expect(validateFontSubmission({ ...base, credit: "a".repeat(501) })).toBe(
      "크레딧 정보는 500자 이내로 입력해주세요",
    );
  });
});

describe("submitFontSubmission", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRpc.mockResolvedValue({ error: null });
  });

  it("입력을 정리해 제한된 RPC로 저장한다", async () => {
    await expect(
      submitFontSubmission({
        fontName: "  아지트 고딕  ",
        category: "고딕",
        maker: "  제작자  ",
        officialUrl: "  https://example.com/font  ",
        licenseNote: "무료",
        submitterContact: "  maker@example.com  ",
        credit: "  만든이  ",
      }),
    ).resolves.toBe(true);

    expect(supabaseClient.rpc).toHaveBeenCalledWith("submit_font_submission", {
      p_font_name: "아지트 고딕",
      p_category: "고딕",
      p_maker: "제작자",
      p_official_url: "https://example.com/font",
      p_license_note: "무료",
      p_submitter_contact: "maker@example.com",
      p_credit: "만든이",
    });
  });

  it("DB 오류는 사용자용 실패 결과로 바꾼다", async () => {
    mockRpc.mockResolvedValue({ error: { message: "rate limited" } });

    await expect(
      submitFontSubmission({
        fontName: "아지트 고딕",
        category: "고딕",
        officialUrl: "https://example.com/font",
      }),
    ).resolves.toBe(false);
  });
});
