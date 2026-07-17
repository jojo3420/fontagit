import { supabaseClient } from "./client";

const FONT_CATEGORIES = ["고딕", "명조", "손글씨", "장식"] as const;
const LICENSE_NOTES = ["무료", "유료", "조건부"] as const;

type FontCategory = (typeof FONT_CATEGORIES)[number];
type LicenseNote = (typeof LICENSE_NOTES)[number];

interface SubmitFontSubmissionParams {
  fontName: string;
  category: string;
  officialUrl: string;
  maker?: string;
  licenseNote?: string;
  submitterContact?: string;
  credit?: string;
}

interface NormalizedSubmission {
  fontName: string;
  category: string;
  officialUrl: string;
  maker: string | null;
  licenseNote: string | null;
  submitterContact: string | null;
  credit: string | null;
}

function normalizeSubmission(params: SubmitFontSubmissionParams): NormalizedSubmission {
  return {
    fontName: params.fontName.trim(),
    category: params.category.trim(),
    officialUrl: params.officialUrl.trim(),
    maker: params.maker?.trim() || null,
    licenseNote: params.licenseNote?.trim() || null,
    submitterContact: params.submitterContact?.trim() || null,
    credit: params.credit?.trim() || null,
  };
}

export function validateFontSubmission(params: SubmitFontSubmissionParams): string | null {
  const submission = normalizeSubmission(params);

  if (!submission.fontName) {
    return "폰트 이름을 입력해주세요";
  }
  if (submission.fontName.length > 100) {
    return "폰트 이름은 100자 이내로 입력해주세요";
  }
  if (!FONT_CATEGORIES.includes(submission.category as FontCategory)) {
    return "유효한 분류를 선택해주세요";
  }
  if (submission.maker && submission.maker.length > 100) {
    return "제작자 이름은 100자 이내로 입력해주세요";
  }
  if (!submission.officialUrl) {
    return "공식 페이지 URL을 입력해주세요";
  }
  if (submission.officialUrl.length > 500) {
    return "공식 페이지 URL은 500자 이내로 입력해주세요";
  }
  if (!isValidHttpUrl(submission.officialUrl)) {
    return "http 또는 https 공식 URL을 입력해주세요";
  }
  if (
    submission.licenseNote &&
    !LICENSE_NOTES.includes(submission.licenseNote as LicenseNote)
  ) {
    return "유효한 라이선스를 선택해주세요";
  }
  if (
    submission.submitterContact &&
    (submission.submitterContact.length > 100 || !isValidEmail(submission.submitterContact))
  ) {
    return "유효한 이메일 주소를 입력해주세요";
  }
  if (submission.credit && submission.credit.length > 500) {
    return "크레딧 정보는 500자 이내로 입력해주세요";
  }

  return null;
}

/** 입력 검증과 속도 제한이 적용된 DB 함수로 익명 신청을 제출한다. */
export async function submitFontSubmission(
  params: SubmitFontSubmissionParams,
): Promise<boolean> {
  const validationError = validateFontSubmission(params);
  if (validationError) {
    throw new Error(validationError);
  }

  const submission = normalizeSubmission(params);

  try {
    const { error } = await supabaseClient.rpc("submit_font_submission", {
      p_font_name: submission.fontName,
      p_category: submission.category,
      p_maker: submission.maker,
      p_official_url: submission.officialUrl,
      p_license_note: submission.licenseNote,
      p_submitter_contact: submission.submitterContact,
      p_credit: submission.credit,
    });

    if (error) {
      throw error;
    }

    return true;
  } catch {
    return false;
  }
}

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function isValidHttpUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return (parsed.protocol === "http:" || parsed.protocol === "https:") && Boolean(parsed.hostname);
  } catch {
    return false;
  }
}
