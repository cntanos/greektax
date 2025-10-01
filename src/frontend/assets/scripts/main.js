/* Entry point for the GreekTax front-end.
 *
 * TODO: Implement SPA-style interactions or progressive enhancement to connect
 * to the backend API for tax computations. Initial features will include:
 * - Fetching year configuration metadata
 * - Managing bilingual labels and locale switching
 * - Handling form inputs and displaying calculation results
 */

const API_ENDPOINT = "/api/v1/calculations";
const STORAGE_KEY = "greektax.locale";

const localeSelect = document.getElementById("locale-select");
const previewButton = document.getElementById("preview-button");
const previewStatus = document.getElementById("preview-status");
const previewJson = document.getElementById("preview-json");

const demoPayload = {
  year: 2024,
  dependents: { children: 1 },
  employment: { gross_income: 24000 },
  freelance: {
    gross_revenue: 12000,
    deductible_expenses: 2000,
    mandatory_contributions: 2500,
  },
};

function resolveStoredLocale(defaultLocale = "en") {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored || defaultLocale;
  } catch (error) {
    console.warn("Unable to access localStorage", error);
    return defaultLocale;
  }
}

function persistLocale(locale) {
  try {
    window.localStorage.setItem(STORAGE_KEY, locale);
  } catch (error) {
    console.warn("Unable to persist locale preference", error);
  }
}

function applyLocale(locale) {
  if (localeSelect) {
    localeSelect.value = locale;
  }
  document.documentElement.lang = locale;
  persistLocale(locale);
}

function setStatus(message, { isError = false, showJson = false } = {}) {
  if (previewStatus) {
    previewStatus.textContent = message;
    previewStatus.setAttribute(
      "data-status",
      isError ? "error" : "info",
    );
  }

  if (previewJson) {
    previewJson.hidden = !showJson;
  }
}

async function requestPreview(locale) {
  const payload = { ...demoPayload, locale };
  setStatus("Requesting preview from the API…");

  try {
    const response = await fetch(API_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept-Language": locale,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.message || response.statusText);
    }

    const result = await response.json();
    setStatus("Preview updated using backend localisation.", {
      showJson: true,
    });
    if (previewJson) {
      previewJson.textContent = JSON.stringify(result, null, 2);
    }
  } catch (error) {
    console.error("Failed to load preview", error);
    setStatus("Unable to fetch preview. Is the backend running?", {
      isError: true,
    });
  }
}

function bootstrap() {
  if (!localeSelect || !previewButton || !previewStatus || !previewJson) {
    console.warn("Preview controls missing from DOM");
    return;
  }

  const initialLocale = resolveStoredLocale();
  applyLocale(initialLocale);

  localeSelect.addEventListener("change", (event) => {
    const target = event.target;
    const locale = typeof target?.value === "string" ? target.value : "en";
    applyLocale(locale);
  });

  previewButton.addEventListener("click", () => {
    const locale = localeSelect.value || "en";
    requestPreview(locale);
  });

  console.info("GreekTax localisation preview initialised");
}

document.addEventListener("DOMContentLoaded", bootstrap);
