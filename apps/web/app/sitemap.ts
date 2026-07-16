import type { MetadataRoute } from "next";
import { getAllSlugs, getAllCollectionSlugs } from "@/lib/data";
import { BASE_URL } from "@/lib/seo";

export const dynamic = "force-static";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const fontSlugs = await getAllSlugs();
  const collectionSlugs = await getAllCollectionSlugs();

  const fontEntries: MetadataRoute.Sitemap = fontSlugs.map((slug) => ({
    url: `${BASE_URL}/fonts/${slug}/`,
    changeFrequency: "weekly" as const,
    priority: 0.8,
  }));

  const collectionEntries: MetadataRoute.Sitemap = collectionSlugs.map(
    (slug) => ({
      url: `${BASE_URL}/collections/${slug}/`,
      changeFrequency: "weekly" as const,
      priority: 0.9,
    })
  );

  const staticEntries: MetadataRoute.Sitemap = [
    {
      url: `${BASE_URL}/`,
      changeFrequency: "daily" as const,
      priority: 1.0,
    },
    {
      url: `${BASE_URL}/fonts/`,
      changeFrequency: "daily" as const,
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/collections/`,
      changeFrequency: "weekly" as const,
      priority: 0.8,
    },
    {
      url: `${BASE_URL}/trends/`,
      changeFrequency: "daily" as const,
      priority: 0.7,
    },
  ];

  return [...staticEntries, ...fontEntries, ...collectionEntries];
}
