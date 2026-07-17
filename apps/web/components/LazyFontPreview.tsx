"use client";

import { useEffect, useRef } from "react";
import type { Font } from "@/types/font";
import { resolveFontPreview } from "@/lib/fontPreview";

function ensureStylesheet(url: string) {
  const exists = Array.from(
    document.querySelectorAll<HTMLLinkElement>(
      'link[data-fontagit-webfont="true"]'
    )
  ).some((link) => link.href === url);
  if (exists) return;

  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = url;
  link.dataset.fontagitWebfont = "true";
  document.head.appendChild(link);
}

export function LazyFontPreview({
  font,
  className,
  children,
}: {
  font: Pick<
    Font,
    "fontKey" | "nameEn" | "sourceTier" | "availableWeights"
  >;
  className?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const preview = resolveFontPreview(font);

  useEffect(() => {
    const stylesheetUrl = preview.stylesheetUrl;
    if (!stylesheetUrl || !ref.current) return;

    const load = () => ensureStylesheet(stylesheetUrl);
    if (!("IntersectionObserver" in window)) {
      load();
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          load();
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [preview.stylesheetUrl]);

  return (
    <div
      ref={ref}
      className={className}
      style={{ fontFamily: preview.fontFamily }}
    >
      {children}
    </div>
  );
}
