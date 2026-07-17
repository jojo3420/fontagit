import { supabaseClient } from './client';

interface SubmitReportParams {
  fontId: string | null;
  reason: string;
  detail?: string;
  contact?: string;
}

const REPORT_REASONS = [
  'copyright',
  'misinformation',
  'inappropriate',
  'other',
] as const;

/**
 * 폰트 신고를 익명으로 제출
 * best-effort: 신고 실패는 조용히 무시(UI 영향 없음)
 * @throws 사용자 입력 검증 실패 시 Error 던짐
 */
export async function submitFontReport(
  params: SubmitReportParams
): Promise<boolean> {
  const { fontId, reason, detail, contact } = params;
  const normalizedReason = reason.trim();
  const normalizedDetail = detail?.trim() || null;
  const normalizedContact = contact?.trim() || null;

  if (
    !REPORT_REASONS.includes(
      normalizedReason as (typeof REPORT_REASONS)[number]
    )
  ) {
    throw new Error('유효한 신고 사유를 선택해주세요');
  }

  if (normalizedDetail && normalizedDetail.length > 1000) {
    throw new Error('상세 설명은 1000자 이내로 입력해주세요');
  }

  if (
    normalizedContact &&
    (normalizedContact.length > 254 || !isValidEmail(normalizedContact))
  ) {
    throw new Error('유효한 이메일 주소를 입력해주세요');
  }

  try {
    const { error } = await supabaseClient.rpc('submit_font_report', {
      p_font_id: fontId,
      p_reason: normalizedReason,
      p_detail: normalizedDetail,
      p_contact: normalizedContact,
    });

    if (error) {
      throw error;
    }

    return true;
  } catch {
    // 신고 제출 실패는 조용히 무시
    return false;
  }
}

function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}
