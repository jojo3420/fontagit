import "@testing-library/jest-dom";
import { vi } from "vitest";

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
