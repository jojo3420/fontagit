import type { Tier } from "@/types/font";
import cls from "./TierChip.module.css";

interface TierChipProps {
  tier: Tier;
}

export function TierChip({ tier }: TierChipProps) {
  const tierLabel = tier === "free" ? "무료" : "유료";
  const tierClass = tier === "free" ? cls.free : cls.paid;

  return <span className={`${cls.chip} ${tierClass}`}>{tierLabel}</span>;
}
