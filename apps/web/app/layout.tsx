import type { Metadata, Viewport } from "next";
import "./globals.css";
import { fontClassNames } from "@/lib/fonts";
import { BASE_URL } from "@/lib/seo";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { MobileTabBar } from "@/components/MobileTabBar";

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: "FontAgit 폰트 아지트",
  description: "무료-유료-국내외 폰트를 검색-비교하는 폰트 아지트",
};

export const viewport: Viewport = { viewportFit: "cover" };

const themeScript = `(function(){try{var t=localStorage.getItem('theme');if(t!=='dark'&&t!=='light'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.setAttribute('data-theme',t);}catch(e){}})();`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className={fontClassNames} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Header />
        {children}
        <Footer />
        <MobileTabBar />
      </body>
    </html>
  );
}
