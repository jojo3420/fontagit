"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./MobileTabBar.module.css";

const TABS = [
  { href: "/", label: "홈" },
  { href: "/fonts", label: "폰트" },
  { href: "/trends", label: "트렌드" },
  { href: "/playground", label: "캔버스" },
  { href: "/compare", label: "비교" },
];

export function MobileTabBar() {
  const pathname = usePathname();
  return (
    <nav className={styles.bar} aria-label="모바일 탭">
      {TABS.map((t) => {
        const active = t.href === "/" ? pathname === "/" : (pathname === t.href || pathname.startsWith(`${t.href}/`));
        return (
          <Link key={t.href} href={t.href} className={active ? styles.active : styles.tab} aria-current={active ? "page" : undefined}>
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
