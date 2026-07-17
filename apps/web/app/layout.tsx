import type { Metadata, Viewport } from "next";
import Script from "next/script";
import "./globals.css";
import { fontClassNames } from "@/lib/fonts";
import { BASE_URL } from "@/lib/seo";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { MobileTabBar } from "@/components/MobileTabBar";
import { GoogleAnalytics } from "@/components/Analytics/GoogleAnalytics";
import { AdBlockBanner } from "@/components/AdBlock/AdBlockBanner";
import {
  GOOGLE_SITE_VERIFICATION,
  NAVER_SITE_VERIFICATION,
  ADSENSE_CLIENT,
  isAdSenseEnabled,
} from "@/lib/analytics/constants";

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: "FontAgit 폰트 아지트",
  description: "무료-유료-국내외 폰트를 검색-비교하는 폰트 아지트",
  other: {
    ...(GOOGLE_SITE_VERIFICATION && {
      "google-site-verification": GOOGLE_SITE_VERIFICATION,
    }),
    ...(NAVER_SITE_VERIFICATION && {
      "naver-site-verification": NAVER_SITE_VERIFICATION,
    }),
  },
};

export const viewport: Viewport = { viewportFit: "cover" };

const themeScript = `(function(){try{var t=localStorage.getItem('theme');if(t!=='dark'&&t!=='light'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.setAttribute('data-theme',t);}catch(e){}})();`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className={fontClassNames} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        {isAdSenseEnabled && (
          <Script
            async
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT}`}
            strategy="lazyOnload"
            crossOrigin="anonymous"
          />
        )}
      </head>
      <body>
        <GoogleAnalytics />
        <Header />
        {children}
        {isAdSenseEnabled && <AdBlockBanner />}
        <Footer />
        <MobileTabBar />
      </body>
    </html>
  );
}
