import { supabaseClient } from './client';

interface SubmitFontSubmissionParams {
  fontName: string;
  maker?: string;
  officialUrl?: string;
  licenseNote?: string;
  submitterContact?: string;
  credit?: string;
}

export function validateFontSubmission(
  params: SubmitFontSubmissionParams
): string | null {
  const { fontName, maker, officialUrl, licenseNote, submitterContact, credit } = params;

  if (!fontName || fontName.trim().length === 0) {
    return '폰트 이름을 입력해주세요';
  }

  if (fontName.trim().length > 100) {
    return '폰트 이름은 100자 이내로 입력해주세요';
  }

  if (maker && maker.length > 100) {
    return '제작자 이름은 100자 이내로 입력해주세요';
  }

  if (officialUrl && officialUrl.length > 500) {
    return '공식 페이지 URL은 500자 이내로 입력해주세요';
  }

  if (officialUrl && !isValidUrl(officialUrl)) {
    return '유효한 URL을 입력해주세요';
  }

  if (licenseNote && licenseNote.length > 100) {
    return '라이선스 정보는 100자 이내로 입력해주세요';
  }

  if (submitterContact && submitterContact.length > 100) {
    return '연락처는 100자 이내로 입력해주세요';
  }

  if (submitterContact && !isValidEmail(submitterContact)) {
    return '유효한 이메일 주소를 입력해주세요';
  }

  if (credit && credit.length > 500) {
    return '크레딧 정보는 500자 이내로 입력해주세요';
  }

  return null;
}

/**
 * 폰트 등록 신청을 익명으로 제출
 * best-effort: 신청 실패는 조용히 무시(UI 영향 없음)
 * @throws 사용자 입력 검증 실패 시 Error 던짐
 */
export async function submitFontSubmission(
  params: SubmitFontSubmissionParams
): Promise<boolean> {
  const { fontName, maker, officialUrl, licenseNote, submitterContact, credit } = params;

  const validationError = validateFontSubmission(params);
  if (validationError) {
    throw new Error(validationError);
  }

  try {
    const { error } = await supabaseClient.from('font_submissions').insert({
      font_name: fontName.trim(),
      maker: maker ? maker.trim() : null,
      official_url: officialUrl ? officialUrl.trim() : null,
      license_note: licenseNote ? licenseNote.trim() : null,
      submitter_contact: submitterContact ? submitterContact.trim() : null,
      credit: credit ? credit.trim() : null,
    });

    if (error) {
      throw error;
    }

    return true;
  } catch {
    // 신청 제출 실패는 조용히 무시
    return false;
  }
}

function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

function isValidUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}
