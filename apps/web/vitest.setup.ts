import "@testing-library/jest-dom";
import { vi } from "vitest";

// 테스트용 환경 변수 설정
process.env.NEXT_PUBLIC_SUPABASE_URL = "https://test.supabase.co";
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-key";

const fontStub = () => ({
  className: "",
  variable: "",
  style: { fontFamily: "" },
});

vi.mock("next/font/google", () => ({
  __esModule: true,
  Black_Han_Sans: fontStub,
  Jua: fontStub,
  Do_Hyeon: fontStub,
  Gowun_Batang: fontStub,
  Nanum_Myeongjo: fontStub,
  Kirang_Haerang: fontStub,
  Gaegu: fontStub,
  Song_Myung: fontStub,
}));

vi.mock("next/navigation", () => ({
  __esModule: true,
  useRouter: () => ({
    push: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));
