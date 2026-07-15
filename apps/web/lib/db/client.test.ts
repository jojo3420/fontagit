import { describe, it, expect, vi } from "vitest";

describe("lib/db/client", () => {
  it("env vars 있을 때 supabaseClient를 export해야 함", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "http://localhost:54321";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-key";

    // Clear module cache to force re-evaluation
    vi.resetModules();

    const clientModule = await import("./client");
    expect(clientModule.supabaseClient).toBeDefined();
    expect(typeof clientModule.supabaseClient).toBe("object");
  });

  it("supabaseClient는 auth, storage 등 기본 모듈을 포함해야 함", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "http://localhost:54321";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-key";

    vi.resetModules();

    const clientModule = await import("./client");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const client = clientModule.supabaseClient as any;
    expect(client).toHaveProperty("auth");
    expect(client).toHaveProperty("storage");
  });

  it("NEXT_PUBLIC_SUPABASE_URL 없을 때 에러 던져야 함", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-key";

    vi.resetModules();

    try {
      await import("./client");
      expect.fail("Should throw error for missing NEXT_PUBLIC_SUPABASE_URL");
    } catch (error) {
      expect((error as Error).message).toBe("NEXT_PUBLIC_SUPABASE_URL is required");
    }
  });

  it("NEXT_PUBLIC_SUPABASE_ANON_KEY 없을 때 에러 던져야 함", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "http://localhost:54321";
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    vi.resetModules();

    try {
      await import("./client");
      expect.fail("Should throw error for missing NEXT_PUBLIC_SUPABASE_ANON_KEY");
    } catch (error) {
      expect((error as Error).message).toBe("NEXT_PUBLIC_SUPABASE_ANON_KEY is required");
    }
  });
});
