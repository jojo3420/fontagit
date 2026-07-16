"use client";

import type { ReactNode } from "react";
import { recordClick } from "@/lib/db/clicks";

interface Props {
  slug: string;
  href: string;
  className: string;
  children: ReactNode;
}

/** 공식 페이지 이동 CTA. 클릭을 fire-and-forget 기록하고 새 탭 이동은 절대 차단하지 않는다 */
export function OfficialLinkCta({ slug, href, className, children }: Props) {
  return (
    <a
      className={className}
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={() => recordClick(slug)}
    >
      {children}
    </a>
  );
}
