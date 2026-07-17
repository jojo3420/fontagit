import { supabaseClient } from './client';

interface SubmitReportParams {
  fontId: string | null;
  reason: string;
  detail?: string;
  contact?: string;
}

/**
 * 폰트 신고를 익명으로 제출
 * best-effort: 신고 실패는 조용히 무시(UI 영향 없음)
 * @throws 사용자 입력 검증 실패 시 Error 던짐
 */
export async function submitFontReport(
  params: SubmitReportParams
): Promise<boolean> {
  const { fontId, reason, detail, contact } = params;

  // 사용자 입력 검증
  if (!reason || reason.trim().length === 0) {
    throw new Error('신고 사유를 선택해주세요');
  }

  if (detail && detail.length > 1000) {
    throw new Error('상세 설명은 1000자 이내로 입력해주세요');
  }

  if (contact && !isValidEmail(contact)) {
    throw new Error('유효한 이메일 주소를 입력해주세요');
  }

  try {
    const { error } = await supabaseClient
      .from('font_reports')
      .insert({
        font_id: fontId,
        reason: reason.trim(),
        detail: detail ? detail.trim() : null,
        contact: contact ? contact.trim() : null,
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
