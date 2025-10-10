import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  ensureTranslations,
  t,
  formatNumber,
  formatCurrency,
  formatPercent,
  formatDateTime,
  formatListForLocale,
  setActiveLocale,
  normaliseLocaleChoice,
  __resetLocalisationState,
} from "../src/frontend/assets/scripts/modules/localisation.js";

beforeEach(() => {
  __resetLocalisationState();
  setActiveLocale("en");
});

describe("ensureTranslations", () => {
  it("stores fetched translations and returns locale", async () => {
    const payload = {
      available_locales: ["en"],
      locale: "en",
      frontend: {
        ui: { list_and: "and" },
        status: { ready: "Ready" },
      },
      fallback: null,
    };

    const resolved = await ensureTranslations("en", async () => payload);
    expect(resolved).toBe("en");
    expect(t("ui.list_and")).toBe("and");
  });

  it("falls back when primary fetch fails", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce({
        available_locales: ["en"],
        locale: "en",
        frontend: { status: { ready: "Ready" } },
        fallback: null,
      });

    const resolved = await ensureTranslations("el", fetchMock);
    expect(resolved).toBe("en");
    setActiveLocale(resolved);
    expect(t("status.ready")).toBe("Ready");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("formatting helpers", () => {
  it("formats numbers using locale-aware rules", () => {
    expect(formatNumber(1234.56, { locale: "en" })).toBe("1,234.56");
    expect(formatCurrency(10, { locale: "el" })).toContain("€");
    expect(formatPercent(0.125, { locale: "en", maximumFractionDigits: 2 })).toBe("12.5%");
  });

  it("formats dates using locale-specific rules", () => {
    const date = new Date("2024-01-05T12:00:00Z");
    const formatted = formatDateTime(date, { locale: "en" });
    expect(typeof formatted).toBe("string");
  });

  it("formats lists with conjunctions", () => {
    setActiveLocale("en");
    expect(formatListForLocale(["A", "B", "C"])).toContain("and");
  });
});

describe("normaliseLocaleChoice", () => {
  it("lowercases and trims locale tags", () => {
    expect(normaliseLocaleChoice("EN-gb")).toBe("en");
  });
});
