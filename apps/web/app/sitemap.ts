import type { MetadataRoute } from "next";
import { getPublishedSlugs, getAllCollectionSlugs } from "@/lib/data";
import { BASE_URL } from "@/lib/seo";

export const dynamic = "force-static";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const fontSlugs = await getPublishedSlugs();
  const collectionSlugs = await getAllCollectionSlugs();

  const fontEntries: MetadataRoute.Sitemap = fontSlugs.map((slug) => ({
    url: `${BASE_URL}/fonts/${encodeURIComponent(slug)}/`,
  }));

  const collectionEntries: MetadataRoute.Sitemap = collectionSlugs.map(
    (slug) => ({
      url: `${BASE_URL}/collections/${encodeURIComponent(slug)}/`,
    })
  );

  const staticEntries: MetadataRoute.Sitemap = [
    "/",
    "/fonts/",
    "/collections/",
    "/trends/",
    "/playground/",
    "/about/",
  ].map((path) => ({ url: `${BASE_URL}${path}` }));

  return [...staticEntries, ...fontEntries, ...collectionEntries];
}
