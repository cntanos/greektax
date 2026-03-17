export const REMOTE_API_BASE = "/api/v1";
export const LOCAL_API_BASE = "/api/v1";

export function resolveApiBase() {
  const defaultBase = LOCAL_API_BASE;

  if (typeof window === "undefined") {
    return LOCAL_API_BASE;
  }

  const windowOverride =
    typeof window.GREEKTAX_API_BASE === "string"
      ? window.GREEKTAX_API_BASE.trim()
      : "";
  if (windowOverride) {
    return windowOverride;
  }

  const documentRef = window.document || null;
  const metaElement =
    documentRef && documentRef.querySelector
      ? documentRef.querySelector("meta[data-api-base]")
      : null;
  if (metaElement) {
    const metaOverride =
      typeof metaElement.dataset?.apiBase === "string"
        ? metaElement.dataset.apiBase.trim()
        : (metaElement.getAttribute("data-api-base") || "").trim();
    if (metaOverride) {
      return metaOverride;
    }
  }

  const locationRef = window.location || null;
  if (locationRef) {
    const hostname = typeof locationRef.hostname === "string"
      ? locationRef.hostname.trim().toLowerCase()
      : "";
    if (
      hostname === "localhost" ||
      hostname === "127.0.0.1" ||
      hostname === "::1" ||
      hostname.endsWith(".localhost")
    ) {
      return LOCAL_API_BASE;
    }
  }

  return defaultBase;
}

export function buildApiEndpoints(apiBase = resolveApiBase()) {
  return {
    API_BASE: apiBase,
    CALCULATIONS_ENDPOINT: `${apiBase}/calculations`,
    CONFIG_YEARS_ENDPOINT: `${apiBase}/config/years`,
    CONFIG_META_ENDPOINT: `${apiBase}/config/meta`,
    CONFIG_INVESTMENT_ENDPOINT: (year, locale) =>
      `${apiBase}/config/${year}/investment-categories?locale=${encodeURIComponent(
        locale,
      )}`,
    CONFIG_DEDUCTIONS_ENDPOINT: (year, locale) =>
      `${apiBase}/config/${year}/deductions?locale=${encodeURIComponent(locale)}`,
    TRANSLATIONS_ENDPOINT: (locale) =>
      locale
        ? `${apiBase}/translations/${encodeURIComponent(locale)}`
        : `${apiBase}/translations`,
  };
}
