import type {
  AuditPermission, Commercial, LicenseWebfont, LicenseRedistribution,
} from "@/types/font";

/** 라이선스 아이콘 상태: ok(가능) / cond(조건부) / no(불가) */
export type LicenseState = "ok" | "cond" | "no" | "unknown";

/** 상업적 사용 한국어 라벨 */
export function commercialLabel(c: Commercial): string {
  return { yes: "가능", conditional: "구매 시", no: "불가" }[c];
}

/** 웹폰트 한국어 라벨 */
export function webfontLabel(w: LicenseWebfont): string {
  return { included: "포함", separate: "별도 구매", no: "불가" }[w];
}

/** 재배포 한국어 라벨 */
export function redistributionLabel(r: LicenseRedistribution): string {
  return { yes: "가능", no: "불가" }[r];
}

export function commercialState(c: Commercial): LicenseState {
  return { yes: "ok", conditional: "cond", no: "no" }[c] as LicenseState;
}

export function webfontState(w: LicenseWebfont): LicenseState {
  return { included: "ok", separate: "cond", no: "no" }[w] as LicenseState;
}

export function redistributionState(r: LicenseRedistribution): LicenseState {
  return { yes: "ok", no: "no" }[r] as LicenseState;
}

export function auditPermissionLabel(permission: AuditPermission): string {
  return {
    allowed: "허용",
    conditional: "조건부",
    denied: "금지",
    unknown: "확인 필요",
  }[permission];
}

export function auditPermissionState(permission: AuditPermission): LicenseState {
  return {
    allowed: "ok",
    conditional: "cond",
    denied: "no",
    unknown: "unknown",
  }[permission] as LicenseState;
}

export function attributionLabel(
  value: "required" | "recommended" | "not_required" | "unknown",
): string {
  return {
    required: "필수",
    recommended: "권장",
    not_required: "불필요",
    unknown: "확인 필요",
  }[value];
}

export function attributionState(
  value: "required" | "recommended" | "not_required" | "unknown",
): LicenseState {
  return value === "unknown" ? "unknown" : value === "required" ? "cond" : "ok";
}

/** officialUrl에서 판매처 호스트만 파생. www. 제거. 실패 시 null */
export function deriveSellerHost(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return host.replace(/^www\./, "") || null;
  } catch {
    return null;
  }
}
