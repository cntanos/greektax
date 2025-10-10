import { describe, expect, it, vi } from "vitest";
import {
  createApiClient,
  resolveApiBase,
  LOCAL_API_BASE,
} from "../src/frontend/assets/scripts/modules/apiClient.js";

describe("resolveApiBase", () => {
  it("returns local base for localhost hostnames", () => {
    const base = resolveApiBase({
      windowRef: { location: { hostname: "localhost" } },
      documentRef: null,
    });
    expect(base).toBe(LOCAL_API_BASE);
  });

  it("prefers meta tag overrides", () => {
    const meta = {
      dataset: { apiBase: "https://example.test/api" },
      getAttribute: vi.fn(),
    };
    const documentRef = { querySelector: vi.fn().mockReturnValue(meta) };
    const base = resolveApiBase({
      windowRef: { location: { hostname: "app.example" } },
      documentRef,
    });
    expect(base).toBe("https://example.test/api");
  });
});

describe("createApiClient", () => {
  it("issues JSON requests to API endpoints", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ years: [] }),
      statusText: "OK",
    });
    const client = createApiClient({
      windowRef: { location: { hostname: "localhost" } },
      fetchImpl: fetchMock,
    });

    await client.fetchYears();
    expect(fetchMock).toHaveBeenCalledWith(`${LOCAL_API_BASE}/config/years`, {});

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ locale: "en", frontend: {} }),
      statusText: "OK",
    });
    await client.fetchTranslations("en");
    expect(fetchMock).toHaveBeenLastCalledWith(
      `${LOCAL_API_BASE}/translations/en`,
      {},
    );
  });
});
