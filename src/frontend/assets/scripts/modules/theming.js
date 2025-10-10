const THEME_STORAGE_KEY = "greektax.theme";
const DEFAULT_THEME = "dark";

let currentTheme = DEFAULT_THEME;
let hasAppliedThemeOnce = false;
let themeTransitionHandle = null;

function getDocumentRef(documentOverride) {
  if (documentOverride) {
    return documentOverride;
  }
  if (typeof document !== "undefined") {
    return document;
  }
  return null;
}

function getWindowRef(windowOverride) {
  if (windowOverride) {
    return windowOverride;
  }
  if (typeof window !== "undefined") {
    return window;
  }
  return null;
}

export function getCurrentTheme() {
  return currentTheme;
}

export function resolveStoredTheme(
  defaultTheme = DEFAULT_THEME,
  storage = getWindowRef()?.localStorage,
) {
  try {
    const stored = storage?.getItem?.(THEME_STORAGE_KEY);
    if (stored === "dark" || stored === "light") {
      return stored;
    }
    return defaultTheme;
  } catch (error) {
    if (typeof console !== "undefined" && console.warn) {
      console.warn("Unable to access theme preference", error);
    }
    return defaultTheme;
  }
}

export function persistTheme(
  theme,
  storage = getWindowRef()?.localStorage,
) {
  try {
    storage?.setItem?.(THEME_STORAGE_KEY, theme);
  } catch (error) {
    if (typeof console !== "undefined" && console.warn) {
      console.warn("Unable to persist theme preference", error);
    }
  }
}

export function updateThemeButtonState(theme, buttons = []) {
  buttons.forEach((button) => {
    if (!button) {
      return;
    }
    const value = button.dataset?.themeOption || DEFAULT_THEME;
    const isActive = value === theme;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

export function applyTheme(
  theme,
  {
    documentRef = getDocumentRef(),
    windowRef = getWindowRef(),
    buttons = [],
    onThemeApplied = null,
  } = {},
) {
  const normalized = theme === "dark" || theme === "light" ? theme : DEFAULT_THEME;
  currentTheme = normalized;
  const root = documentRef?.documentElement || null;

  if (root) {
    if (hasAppliedThemeOnce && windowRef) {
      root.classList.add("theme-transition");
      if (themeTransitionHandle) {
        windowRef.clearTimeout(themeTransitionHandle);
      }
      themeTransitionHandle = windowRef.setTimeout(() => {
        root.classList.remove("theme-transition");
        themeTransitionHandle = null;
      }, 280);
    }

    root.setAttribute("data-theme", normalized);
  }

  updateThemeButtonState(normalized, buttons);
  persistTheme(normalized, windowRef?.localStorage);
  hasAppliedThemeOnce = true;

  const executeCallback = () => {
    if (typeof onThemeApplied === "function") {
      onThemeApplied(normalized);
    }
  };

  if (windowRef?.requestAnimationFrame) {
    windowRef.requestAnimationFrame(() => {
      windowRef.requestAnimationFrame(executeCallback);
    });
  } else if (windowRef) {
    windowRef.setTimeout(executeCallback, 0);
  } else {
    executeCallback();
  }
}

export function initialiseThemeControls(
  buttons,
  {
    documentRef = getDocumentRef(),
    windowRef = getWindowRef(),
    onThemeApplied = null,
  } = {},
) {
  if (!Array.isArray(buttons) || buttons.length === 0) {
    return;
  }

  buttons.forEach((button) => {
    if (!button) {
      return;
    }

    button.addEventListener("click", () => {
      const value = button.dataset?.themeOption || DEFAULT_THEME;
      if (value === currentTheme) {
        return;
      }
      applyTheme(value, {
        documentRef,
        windowRef,
        buttons,
        onThemeApplied,
      });
    });
  });
}

export { DEFAULT_THEME, THEME_STORAGE_KEY };
