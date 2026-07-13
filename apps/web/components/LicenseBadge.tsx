import type { Commercial } from "@/types/font";
import cls from "./LicenseBadge.module.css";

interface LicenseBadgeProps {
  commercial: Commercial;
}

const COMMERCIAL_MAP = {
  yes: { cls: "yes", label: "가능", icon: "✓" },
  conditional: { cls: "conditional", label: "조건부", icon: "⚡" },
  no: { cls: "no", label: "불가", icon: "✕" },
} as const;

export function LicenseBadge({ commercial }: LicenseBadgeProps) {
  const config = COMMERCIAL_MAP[commercial];

  return (
    <span className={`${cls.badge} ${cls[config.cls]}`}>
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
}
