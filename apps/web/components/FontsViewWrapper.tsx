"use client";

import { useSearchParams } from "next/navigation";
import type { Font } from "@/types/font";
import { ClientFontFilters } from "./ClientFontFilters";
import { ClientFontsList } from "./ClientFontsList";
import { SectionedFontsView } from "./SectionedFontsView";

interface FontsViewWrapperProps {
  fonts: Font[];
}

/**
 * 폰트 목록 및 개요를 선택적으로 렌더하는 래퍼.
 * 파라미터에 따라 개요 모드(SectionedFontsView) 또는 평면 모드(ClientFontsList)를 렌더한다.
 */
export function FontsViewWrapper({ fonts }: FontsViewWrapperProps) {
  const searchParams = useSearchParams();
  const section = searchParams.get("section");
  const category = searchParams.get("category");
  const tier = searchParams.get("tier");
  const source = searchParams.get("source");

  // 파라미터가 없으면 개요 모드
  const isOverview = !section && !category && !tier && !source;

  return isOverview ? (
    <SectionedFontsView fonts={fonts} />
  ) : (
    <>
      <ClientFontFilters fonts={fonts} />
      <ClientFontsList fonts={fonts} />
    </>
  );
}
