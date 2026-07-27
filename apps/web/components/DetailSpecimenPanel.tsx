"use client";
import { useEffect, useMemo, useState } from "react";
import type { Font } from "@/types/font";
import { getDefaultSpecimenText } from "@/lib/specimen";
import { resolveDetailFontPreview } from "@/lib/fontPreview";
import { SpecimenBox } from "./SpecimenBox";
import {
  WeightSpecimenSection,
  comboKey,
  type ComboLoadStatus,
} from "./WeightSpecimenSection";

const LOAD_TIMEOUT_MS = 5000;
/** 판정 일관성을 위한 고정 검사 문자열(사용자 입력과 무관). */
const PROBE_TEXT = "다람쥐 한글Aa1";
/** 같은 url의 in-flight/완료 Promise를 재사용하여 경합 방지. */
const stylesheetPromises = new Map<string, Promise<void>>();

function ensureStylesheet(url: string): Promise<void> {
  if (stylesheetPromises.has(url)) {
    return stylesheetPromises.get(url)!;
  }

  const existing = Array.from(
    document.querySelectorAll<HTMLLinkElement>(
      'link[data-fontagit-webfont="true"]'
    )
  ).find((link) => link.href === url);
  if (existing) {
    const resolved = Promise.resolve();
    stylesheetPromises.set(url, resolved);
    return resolved;
  }

  const promise = new Promise<void>((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = url;
    link.dataset.fontagitWebfont = "true";
    link.onload = () => {
      resolve();
    };
    link.onerror = () => {
      stylesheetPromises.delete(url);
      reject(new Error("stylesheet load failed"));
    };
    document.head.appendChild(link);
  });

  stylesheetPromises.set(url, promise);
  return promise;
}

/** 요청 조합과 로드된 FontFace의 weight/style이 실제로 일치하는지 대조한다. */
function fontActuallyLoaded(
  family: string,
  weight: number,
  style: "normal" | "italic"
): boolean {
  return Array.from(document.fonts).some(
    (face) =>
      face.family.replace(/^["']|["']$/g, "") === family &&
      face.style === style &&
      (face.weight === String(weight) ||
        face.weight.split(" ").includes(String(weight))) &&
      face.status === "loaded"
  );
}

/**
 * 상세 화면 클라이언트 래퍼: 미리보기 문장 상태를 소유하고,
 * 전체 조합 시트를 1회 로드한 뒤 조합별 실로드를 검증해 섹션에 내려준다.
 */
export function DetailSpecimenPanel({
  font,
  editable,
  caption,
}: {
  font: Font;
  editable: boolean;
  caption?: string;
}) {
  const [text, setText] = useState(getDefaultSpecimenText(font));
  const detail = useMemo(() => resolveDetailFontPreview(font), [font]);
  const [statuses, setStatuses] = useState<Record<string, ComboLoadStatus>>({});

  useEffect(() => {
    if (detail.combos.length === 0) return;
    let cancelled = false;
    const familyName = font.nameEn.trim();
    const markAll = (status: ComboLoadStatus) => {
      if (cancelled) return;
      setStatuses(
        Object.fromEntries(detail.combos.map((c) => [comboKey(c), status]))
      );
    };
    markAll("loading");

    const verify = async () => {
      for (const combo of detail.combos) {
        const spec = `${combo.style} ${combo.weight} 16px ${JSON.stringify(familyName)}`;
        let ok = false;
        try {
          await document.fonts.load(spec, PROBE_TEXT);
          ok = fontActuallyLoaded(familyName, combo.weight, combo.style);
        } catch {
          ok = false;
        }
        if (cancelled) return;
        setStatuses((prev) => ({
          ...prev,
          [comboKey(combo)]: ok ? "loaded" : "failed",
        }));
      }
    };

    const timeout = window.setTimeout(() => {
      if (cancelled) return;
      setStatuses((prev) =>
        Object.fromEntries(
          detail.combos.map((c) => [
            comboKey(c),
            prev[comboKey(c)] === "loaded" ? "loaded" : "failed",
          ])
        )
      );
    }, LOAD_TIMEOUT_MS);

    const start = detail.stylesheetUrl
      ? ensureStylesheet(detail.stylesheetUrl)
      : Promise.resolve();
    start.then(verify).catch(() => markAll("failed"));

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [detail, font.nameEn]);

  return (
    <>
      <SpecimenBox
        font={font}
        editable={editable}
        caption={caption}
        text={text}
        onTextChange={setText}
        stylesheetManaged={detail.stylesheetUrl !== null}
      />
      <WeightSpecimenSection
        font={font}
        text={text}
        combos={detail.combos}
        statuses={statuses}
        fontFamily={detail.fontFamily}
      />
    </>
  );
}
