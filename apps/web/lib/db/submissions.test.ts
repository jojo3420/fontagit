import { describe, it, expect } from "vitest";
import { validateFontSubmission } from "./submissions";

describe("validateFontSubmission", () => {
  describe("필수 검증", () => {
    it("폰트 이름 미입력 시 에러 메시지 반환", () => {
      const error = validateFontSubmission({ fontName: "" });
      expect(error).toBe("폰트 이름을 입력해주세요");
    });

    it("폰트 이름이 공백만 입력 시 에러 메시지 반환", () => {
      const error = validateFontSubmission({ fontName: "   " });
      expect(error).toBe("폰트 이름을 입력해주세요");
    });

    it("폰트 이름이 100자 초과 시 에러 메시지 반환", () => {
      const longName = "a".repeat(101);
      const error = validateFontSubmission({ fontName: longName });
      expect(error).toBe("폰트 이름은 100자 이내로 입력해주세요");
    });
  });

  describe("선택 필드 검증", () => {
    it("제작자 이름이 100자 초과 시 에러 메시지 반환", () => {
      const longMaker = "a".repeat(101);
      const error = validateFontSubmission({
        fontName: "Test Font",
        maker: longMaker,
      });
      expect(error).toBe("제작자 이름은 100자 이내로 입력해주세요");
    });

    it("유효하지 않은 URL 형식 시 에러 메시지 반환", () => {
      const error = validateFontSubmission({
        fontName: "Test Font",
        officialUrl: "not-a-url",
      });
      expect(error).toBe("유효한 URL을 입력해주세요");
    });

    it("URL이 500자 초과 시 에러 메시지 반환", () => {
      const longUrl = "https://example.com/" + "a".repeat(481);
      const error = validateFontSubmission({
        fontName: "Test Font",
        officialUrl: longUrl,
      });
      expect(error).toBe("공식 페이지 URL은 500자 이내로 입력해주세요");
    });

    it("유효하지 않은 이메일 형식 시 에러 메시지 반환", () => {
      const error = validateFontSubmission({
        fontName: "Test Font",
        submitterContact: "not-an-email",
      });
      expect(error).toBe("유효한 이메일 주소를 입력해주세요");
    });

    it("연락처가 100자 초과 시 에러 메시지 반환", () => {
      const longContact = "a".repeat(101) + "@example.com";
      const error = validateFontSubmission({
        fontName: "Test Font",
        submitterContact: longContact,
      });
      expect(error).toBe("연락처는 100자 이내로 입력해주세요");
    });

    it("크레딧이 500자 초과 시 에러 메시지 반환", () => {
      const longCredit = "a".repeat(501);
      const error = validateFontSubmission({
        fontName: "Test Font",
        credit: longCredit,
      });
      expect(error).toBe("크레딧 정보는 500자 이내로 입력해주세요");
    });

    it("라이선스 정보가 100자 초과 시 에러 메시지 반환", () => {
      const longLicense = "a".repeat(101);
      const error = validateFontSubmission({
        fontName: "Test Font",
        licenseNote: longLicense,
      });
      expect(error).toBe("라이선스 정보는 100자 이내로 입력해주세요");
    });
  });

  describe("성공 케이스", () => {
    it("필수 필드만 입력 시 null 반환", () => {
      const error = validateFontSubmission({ fontName: "Test Font" });
      expect(error).toBeNull();
    });

    it("모든 필드 유효하게 입력 시 null 반환", () => {
      const error = validateFontSubmission({
        fontName: "Test Font",
        maker: "Test Maker",
        officialUrl: "https://example.com",
        licenseNote: "무료",
        submitterContact: "test@example.com",
        credit: "Test Designer",
      });
      expect(error).toBeNull();
    });

    it("선택 필드 비워도 null 반환", () => {
      const error = validateFontSubmission({
        fontName: "Test Font",
        maker: undefined,
        officialUrl: undefined,
        licenseNote: undefined,
        submitterContact: undefined,
        credit: undefined,
      });
      expect(error).toBeNull();
    });

    it("최대 길이 정확히 입력 시 null 반환", () => {
      const error = validateFontSubmission({
        fontName: "a".repeat(100),
        maker: "b".repeat(100),
        officialUrl: "https://example.com/" + "c".repeat(470),
        submitterContact: "d".repeat(90) + "@test.com",
        credit: "e".repeat(500),
      });
      expect(error).toBeNull();
    });
  });

  describe("URL 유효성", () => {
    it("유효한 http URL 허용", () => {
      const error = validateFontSubmission({
        fontName: "Test",
        officialUrl: "http://example.com",
      });
      expect(error).toBeNull();
    });

    it("유효한 https URL 허용", () => {
      const error = validateFontSubmission({
        fontName: "Test",
        officialUrl: "https://example.com/path",
      });
      expect(error).toBeNull();
    });

    it("프로토콜 없는 URL 거절", () => {
      const error = validateFontSubmission({
        fontName: "Test",
        officialUrl: "example.com",
      });
      expect(error).toBe("유효한 URL을 입력해주세요");
    });
  });

  describe("이메일 유효성", () => {
    it("유효한 이메일 허용", () => {
      const error = validateFontSubmission({
        fontName: "Test",
        submitterContact: "test@example.com",
      });
      expect(error).toBeNull();
    });

    it("특수문자 포함 이메일 허용", () => {
      const error = validateFontSubmission({
        fontName: "Test",
        submitterContact: "test+tag@example.co.uk",
      });
      expect(error).toBeNull();
    });

    it("@ 없는 이메일 거절", () => {
      const error = validateFontSubmission({
        fontName: "Test",
        submitterContact: "testexample.com",
      });
      expect(error).toBe("유효한 이메일 주소를 입력해주세요");
    });

    it("공백 포함 이메일 거절", () => {
      const error = validateFontSubmission({
        fontName: "Test",
        submitterContact: "test @example.com",
      });
      expect(error).toBe("유효한 이메일 주소를 입력해주세요");
    });
  });
});
