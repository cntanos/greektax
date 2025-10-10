import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  applyTheme,
  resolveStoredTheme,
  initialiseThemeControls,
} from "../src/frontend/assets/scripts/modules/theming.js";

const THEME_STORAGE_KEY = "greektax.theme";

beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
    callback();
    return 1;
  });
  localStorage.clear();
  document.documentElement.setAttribute("data-theme", "dark");
  document.body.innerHTML = "";
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("resolveStoredTheme", () => {
  it("returns stored theme when available", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "light");
    expect(resolveStoredTheme()).toBe("light");
  });

  it("falls back to default for unknown values", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "blue");
    expect(resolveStoredTheme("light")).toBe("light");
  });
});

describe("applyTheme", () => {
  it("updates document attribute and persists theme", () => {
    const button = document.createElement("button");
    button.dataset.themeOption = "light";
    document.body.appendChild(button);

    const onApplied = vi.fn();
    applyTheme("light", { buttons: [button], onThemeApplied: onApplied });

    vi.runAllTimers();

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(button.classList.contains("is-active")).toBe(true);
    expect(button.getAttribute("aria-pressed")).toBe("true");
    expect(onApplied).toHaveBeenCalledWith("light");
  });
});

describe("initialiseThemeControls", () => {
  it("applies theme when a different option is selected", () => {
    const darkButton = document.createElement("button");
    darkButton.dataset.themeOption = "dark";
    darkButton.classList.add("is-active");
    darkButton.setAttribute("aria-pressed", "true");

    const lightButton = document.createElement("button");
    lightButton.dataset.themeOption = "light";

    document.body.appendChild(darkButton);
    document.body.appendChild(lightButton);

    const onApplied = vi.fn();
    applyTheme("dark", { buttons: [darkButton, lightButton], onThemeApplied: vi.fn() });
    vi.runAllTimers();
    initialiseThemeControls([darkButton, lightButton], { onThemeApplied: onApplied });

    lightButton.click();

    vi.runAllTimers();
    expect(onApplied).toHaveBeenCalledWith("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
