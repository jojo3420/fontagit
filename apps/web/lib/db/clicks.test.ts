import { describe, it, expect, vi, beforeEach } from "vitest";

const rpcMock = vi.fn();
vi.mock("./client", () => ({
  supabaseClient: { rpc: (...args: unknown[]) => rpcMock(...args) },
}));

import { recordClick } from "./clicks";

describe("recordClick", () => {
  beforeEach(() => {
    rpcMock.mockReset();
  });

  it("record_click RPC를 p_slug로 호출한다", async () => {
    rpcMock.mockResolvedValue({ data: null, error: null });
    recordClick("noto-sans-kr");
    await vi.waitFor(() =>
      expect(rpcMock).toHaveBeenCalledWith("record_click", { p_slug: "noto-sans-kr" })
    );
  });

  it("RPC 오류가 나도 throw하지 않는다 (fire-and-forget)", async () => {
    rpcMock.mockResolvedValue({ data: null, error: { message: "boom" } });
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => recordClick("noto-sans-kr")).not.toThrow();
    await vi.waitFor(() => expect(consoleErrorSpy).toHaveBeenCalled());
    consoleErrorSpy.mockRestore();
  });

  it("RPC reject(네트워크 예외)여도 unhandled rejection 없이 삼킨다", async () => {
    rpcMock.mockRejectedValue(new Error("network down"));
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => recordClick("noto-sans-kr")).not.toThrow();
    await vi.waitFor(() => expect(consoleErrorSpy).toHaveBeenCalled());
    consoleErrorSpy.mockRestore();
  });

  it("빈 slug는 RPC를 호출하지 않는다", () => {
    recordClick("");
    expect(rpcMock).not.toHaveBeenCalled();
  });

  it("rpc가 동기 throw해도 throw하지 않는다 (계약 유지)", async () => {
    rpcMock.mockImplementation(() => {
      throw new Error("sync error");
    });
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => recordClick("noto-sans-kr")).not.toThrow();
    await vi.waitFor(() => expect(consoleErrorSpy).toHaveBeenCalled());
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      "[clicks] record_click failed:",
      expect.any(Error)
    );
    consoleErrorSpy.mockRestore();
  });
});
