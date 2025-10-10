const REMOTE_API_BASE = "https://cntanos.pythonanywhere.com/api/v1";
const LOCAL_API_BASE = "/api/v1";

function getWindowRef(windowOverride) {
  if (windowOverride) {
    return windowOverride;
  }
  if (typeof window !== "undefined") {
    return window;
  }
  return null;
}

function getDocumentRef(documentOverride) {
  if (documentOverride) {
    return documentOverride;
  }
  const windowRef = getWindowRef();
  return windowRef?.document ?? null;
}

export function resolveApiBase({ windowRef = getWindowRef(), documentRef = getDocumentRef() } = {}) {
  const defaultBase = REMOTE_API_BASE;

  if (!windowRef) {
    return LOCAL_API_BASE;
  }

  const windowOverride =
    typeof windowRef.GREEKTAX_API_BASE === "string" ? windowRef.GREEKTAX_API_BASE.trim() : "";
  if (windowOverride) {
    return windowOverride;
  }

  const metaElement = documentRef?.querySelector?.("meta[data-api-base]") ?? null;
  if (metaElement) {
    const datasetValue =
      typeof metaElement.dataset?.apiBase === "string" ? metaElement.dataset.apiBase.trim() : "";
    const attributeValue =
      typeof metaElement.getAttribute === "function"
        ? (metaElement.getAttribute("data-api-base") || "").trim()
        : "";
    const metaOverride = datasetValue || attributeValue;
    if (metaOverride) {
      return metaOverride;
    }
  }

  const locationRef = windowRef.location || null;
  if (locationRef && typeof locationRef.hostname === "string") {
    const hostname = locationRef.hostname.trim().toLowerCase();
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

export function createApiClient({
  windowRef = getWindowRef(),
  documentRef = getDocumentRef(),
  fetchImpl = typeof fetch === "function" ? fetch : null,
} = {}) {
  const apiBase = resolveApiBase({ windowRef, documentRef });

  if (typeof fetchImpl !== "function") {
    throw new Error("Fetch implementation is required for the API client");
  }

  const endpoints = {
    years: `${apiBase}/config/years`,
    meta: `${apiBase}/config/meta`,
    investment: (year, locale) =>
      `${apiBase}/config/${year}/investment-categories?locale=${encodeURIComponent(locale)}`,
    deductions: (year, locale) =>
      `${apiBase}/config/${year}/deductions?locale=${encodeURIComponent(locale)}`,
    calculations: `${apiBase}/calculations`,
    translations: (locale) =>
      locale
        ? `${apiBase}/translations/${encodeURIComponent(locale)}`
        : `${apiBase}/translations`,
  };

  async function fetchJson(url, options = {}) {
    const response = await fetchImpl(url, options);
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      const message =
        typeof errorPayload?.message === "string" && errorPayload.message.trim()
          ? errorPayload.message.trim()
          : response.statusText;
      throw new Error(message || `Request failed with status ${response.status}`);
    }
    return response.json();
  }

  return {
    apiBase,
    fetchTranslations(locale) {
      return fetchJson(endpoints.translations(locale));
    },
    fetchYears() {
      return fetchJson(endpoints.years);
    },
    fetchMeta() {
      return fetchJson(endpoints.meta, { credentials: "omit" });
    },
    fetchInvestmentCategories(year, locale) {
      return fetchJson(endpoints.investment(year, locale));
    },
    fetchDeductionHints(year, locale) {
      return fetchJson(endpoints.deductions(year, locale));
    },
    submitCalculation(payload, locale) {
      return fetchJson(endpoints.calculations, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept-Language": locale,
        },
        body: JSON.stringify(payload),
      });
    },
  };
}

export { REMOTE_API_BASE, LOCAL_API_BASE };
