/**
 * Front-end logic for the GreekTax prototype calculator.
 *
 * The script bootstraps localisation-aware metadata retrieval, provides client
 * validation for numeric fields, and renders interactive calculation results
 * returned by the Flask back-end.
 */

const REMOTE_API_BASE = "https://cntanos.pythonanywhere.com/api/v1";
const LOCAL_API_BASE = "/api/v1";

// Default to the remote API; toggle the line below for local development.
const API_BASE = REMOTE_API_BASE;
// const API_BASE = LOCAL_API_BASE; // Uncomment to use the local API during development.
const CALCULATIONS_ENDPOINT = `${API_BASE}/calculations`;
const CONFIG_YEARS_ENDPOINT = `${API_BASE}/config/years`;
const CONFIG_META_ENDPOINT = `${API_BASE}/config/meta`;
const CONFIG_INVESTMENT_ENDPOINT = (year, locale) =>
  `${API_BASE}/config/${year}/investment-categories?locale=${encodeURIComponent(
    locale,
  )}`;
const CONFIG_DEDUCTIONS_ENDPOINT = (year, locale) =>
  `${API_BASE}/config/${year}/deductions?locale=${encodeURIComponent(locale)}`;
const STORAGE_KEY = "greektax.locale";
const CALCULATOR_STORAGE_KEY = "greektax.calculator.v1";
const CALCULATOR_STORAGE_TTL_MS = 2 * 60 * 60 * 1000; // 2 hours
const THEME_STORAGE_KEY = "greektax.theme";
const DEFAULT_THEME = "dark";
const PLOTLY_SDK_URL = "https://cdn.plot.ly/plotly-2.26.0.min.js";
const PLOTLY_SDK_ATTRIBUTE = "data-plotly-sdk";
const SVG_NS = "http://www.w3.org/2000/svg";

let plotlyLoaderPromise = null;
let pendingPlotlyJob = null;
let sankeyRenderSequence = 0;
let sankeyPlotlyRef = null;
let sankeyResizeObserver = null;
let sankeyWindowResizeHandler = null;
let hasAppliedThemeOnce = false;
let themeTransitionHandle = null;

const TRANSLATIONS_ENDPOINT = (locale) =>
  locale
    ? `${API_BASE}/translations/${encodeURIComponent(locale)}`
    : `${API_BASE}/translations`;

const translationsByLocale = new Map();
let availableTranslationLocales = ["en"];
let fallbackLocale = "en";


let currentLocale = "en";
let currentTheme = DEFAULT_THEME;
const yearMetadataByYear = new Map();
let currentYearMetadata = null;
let currentEmploymentMode = "annual";
let currentPensionMode = "annual";
let currentInvestmentCategories = [];
let currentDeductionHints = [];
let currentFreelanceMetadata = null;
let derivedFreelanceYearsActive = null;
let derivedFreelanceNewlySelfEmployed = false;
let currentYearToggles = {};
let currentYearToggleKeys = new Set();
let dynamicFieldLabels = {};
let deductionValidationByInput = {};
let lastCalculation = null;
let loadedCalculatorState = null;
let pendingCalculatorState = null;
let calculatorStatePersistHandle = null;
let isApplyingYearMetadata = false;
let partialYearWarningActive = false;

const EMPLOYMENT_CONTRIBUTION_PREVIEW_MESSAGES = {
  automatic: {
    key: "hints.employment-employee-contributions-preview",
    fallback: {
      en: "Payroll currently includes {{amount}} in annual EFKA contributions. Enter your yearly total below if it differs.",
      el: "Η μισθοδοσία περιλαμβάνει {{amount}} ετήσιες εισφορές ΕΦΚΑ. Αν το ετήσιο ποσό διαφέρει, καταχωρήστε το παρακάτω.",
    },
  },
  empty: {
    key: "hints.employment-employee-contributions-preview-empty",
    fallback: {
      en: "Run a calculation to preview the EFKA contributions covered by payroll, or enter your annual total below.",
      el: "Εκτελέστε έναν υπολογισμό για να εμφανιστούν οι εισφορές ΕΦΚΑ της μισθοδοσίας ή εισάγετε το ετήσιο ποσό σας παρακάτω.",
    },
  },
  excluded: {
    key: "hints.employment-employee-contributions-preview-excluded",
    fallback: {
      en: "EFKA contributions are excluded from the net calculation; turn the option back on to include them.",
      el: "Οι εισφορές ΕΦΚΑ εξαιρούνται από το καθαρό αποτέλεσμα· ενεργοποιήστε ξανά την επιλογή για να συμπεριληφθούν.",
    },
  },
  manual: {
    key: "hints.employment-employee-contributions-preview-manual",
    fallback: {
      en: "Using your entered EFKA total: {{amount}} per year.",
      el: "Χρησιμοποιείται το ποσό που καταχωρήσατε: {{amount}} ετησίως.",
    },
  },
};

function buildCalculatorFormNameUsage() {
  const usage = new Map();
  if (!calculatorForm) {
    return usage;
  }

  Array.from(calculatorForm.elements || []).forEach((element) => {
    if (!element || typeof element.name !== "string") {
      return;
    }
    const trimmed = element.name.trim();
    if (!trimmed) {
      return;
    }
    usage.set(trimmed, (usage.get(trimmed) || 0) + 1);
  });

  return usage;
}

function getElementPersistenceKey(element, nameUsage = null) {
  if (!element) {
    return null;
  }

  const datasetKey =
    element.dataset && typeof element.dataset.persistKey === "string"
      ? element.dataset.persistKey.trim()
      : "";
  if (datasetKey) {
    return datasetKey;
  }

  const name = typeof element.name === "string" ? element.name.trim() : "";
  if (name) {
    if (!nameUsage || nameUsage.get(name) === 1) {
      return name;
    }
  }

  const id = typeof element.id === "string" ? element.id.trim() : "";
  if (id) {
    return id;
  }

  if (name) {
    return name;
  }

  return null;
}

function escapeSelector(value) {
  if (typeof value !== "string" || !value) {
    return "";
  }
  if (window.CSS && typeof window.CSS.escape === "function") {
    return window.CSS.escape(value);
  }
  return value.replace(/["\\]/g, "\\$&");
}

function getElementsByPersistenceKey(key) {
  if (!key) {
    return [];
  }

  const unique = new Set();
  const matches = [];

  const byId = document.getElementById(key);
  if (byId) {
    unique.add(byId);
    matches.push(byId);
  }

  const escapedKey = escapeSelector(key);
  if (escapedKey) {
    document
      .querySelectorAll(`[data-persist-key="${escapedKey}"]`)
      .forEach((element) => {
        if (!unique.has(element)) {
          unique.add(element);
          matches.push(element);
        }
      });

    if (!matches.length) {
      document
        .querySelectorAll(`[name="${escapedKey}"]`)
        .forEach((element) => {
          if (!unique.has(element)) {
            unique.add(element);
            matches.push(element);
          }
        });
    }
  }

  return matches;
}

const warnedMissingPersistenceKey = new WeakSet();

function warnMissingPersistenceKey(element) {
  if (!element || warnedMissingPersistenceKey.has(element)) {
    return;
  }
  warnedMissingPersistenceKey.add(element);
  if (typeof console !== "undefined" && console && console.warn) {
    console.warn(
      "Calculator field is missing a persistence key (add an id, name, or data-persist-key)",
      element,
    );
  }
}

function normaliseLocaleChoice(locale) {
  if (typeof locale !== "string" || !locale) {
    return fallbackLocale;
  }
  return locale.toLowerCase().split("-")[0];
}

function getFrontendCatalog(locale) {
  const entry = translationsByLocale.get(locale);
  return entry && typeof entry === "object" ? entry : null;
}

function storeFrontendTranslations(locale, frontend) {
  if (!locale || !frontend || typeof frontend !== "object") {
    return;
  }
  translationsByLocale.set(locale, frontend);
}

async function requestTranslations(locale) {
  const response = await fetch(TRANSLATIONS_ENDPOINT(locale));
  if (!response.ok) {
    throw new Error(`Unable to load translations (${response.status})`);
  }

  const payload = await response.json();
  if (!payload || typeof payload !== "object") {
    throw new Error("Unexpected translations payload");
  }

  if (Array.isArray(payload.available_locales) && payload.available_locales.length) {
    availableTranslationLocales = payload.available_locales
      .map((value) =>
        typeof value === "string" ? value.toLowerCase().split("-")[0] : null,
      )
      .filter((value) => value);
  }

  const resolvedLocale =
    typeof payload.locale === "string"
      ? payload.locale.toLowerCase().split("-")[0]
      : null;
  if (resolvedLocale && payload.frontend && typeof payload.frontend === "object") {
    storeFrontendTranslations(resolvedLocale, payload.frontend);
  }

  const fallbackPayload = payload.fallback;
  if (
    fallbackPayload &&
    typeof fallbackPayload === "object" &&
    typeof fallbackPayload.locale === "string" &&
    fallbackPayload.frontend &&
    typeof fallbackPayload.frontend === "object"
  ) {
    const fallbackResolved = fallbackPayload.locale.toLowerCase().split("-")[0];
    fallbackLocale = fallbackResolved;
    storeFrontendTranslations(fallbackResolved, fallbackPayload.frontend);
    if (!availableTranslationLocales.includes(fallbackResolved)) {
      availableTranslationLocales.push(fallbackResolved);
    }
  }

  if (resolvedLocale && !availableTranslationLocales.includes(resolvedLocale)) {
    availableTranslationLocales.push(resolvedLocale);
  }

  if (!availableTranslationLocales.length) {
    availableTranslationLocales = [fallbackLocale];
  } else {
    availableTranslationLocales = Array.from(new Set(availableTranslationLocales));
  }

  return resolvedLocale || fallbackLocale;
}

async function ensureTranslations(locale) {
  const target = normaliseLocaleChoice(locale);
  if (!translationsByLocale.has(target)) {
    try {
      return await requestTranslations(target);
    } catch (error) {
      console.error("Failed to load translations", error);
      if (!translationsByLocale.has(fallbackLocale)) {
        try {
          await requestTranslations(fallbackLocale);
        } catch (fallbackError) {
          console.error("Failed to load fallback translations", fallbackError);
        }
      }
    }
  }
  return translationsByLocale.has(target) ? target : fallbackLocale;
}

function getMessagesSection(locale, section) {
  const catalogue = getFrontendCatalog(locale);
  if (catalogue && section in catalogue && typeof catalogue[section] === "object") {
    return catalogue[section];
  }
  const fallbackCatalogue = getFrontendCatalog(fallbackLocale);
  if (
    fallbackCatalogue &&
    section in fallbackCatalogue &&
    typeof fallbackCatalogue[section] === "object"
  ) {
    return fallbackCatalogue[section];
  }
  return {};
}

const localeButtons = Array.from(
  document.querySelectorAll("[data-locale-option]"),
);
const themeButtons = Array.from(
  document.querySelectorAll("[data-theme-option]"),
);

const yearSelect = document.getElementById("year-select");
const childrenInput = document.getElementById("children-input");
const birthYearInput = document.getElementById("birth-year");
const ageBandSelect = document.getElementById("age-band");
const youthEligibilityControl = document.getElementById(
  "youth-eligibility-control",
);
const youthEligibilityToggle = document.getElementById(
  "youth-eligibility-toggle",
);
const smallVillageControl = document.getElementById("small-village-control");
const smallVillageToggle = document.getElementById("small-village-toggle");
const newMotherControl = document.getElementById("new-mother-control");
const newMotherToggle = document.getElementById("new-mother-toggle");
const youthRatesNote = document.getElementById("youth-rates-note");
const tekmiriaNote = document.getElementById("tekmiria-note");
const employmentIncomeInput = document.getElementById("employment-income");
const employmentMonthlyIncomeInput = document.getElementById(
  "employment-monthly-income",
);
const employmentEmployeeContributionsInput = document.getElementById(
  "employment-employee-contributions",
);
const employmentEmployeeContributionsPreview = document.getElementById(
  "employment-employee-contributions-preview",
);
const employmentIncludeSocialToggle = document.getElementById(
  "employment-include-social",
);
const employmentPaymentsInput = document.getElementById("employment-payments");
const employmentWithholdingInput = document.getElementById(
  "employment-withholding",
);
const employmentModeSelect = document.getElementById("employment-mode");
const yearAlertsContainer = document.getElementById("year-alerts");
const pensionModeSelect = document.getElementById("pension-mode");
const pensionPaymentsInput = document.getElementById("pension-payments");
const pensionIncomeInput = document.getElementById("pension-income");
const pensionMonthlyIncomeInput = document.getElementById(
  "pension-monthly-income",
);
const freelanceRevenueInput = document.getElementById("freelance-revenue");
const freelanceExpensesInput = document.getElementById("freelance-expenses");
const freelanceContributionsInput = document.getElementById(
  "freelance-contributions",
);
const freelanceAuxiliaryContributionsInput = document.getElementById(
  "freelance-auxiliary-contributions",
);
const freelanceLumpSumContributionsInput = document.getElementById(
  "freelance-lump-sum-contributions",
);
const freelanceActivityStartInput = document.getElementById(
  "freelance-activity-start-year",
);
const tradeFeeToggle = document.getElementById("trade-fee-toggle");
const tradeFeeNote = document.getElementById("trade-fee-note");
const freelanceEfkaSelect = document.getElementById("freelance-efka-category");
const freelanceEfkaMonthsInput = document.getElementById("freelance-efka-months");
const freelanceEfkaHint = document.getElementById("freelance-efka-category-hint");
const freelanceTradeFeeLocationSelect = document.getElementById(
  "freelance-trade-fee-location",
);
const freelanceTradeFeeHint = document.getElementById("freelance-trade-fee-hint");
const freelanceYearsActiveInput = document.getElementById("freelance-years-active");
const freelanceEfkaSummary = document.getElementById("freelance-efka-summary");
const bracketSummaryElements = Array.from(
  document.querySelectorAll("[data-bracket-summary]"),
);
const bracketSummaryBySection = new Map();
bracketSummaryElements.forEach((element) => {
  const section = element.getAttribute("data-bracket-summary");
  if (!section) {
    return;
  }
  const content =
    element.querySelector("[data-bracket-summary-content]") || element;
  bracketSummaryBySection.set(section, { element, content });
});
const rentalIncomeInput = document.getElementById("rental-income");
const rentalExpensesInput = document.getElementById("rental-expenses");
const investmentFieldsContainer = document.getElementById("investment-fields");
const agriculturalRevenueInput = document.getElementById("agricultural-revenue");
const agriculturalExpensesInput = document.getElementById("agricultural-expenses");
const agriculturalProfessionalFarmerInput = document.getElementById(
  "agricultural-professional-farmer",
);
const otherIncomeInput = document.getElementById("other-income");
const deductionsDonationsInput = document.getElementById("deductions-donations");
const deductionsMedicalInput = document.getElementById("deductions-medical");
const deductionsEducationInput = document.getElementById("deductions-education");
const deductionsInsuranceInput = document.getElementById("deductions-insurance");
const enfiaInput = document.getElementById("enfia-due");
const luxuryInput = document.getElementById("luxury-due");
const freelanceSection = document.getElementById("freelance-section");
const agriculturalSection = document.getElementById("agricultural-section");
const otherSection = document.getElementById("other-section");
const rentalSection = document.getElementById("rental-section");
const investmentSection = document.getElementById("investment-section");
const deductionsSection = document.getElementById("deductions-section");
const obligationsSection = document.getElementById("obligations-section");
const employmentSection = document.getElementById("employment-section");
const pensionSection = document.getElementById("pension-section");
const toggleFreelance = document.getElementById("toggle-freelance");
const toggleEmployment = document.getElementById("toggle-employment");
const toggleAgricultural = document.getElementById("toggle-agricultural");
const togglePension = document.getElementById("toggle-pension");
const toggleOther = document.getElementById("toggle-other");
const toggleRental = document.getElementById("toggle-rental");
const toggleInvestment = document.getElementById("toggle-investment");
const toggleDeductions = document.getElementById("toggle-deductions");
const toggleObligations = document.getElementById("toggle-obligations");
const calculatorForm = document.getElementById("calculator-form");
const calculatorStatus = document.getElementById("calculator-status");
const resultsSection = document.getElementById("calculation-results");
const sankeyWrapper = document.getElementById("sankey-wrapper");
const sankeyChart = document.getElementById("sankey-chart");
const sankeyEmptyState = document.getElementById("sankey-empty");
const sankeyLegend = sankeyWrapper
  ? sankeyWrapper.querySelector(".sankey-legend")
  : null;
const distributionWrapper = document.getElementById("distribution-wrapper");
const distributionVisual = distributionWrapper
  ? distributionWrapper.querySelector(".distribution-visual")
  : null;
const distributionChart = document.getElementById("distribution-chart");
const distributionList = document.getElementById("distribution-list");
const distributionEmptyState = document.getElementById("distribution-empty");
const summaryGrid = document.getElementById("summary-grid");
const detailsList = document.getElementById("details-list");
const clearButton = document.getElementById("clear-button");
const downloadButton = document.getElementById("download-button");
const downloadCsvButton = document.getElementById("download-csv-button");
const printButton = document.getElementById("print-button");

function lookupMessage(locale, keyParts) {
  let cursor = getFrontendCatalog(locale);
  for (const part of keyParts) {
    if (cursor && typeof cursor === "object" && part in cursor) {
      cursor = cursor[part];
    } else {
      return undefined;
    }
  }
  return cursor;
}

function formatTemplate(template, replacements) {
  return Object.entries(replacements).reduce((accumulator, [key, value]) => {
    const pattern = new RegExp(`{{\\s*${key}\\s*}}`, "g");
    return accumulator.replace(pattern, String(value));
  }, template);
}

function t(key, replacements = {}, locale = currentLocale) {
  const keyParts = key.split(".");
  const primary = lookupMessage(locale, keyParts);
  const fallback =
    locale === fallbackLocale ? undefined : lookupMessage(fallbackLocale, keyParts);
  const template =
    typeof primary === "string"
      ? primary
      : typeof fallback === "string"
      ? fallback
      : key;
  return formatTemplate(template, replacements);
}

function getCssVariable(name, fallback = "") {
  if (typeof window === "undefined") {
    return fallback;
  }
  const styles = window.getComputedStyle(document.documentElement);
  const value = styles.getPropertyValue(name);
  return value ? value.trim() : fallback;
}

function colorWithAlpha(color, alpha, fallback) {
  const trimmed = (color || "").trim();
  if (!trimmed) {
    return fallback;
  }

  if (trimmed.startsWith("#")) {
    const hex = trimmed.slice(1);
    let normalized = hex;
    if (hex.length === 3) {
      normalized = hex
        .split("")
        .map((char) => char + char)
        .join("");
    }
    if (normalized.length !== 6) {
      return fallback;
    }
    const value = Number.parseInt(normalized, 16);
    if (!Number.isFinite(value)) {
      return fallback;
    }
    const r = (value >> 16) & 255;
    const g = (value >> 8) & 255;
    const b = value & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  const rgbMatch = trimmed.match(/rgba?\(([^)]+)\)/i);
  if (rgbMatch) {
    const parts = rgbMatch[1]
      .split(",")
      .map((part) => Number.parseFloat(part.trim()))
      .filter((value) => Number.isFinite(value));
    if (parts.length >= 3) {
      const [r, g, b] = parts;
      return `rgba(${Math.max(0, Math.min(255, r))}, ${Math.max(
        0,
        Math.min(255, g),
      )}, ${Math.max(0, Math.min(255, b))}, ${alpha})`;
    }
  }

  return fallback;
}

function parseNumericValue(value) {
  const number = Number.parseFloat(value);
  return Number.isFinite(number) ? number : 0;
}

function getElementInnerWidth(element) {
  if (!element) {
    return 0;
  }

  const rect = element.getBoundingClientRect?.();
  let width = Math.round(rect?.width || element.clientWidth || 0);

  if (!width) {
    return 0;
  }

  if (
    element === sankeyWrapper &&
    typeof window !== "undefined" &&
    typeof window.getComputedStyle === "function"
  ) {
    const styles = window.getComputedStyle(element);
    width -= Math.round(
      parseNumericValue(styles.paddingLeft) +
        parseNumericValue(styles.paddingRight),
    );
  }

  return Math.max(0, width);
}

function measureSankeyAvailableWidth() {
  const primary = [sankeyChart, sankeyWrapper];

  for (const element of primary) {
    const width = getElementInnerWidth(element);
    if (width > 0) {
      return width;
    }
  }

  const fallbackElements = [];

  if (sankeyWrapper?.parentElement) {
    fallbackElements.push(sankeyWrapper.parentElement);
    if (sankeyWrapper.parentElement.parentElement) {
      fallbackElements.push(sankeyWrapper.parentElement.parentElement);
    }
  }

  if (typeof document !== "undefined") {
    if (document.documentElement) {
      fallbackElements.push(document.documentElement);
    }
    if (document.body) {
      fallbackElements.push(document.body);
    }
  }

  for (const element of fallbackElements) {
    const width = getElementInnerWidth(element);
    if (width > 0) {
      return width;
    }
  }

  return 0;
}

function computeSankeyDimensions() {
  const measuredWidth = Math.round(measureSankeyAvailableWidth());
  const fallbackWidth =
    typeof window !== "undefined" && Number.isFinite(window.innerWidth)
      ? Math.round(window.innerWidth || 0)
      : 0;
  const resolvedWidth = Math.max(
    320,
    measuredWidth > 0 ? measuredWidth : fallbackWidth || 640,
  );
  const chartHeight = Math.max(
    280,
    Math.min(520, Math.round(resolvedWidth * 0.62)),
  );

  return { width: resolvedWidth, height: chartHeight };
}

function applySankeyDimensions(plotlyInstance = sankeyPlotlyRef) {
  if (!sankeyChart) {
    return;
  }

  const { width, height } = computeSankeyDimensions();

  sankeyChart.style.minHeight = `${height}px`;
  sankeyChart.style.height = `${height}px`;
  sankeyChart.style.minWidth = "0";
  sankeyChart.style.width = "100%";

  if (plotlyInstance?.relayout && width > 0) {
    const relayoutResult = plotlyInstance.relayout(sankeyChart, {
      width,
      height,
    });

    if (typeof relayoutResult?.catch === "function") {
      relayoutResult.catch(() => {});
    }
  }

  if (plotlyInstance?.Plots?.resize) {
    plotlyInstance.Plots.resize(sankeyChart);
  }
}

function ensureSankeyResizeHandlers() {
  if (!sankeyChart || typeof window === "undefined") {
    return;
  }

  const handleResize = () => {
    if (!sankeyChart || sankeyWrapper?.hidden) {
      return;
    }
    applySankeyDimensions();
  };

  if (!sankeyWindowResizeHandler) {
    sankeyWindowResizeHandler = () => handleResize();
    window.addEventListener("resize", sankeyWindowResizeHandler);
  }

  if (typeof ResizeObserver === "function") {
    if (!sankeyResizeObserver) {
      sankeyResizeObserver = new ResizeObserver(() => handleResize());
    }

    sankeyResizeObserver.disconnect();
    const target = sankeyWrapper || sankeyChart;
    if (target) {
      sankeyResizeObserver.observe(target);
    }
  }
}

function ensurePlotlyLoaded() {
  if (typeof Plotly !== "undefined") {
    return Promise.resolve(Plotly);
  }

  if (plotlyLoaderPromise) {
    return plotlyLoaderPromise;
  }

  plotlyLoaderPromise = new Promise((resolve, reject) => {
    const selector = `script[${PLOTLY_SDK_ATTRIBUTE}]`;
    const existingScript = document.querySelector(selector);

    if (existingScript?.dataset.loaded === "true" && typeof Plotly !== "undefined") {
      resolve(Plotly);
      return;
    }

    const script = existingScript || document.createElement("script");
    script.src = PLOTLY_SDK_URL;
    script.async = true;
    script.setAttribute(PLOTLY_SDK_ATTRIBUTE, "true");

    const handleLoad = () => {
      script.dataset.loaded = "true";
      if (typeof Plotly !== "undefined") {
        resolve(Plotly);
      } else {
        reject(new Error("Plotly loaded without exposing a global"));
      }
    };

    const handleError = () => {
      reject(new Error("Failed to load the Plotly visualisation library"));
    };

    script.addEventListener("load", handleLoad, { once: true });
    script.addEventListener("error", handleError, { once: true });

    if (!existingScript) {
      document.head.appendChild(script);
    }
  })
    .catch((error) => {
      plotlyLoaderPromise = null;
      throw error;
    });

  return plotlyLoaderPromise;
}

function scheduleIdleWork(callback) {
  if (typeof window.requestIdleCallback === "function") {
    return window.requestIdleCallback(callback, { timeout: 500 });
  }
  return window.setTimeout(callback, 32);
}

function cancelIdleWork(handle) {
  if (handle == null) {
    return;
  }
  if (typeof window.cancelIdleCallback === "function") {
    window.cancelIdleCallback(handle);
  } else {
    window.clearTimeout(handle);
  }
}

function resolveStoredLocale(defaultLocale = "en") {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return normaliseLocaleChoice(stored || defaultLocale);
  } catch (error) {
    console.warn("Unable to access localStorage", error);
    return normaliseLocaleChoice(defaultLocale);
  }
}

function persistLocale(locale) {
  try {
    window.localStorage.setItem(STORAGE_KEY, locale);
  } catch (error) {
    console.warn("Unable to persist locale preference", error);
  }
}

function resolveStoredTheme(defaultTheme = DEFAULT_THEME) {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "dark" || stored === "light") {
      return stored;
    }
    return defaultTheme;
  } catch (error) {
    console.warn("Unable to access theme preference", error);
    return defaultTheme;
  }
}

function persistTheme(theme) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (error) {
    console.warn("Unable to persist theme preference", error);
  }
}

function loadStoredCalculatorState() {
  try {
    const raw = window.localStorage.getItem(CALCULATOR_STORAGE_KEY);
    if (!raw) {
      return null;
    }

    if (typeof raw !== "string" || !raw.trim().startsWith("{")) {
      window.localStorage.removeItem(CALCULATOR_STORAGE_KEY);
      return null;
    }

    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      window.localStorage.removeItem(CALCULATOR_STORAGE_KEY);
      return null;
    }

    const timestamp = Number(parsed.timestamp);
    if (!Number.isFinite(timestamp)) {
      window.localStorage.removeItem(CALCULATOR_STORAGE_KEY);
      return null;
    }

    if (Date.now() - timestamp > CALCULATOR_STORAGE_TTL_MS) {
      window.localStorage.removeItem(CALCULATOR_STORAGE_KEY);
      return null;
    }

    const values = parsed.values;
    if (!values || typeof values !== "object") {
      window.localStorage.removeItem(CALCULATOR_STORAGE_KEY);
      return null;
    }

    return values;
  } catch (error) {
    console.warn("Unable to load calculator state", error);
    return null;
  }
}

function captureElementValue(element) {
  if (!element) {
    return undefined;
  }

  if (element instanceof HTMLInputElement) {
    if (element.type === "checkbox") {
      return Boolean(element.checked);
    }
    if (element.type === "radio") {
      return element.checked ? element.value : undefined;
    }
    if (isNumericInputElement(element)) {
      return element.value ?? "";
    }
    return element.value ?? "";
  }

  if (element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement) {
    return element.value ?? "";
  }

  return undefined;
}

function captureCalculatorState() {
  if (!calculatorForm) {
    return {};
  }

  const values = {};
  const elements = Array.from(calculatorForm.elements || []);
  const nameUsage = buildCalculatorFormNameUsage();

  elements.forEach((element) => {
    const key = getElementPersistenceKey(element, nameUsage);
    if (!key) {
      warnMissingPersistenceKey(element);
      return;
    }

    if (element instanceof HTMLInputElement && element.type === "radio") {
      if (element.checked) {
        values[key] = element.value;
      } else if (!Object.prototype.hasOwnProperty.call(values, key)) {
        values[key] = "";
      }
      return;
    }

    const value = captureElementValue(element);
    if (value === undefined) {
      return;
    }

    values[key] = value;
  });
  return values;
}

function assignLoadedCalculatorState(values) {
  if (!values || typeof values !== "object") {
    loadedCalculatorState = null;
    return;
  }

  loadedCalculatorState = Object.assign({}, values);
}

function getStoredCalculatorValue(key) {
  if (!key) {
    return undefined;
  }

  if (
    pendingCalculatorState &&
    Object.prototype.hasOwnProperty.call(pendingCalculatorState, key)
  ) {
    return pendingCalculatorState[key];
  }

  if (
    loadedCalculatorState &&
    Object.prototype.hasOwnProperty.call(loadedCalculatorState, key)
  ) {
    return loadedCalculatorState[key];
  }

  return undefined;
}

function preserveCurrentFormValues() {
  if (!calculatorForm) {
    return;
  }

  const snapshot = captureCalculatorState();
  if (!snapshot || typeof snapshot !== "object") {
    return;
  }

  const keys = Object.keys(snapshot);
  if (!keys.length) {
    return;
  }

  pendingCalculatorState = {
    ...snapshot,
    ...(pendingCalculatorState || {}),
  };
}

function persistCalculatorState() {
  if (!calculatorForm) {
    return;
  }

  try {
    const payload = {
      timestamp: Date.now(),
      values: captureCalculatorState(),
    };
    assignLoadedCalculatorState(payload.values);
    window.localStorage.setItem(
      CALCULATOR_STORAGE_KEY,
      JSON.stringify(payload),
    );
  } catch (error) {
    console.warn("Unable to persist calculator state", error);
  } finally {
    if (calculatorStatePersistHandle) {
      window.clearTimeout(calculatorStatePersistHandle);
      calculatorStatePersistHandle = null;
    }
  }
}

function schedulePersistCalculatorState() {
  try {
    if (calculatorStatePersistHandle) {
      window.clearTimeout(calculatorStatePersistHandle);
    }
    calculatorStatePersistHandle = window.setTimeout(() => {
      persistCalculatorState();
    }, 150);
  } catch (error) {
    console.warn("Unable to schedule calculator state persistence", error);
  }
}

function resolveLocaleTag(locale) {
  if (locale === "el") {
    return "el-GR";
  }
  if (locale === "en") {
    return "en-GB";
  }
  return locale || "en-GB";
}

const NON_BREAKING_SPACE = "\u00a0";
const GROUPING_REGEX = /\B(?=(\d{3})+(?!\d))/g;
const DEFAULT_CURRENCY = "EUR";

const FALLBACK_NUMBER_FORMATS = {
  el: {
    decimal: ",",
    group: ".",
    currencyPattern: (value, { useNonBreakingSpace }) =>
      `${value}${useNonBreakingSpace ? NON_BREAKING_SPACE : " "}€`,
    percentSuffix: "%",
  },
  en: {
    decimal: ".",
    group: ",",
    currencyPattern: (value) => `€${value}`,
    percentSuffix: "%",
  },
};

const numberFormatterCache = new Map();

function getFallbackFormat(locale) {
  if (locale in FALLBACK_NUMBER_FORMATS) {
    return FALLBACK_NUMBER_FORMATS[locale];
  }
  return FALLBACK_NUMBER_FORMATS.en;
}

function getActiveLocale() {
  return normaliseLocaleChoice(currentLocale || fallbackLocale || "en");
}

function formatListForLocale(items) {
  const values = Array.isArray(items)
    ? items.filter((item) => typeof item === "string" && item.trim())
    : [];
  if (!values.length) {
    return "";
  }

  if (typeof Intl !== "undefined" && typeof Intl.ListFormat === "function") {
    try {
      const formatter = new Intl.ListFormat(getActiveLocale(), {
        style: "long",
        type: "conjunction",
      });
      return formatter.format(values);
    } catch (error) {
      console.warn("Unable to format list for locale", error);
    }
  }

  if (values.length === 1) {
    return values[0];
  }

  const conjunctionKey = "ui.list_and";
  const conjunction = t(conjunctionKey);
  const conjunctionWord =
    conjunction && conjunction !== conjunctionKey ? conjunction : "and";

  if (values.length === 2) {
    return `${values[0]} ${conjunctionWord} ${values[1]}`;
  }

  const head = values.slice(0, -1).join(", ");
  const tail = values[values.length - 1];
  return `${head}, ${conjunctionWord} ${tail}`;
}

function getNumberFormatter(locale, options) {
  if (typeof Intl === "undefined" || typeof Intl.NumberFormat === "undefined") {
    return null;
  }

  const resolvedLocale = resolveLocaleTag(locale);
  const key = [
    resolvedLocale,
    options.style || "decimal",
    options.currency || "",
    options.minimumFractionDigits ?? "",
    options.maximumFractionDigits ?? "",
    options.useGrouping === false ? "nogroup" : "group",
  ].join("|");

  if (!numberFormatterCache.has(key)) {
    try {
      numberFormatterCache.set(key, new Intl.NumberFormat(resolvedLocale, options));
    } catch (error) {
      console.warn("Unable to create number formatter", error);
      numberFormatterCache.set(key, null);
    }
  }

  return numberFormatterCache.get(key);
}

function coerceFiniteNumber(value) {
  const parsed = Number.parseFloat(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatNumberParts(value, fractionDigits, localeConfig) {
  const rounded = fractionDigits >= 0 ? Math.round(value * 10 ** fractionDigits) / 10 ** fractionDigits : value;
  const sign = rounded < 0 ? "-" : "";
  const absolute = Math.abs(rounded);
  let [integerPart, fractionPart = ""] = absolute
    .toFixed(Math.max(fractionDigits, 0))
    .split(".");
  integerPart = integerPart.replace(GROUPING_REGEX, localeConfig.group);
  if (fractionDigits > 0) {
    return {
      sign,
      integerPart,
      fractionPart,
    };
  }
  return { sign, integerPart, fractionPart: "" };
}

function formatNumber(value, {
  locale = getActiveLocale(),
  minimumFractionDigits = 0,
  maximumFractionDigits = 2,
  useNonBreakingSpace = true,
} = {}) {
  const numeric = coerceFiniteNumber(value);
  const formatter = getNumberFormatter(resolveLocaleTag(locale), {
    style: "decimal",
    minimumFractionDigits,
    maximumFractionDigits,
  });

  if (formatter) {
    let formatted = formatter.format(numeric);
    if (!useNonBreakingSpace) {
      formatted = formatted.replace(/\u00a0/g, " ");
    }
    return formatted;
  }

  const fallback = getFallbackFormat(locale);
  const parts = formatNumberParts(numeric, maximumFractionDigits, fallback);
  let fractionPart = parts.fractionPart;
  if (fractionPart && maximumFractionDigits > minimumFractionDigits) {
    fractionPart = fractionPart.replace(/0+$/, "");
  }
  if (fractionPart && minimumFractionDigits > 0) {
    while (fractionPart.length < minimumFractionDigits) {
      fractionPart += "0";
    }
  }
  const decimalPart = fractionPart
    ? `${fallback.decimal}${fractionPart}`
    : minimumFractionDigits > 0
    ? `${fallback.decimal}${"0".repeat(minimumFractionDigits)}`
    : "";
  return `${parts.sign}${parts.integerPart}${decimalPart}`;
}

function formatInteger(value, { locale = getActiveLocale() } = {}) {
  const numeric = Math.round(coerceFiniteNumber(value));
  const formatter = getNumberFormatter(resolveLocaleTag(locale), {
    style: "decimal",
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  });
  if (formatter) {
    return formatter.format(numeric);
  }
  const fallback = getFallbackFormat(locale);
  const parts = formatNumberParts(numeric, 0, fallback);
  return `${parts.sign}${parts.integerPart}`;
}

function formatCurrency(value, {
  locale = getActiveLocale(),
  useNonBreakingSpace = true,
} = {}) {
  const numeric = coerceFiniteNumber(value);
  const formatter = getNumberFormatter(resolveLocaleTag(locale), {
    style: "currency",
    currency: DEFAULT_CURRENCY,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  if (formatter) {
    let formatted = formatter.format(numeric);
    if (!useNonBreakingSpace) {
      formatted = formatted.replace(/\u00a0/g, " ");
    }
    return formatted;
  }

  const fallback = getFallbackFormat(locale);
  const parts = formatNumberParts(numeric, 2, fallback);
  const valuePart = `${parts.integerPart}${fallback.decimal}${parts.fractionPart}`;
  const formattedValue = fallback.currencyPattern(valuePart, { useNonBreakingSpace });
  return `${parts.sign}${formattedValue}`;
}

function formatPercent(value, {
  locale = getActiveLocale(),
  maximumFractionDigits = 1,
  minimumFractionDigits = 0,
  useNonBreakingSpace = true,
} = {}) {
  const numeric = coerceFiniteNumber(value);
  const formatter = getNumberFormatter(resolveLocaleTag(locale), {
    style: "percent",
    minimumFractionDigits,
    maximumFractionDigits,
  });

  if (formatter) {
    let formatted = formatter.format(numeric);
    if (!useNonBreakingSpace) {
      formatted = formatted.replace(/\u00a0/g, " ");
    }
    return formatted;
  }

  const fallback = getFallbackFormat(locale);
  const scaled = numeric * 100;
  const parts = formatNumberParts(scaled, Math.max(maximumFractionDigits, minimumFractionDigits), fallback);
  let fractionPart = parts.fractionPart;
  if (fractionPart) {
    fractionPart = fractionPart.replace(/0+$/, "");
  }
  if (fractionPart && fractionPart.length < minimumFractionDigits) {
    while (fractionPart.length < minimumFractionDigits) {
      fractionPart += "0";
    }
  }
  const decimalPart = fractionPart ? `${fallback.decimal}${fractionPart}` : "";
  return `${parts.sign}${parts.integerPart}${decimalPart}${fallback.percentSuffix}`;
}

function formatDateTime(value, { locale = getActiveLocale() } = {}) {
  if (!value) {
    return "";
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  if (typeof Intl !== "undefined" && typeof Intl.DateTimeFormat !== "undefined") {
    try {
      const formatter = new Intl.DateTimeFormat(resolveLocaleTag(locale), {
        dateStyle: "medium",
        timeStyle: "short",
      });
      return formatter.format(date);
    } catch (error) {
      console.warn("Unable to format date", error);
    }
  }
  return date.toISOString();
}

function formatList(items, localeOverride = getActiveLocale()) {
  if (!Array.isArray(items) || items.length === 0) {
    return "";
  }
  if (typeof Intl !== "undefined" && typeof Intl.ListFormat !== "undefined") {
    try {
      const formatter = new Intl.ListFormat(resolveLocaleTag(localeOverride), {
        style: "long",
        type: "conjunction",
      });
      return formatter.format(items);
    } catch (error) {
      // Fall back to manual formatting below.
    }
  }
  if (items.length === 1) {
    return items[0];
  }
  const rest = items.slice(0, -1).join(", ");
  const last = items[items.length - 1];
  const conjunction = t("ui.list_and", {}, localeOverride) || "and";
  return `${rest} ${conjunction} ${last}`;
}

function updateLocaleButtonState(locale) {
  if (!localeButtons.length) {
    return;
  }

  localeButtons.forEach((button) => {
    const value = button.dataset.localeOption || "en";
    const isActive = value === locale;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function updateThemeButtonState(theme) {
  if (!themeButtons.length) {
    return;
  }

  themeButtons.forEach((button) => {
    const value = button.dataset.themeOption || DEFAULT_THEME;
    const isActive = value === theme;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function applyTheme(theme) {
  const normalized =
    theme === "dark" || theme === "light" ? theme : DEFAULT_THEME;
  currentTheme = normalized;
  const root = document.documentElement;
  if (hasAppliedThemeOnce) {
    root.classList.add("theme-transition");
    if (themeTransitionHandle) {
      window.clearTimeout(themeTransitionHandle);
    }
    themeTransitionHandle = window.setTimeout(() => {
      root.classList.remove("theme-transition");
      themeTransitionHandle = null;
    }, 280);
  }
  root.setAttribute("data-theme", normalized);
  updateThemeButtonState(normalized);
  persistTheme(normalized);
  hasAppliedThemeOnce = true;
  const rerenderResults = () => {
    if (lastCalculation) {
      renderCalculation(lastCalculation);
    }
  };
  if (typeof window.requestAnimationFrame === "function") {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(rerenderResults);
    });
  } else {
    window.setTimeout(rerenderResults, 0);
  }
}

async function applyLocale(locale) {
  const resolved = await ensureTranslations(locale);
  currentLocale = resolved;
  persistLocale(resolved);
  document.documentElement.lang = resolved;
  updateLocaleButtonState(resolved);
  localiseStaticText();
  applyEmploymentModeLabels();
  renderYearWarnings(currentYearMetadata, {
    showPartialYearWarning: partialYearWarningActive,
  });
  preserveCurrentFormValues();
  refreshInvestmentCategories();
  refreshDeductionHints();
  populateFreelanceMetadata(currentFreelanceMetadata);
  if (lastCalculation) {
    renderCalculation(lastCalculation);
  } else {
    updateEmploymentContributionPreview([]);
  }
}

function localiseStaticText() {
  document.querySelectorAll("[data-i18n-key]").forEach((element) => {
    const key = element.getAttribute("data-i18n-key");
    if (!key) {
      return;
    }
    const message = t(key);
    if (typeof message === "string") {
      element.textContent = message;
    }
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    const key = element.getAttribute("data-i18n-placeholder");
    if (!key) {
      return;
    }
    const message = t(key);
    if (typeof message === "string" && "placeholder" in element) {
      element.placeholder = message;
    }
  });
}

function initialiseLocaleControls() {
  if (!localeButtons.length) {
    return;
  }

  localeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const value = button.dataset.localeOption || "en";
      if (normaliseLocaleChoice(value) === currentLocale) {
        return;
      }
      void applyLocale(value);
    });
  });
}

function initialiseThemeControls() {
  if (!themeButtons.length) {
    return;
  }

  themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const value = button.dataset.themeOption || DEFAULT_THEME;
      if (value === currentTheme) {
        return;
      }
      applyTheme(value);
    });
  });
}

function setCalculatorStatus(message, { isError = false } = {}) {
  if (!calculatorStatus) {
    return;
  }
  calculatorStatus.textContent = message;
  calculatorStatus.setAttribute("data-status", isError ? "error" : "info");
}

function sanitiseToggleMap(source) {
  if (!source || typeof source !== "object") {
    return {};
  }
  const toggles = {};
  Object.entries(source).forEach(([key, value]) => {
    toggles[String(key)] = Boolean(value);
  });
  return toggles;
}

function resolveStoredToggleValue(element) {
  if (!element) {
    return false;
  }

  const key = getElementPersistenceKey(element);
  if (!key) {
    return Boolean(element.defaultChecked);
  }

  const storedValue = getStoredCalculatorValue(key);
  if (storedValue !== undefined) {
    return Boolean(storedValue);
  }

  return Boolean(element.defaultChecked);
}

function syncDemographicToggleState(key, control, toggleElement, isAvailable) {
  if (control) {
    control.hidden = !isAvailable;
  }

  if (!toggleElement) {
    if (!isAvailable) {
      delete currentYearToggles[key];
    }
    return;
  }

  if (!isAvailable) {
    toggleElement.checked = Boolean(toggleElement.defaultChecked);
    delete currentYearToggles[key];
    return;
  }

  const desired = resolveStoredToggleValue(toggleElement);
  toggleElement.checked = desired;
  currentYearToggles[key] = desired;
}

function applyContributionDefaults(metadata) {
  const employmentDefaults =
    (metadata && metadata.employment && metadata.employment.defaults) || {};
  if (employmentIncludeSocialToggle) {
    if (employmentDefaults.hasOwnProperty("include_social_contributions")) {
      employmentIncludeSocialToggle.checked = Boolean(
        employmentDefaults.include_social_contributions,
      );
    } else {
      employmentIncludeSocialToggle.checked = Boolean(
        employmentIncludeSocialToggle.defaultChecked,
      );
    }
  }

  const freelanceDefaults =
    (metadata && metadata.freelance && metadata.freelance.defaults) || {};
  if (tradeFeeToggle) {
    if (freelanceDefaults.hasOwnProperty("include_trade_fee")) {
      tradeFeeToggle.checked = Boolean(freelanceDefaults.include_trade_fee);
    } else {
      tradeFeeToggle.checked = Boolean(tradeFeeToggle.defaultChecked);
    }
  }
}

function updateDemographicToggles(metadata, toggles) {
  const hasYouthToggle = Object.prototype.hasOwnProperty.call(
    toggles,
    "youth_eligibility",
  );
  syncDemographicToggleState(
    "youth_eligibility",
    youthEligibilityControl,
    youthEligibilityToggle,
    hasYouthToggle,
  );

  const hasSmallVillage = Object.prototype.hasOwnProperty.call(
    toggles,
    "small_village",
  );
  syncDemographicToggleState(
    "small_village",
    smallVillageControl,
    smallVillageToggle,
    hasSmallVillage,
  );

  const hasNewMother = Object.prototype.hasOwnProperty.call(
    toggles,
    "new_mother",
  );
  syncDemographicToggleState(
    "new_mother",
    newMotherControl,
    newMotherToggle,
    hasNewMother,
  );
}

function computeBracketRangeLabel(bracket, index, previousUpper) {
  const upper = bracket && bracket.upper;
  if (upper === null || upper === undefined) {
    return t("ui.bracket_range_final", {
      lower: formatCurrency(previousUpper),
    });
  }
  if (index === 0) {
    return t("ui.bracket_range_initial", {
      upper: formatCurrency(upper),
    });
  }
  return t("ui.bracket_range_between", {
    lower: formatCurrency(previousUpper),
    upper: formatCurrency(upper),
  });
}

function renderBracketSummary(section, brackets) {
  const target = bracketSummaryBySection.get(section);
  if (!target) {
    return;
  }
  const { element, content } = target;
  if (!content) {
    return;
  }

  const entries = Array.isArray(brackets) ? brackets : [];
  if (!entries.length) {
    content.innerHTML = "";
    element.hidden = true;
    if (element instanceof HTMLDetailsElement) {
      element.open = false;
    }
    return;
  }

  const fragment = document.createDocumentFragment();
  let previousUpper = 0;

  entries.forEach((bracket, index) => {
    if (!bracket) {
      return;
    }

    const row = document.createElement("div");
    row.className = "bracket-summary__row";

    const rangeHeading = document.createElement("h4");
    rangeHeading.className = "bracket-summary__range";
    rangeHeading.textContent = computeBracketRangeLabel(
      bracket,
      index,
      previousUpper,
    );
    row.appendChild(rangeHeading);

    if (typeof bracket.upper === "number") {
      previousUpper = bracket.upper;
    }

    const metrics = document.createElement("dl");
    metrics.className = "bracket-summary__metrics";

    const baseDt = document.createElement("dt");
    baseDt.textContent = t("ui.bracket_label_base");
    metrics.appendChild(baseDt);

    const baseDd = document.createElement("dd");
    const baseRate =
      bracket.base_rate !== undefined && bracket.base_rate !== null
        ? bracket.base_rate
        : bracket.rate;
    baseDd.textContent = formatPercent(baseRate || 0);
    metrics.appendChild(baseDd);

    const householdRates = Array.isArray(bracket.household?.rates)
      ? bracket.household.rates
      : [];
    if (householdRates.length) {
      const householdDt = document.createElement("dt");
      householdDt.textContent = t("ui.bracket_label_household");
      metrics.appendChild(householdDt);

      const householdDd = document.createElement("dd");
      const householdParts = householdRates.map((entry) =>
        t("ui.bracket_household_entry", {
          dependants: entry.dependants,
          rate: formatPercent(entry.rate),
        }),
      );
      const reductionFactor = bracket.household?.reduction_factor;
      if (reductionFactor) {
        householdParts.push(
          t("ui.bracket_household_reduction", {
            reduction: formatPercent(reductionFactor),
          }),
        );
      }
      householdDd.textContent = householdParts.join(" ");
      metrics.appendChild(householdDd);
    }

    const youthRates = Array.isArray(bracket.youth) ? bracket.youth : [];
    if (youthRates.length) {
      const youthDt = document.createElement("dt");
      youthDt.textContent = t("ui.bracket_label_youth");
      metrics.appendChild(youthDt);

      const youthDd = document.createElement("dd");
      const youthParts = youthRates.map((entry) => {
        const label = t(`ui.youth_band.${entry.band}`) || entry.band;
        const dependantRates = Array.isArray(entry.dependant_rates)
          ? entry.dependant_rates
          : [];
        const baseRate =
          entry.rate !== undefined && entry.rate !== null
            ? formatPercent(entry.rate)
            : null;
        let rateText = baseRate;
        if (dependantRates.length) {
          const dependantText = dependantRates
            .map((dependantEntry) =>
              t("ui.bracket_household_entry", {
                dependants: dependantEntry.dependants,
                rate: formatPercent(dependantEntry.rate),
              }),
            )
            .join(" ");
          rateText = baseRate ? `${baseRate} (${dependantText})` : dependantText;
        }
        return t("ui.bracket_youth_entry", {
          label,
          rate: rateText || formatPercent(0),
        });
      });
      youthDd.textContent = youthParts.join(" ");
      metrics.appendChild(youthDd);
    }

    const notes = [];
    if (bracket.pending_confirmation) {
      notes.push(t("ui.bracket_pending"));
    }
    if (bracket.estimate) {
      notes.push(t("ui.bracket_estimate"));
    }
    if (notes.length) {
      const notesDt = document.createElement("dt");
      notesDt.textContent = t("ui.bracket_label_notes");
      metrics.appendChild(notesDt);

      const notesDd = document.createElement("dd");
      notesDd.textContent = notes.join(" ");
      metrics.appendChild(notesDd);
    }

    row.appendChild(metrics);
    fragment.appendChild(row);
  });

  content.innerHTML = "";
  content.appendChild(fragment);
  element.hidden = false;
}

function renderBracketSummaries(metadata) {
  if (!bracketSummaryBySection.size) {
    return;
  }

  const sections = [
    ["employment", metadata?.employment?.brackets],
    ["pension", metadata?.pension?.brackets],
    ["freelance", metadata?.freelance?.brackets],
    ["agricultural", metadata?.agricultural?.brackets],
    ["other", metadata?.other?.brackets],
    ["rental", metadata?.rental?.brackets],
  ];

  sections.forEach(([section, brackets]) => {
    renderBracketSummary(section, brackets);
  });
}

function collectYouthBands(brackets) {
  const bands = new Set();
  if (Array.isArray(brackets)) {
    brackets.forEach((bracket) => {
      if (Array.isArray(bracket?.youth)) {
        bracket.youth.forEach((entry) => {
          if (entry?.band) {
            bands.add(String(entry.band));
          }
        });
      }
    });
  }
  return Array.from(bands);
}

function collectAllYouthBands(metadata) {
  const sections = [
    metadata?.employment?.brackets,
    metadata?.pension?.brackets,
    metadata?.freelance?.brackets,
    metadata?.agricultural?.brackets,
    metadata?.other?.brackets,
    metadata?.rental?.brackets,
  ];
  const bands = new Set();
  sections.forEach((brackets) => {
    collectYouthBands(brackets).forEach((band) => bands.add(band));
  });
  return Array.from(bands);
}

function updateYouthNotes(metadata, toggles) {
  if (!youthRatesNote) {
    return;
  }

  const hasToggle = currentYearToggleKeys.has("youth_eligibility");
  if (!metadata || !hasToggle) {
    youthRatesNote.textContent = "";
    youthRatesNote.hidden = true;
    return;
  }

  const bands = collectAllYouthBands(metadata);
  if (!bands.length) {
    youthRatesNote.textContent = "";
    youthRatesNote.hidden = true;
    return;
  }

  const labels = bands.map((band) => t(`ui.youth_band.${band}`) || band);
  const formatted = formatList(labels) || labels.join(", ");
  youthRatesNote.textContent = t("hints.youth-rates-note", {
    categories: formatted,
  });
  youthRatesNote.hidden = false;
}

function updateTekmiriaNote(metadata, toggles) {
  if (!tekmiriaNote) {
    return;
  }

  const tekmiriaConfig = metadata?.employment?.tekmiria;
  if (!tekmiriaConfig || !tekmiriaConfig.enabled) {
    tekmiriaNote.textContent = "";
    tekmiriaNote.hidden = true;
    return;
  }

  const factor = tekmiriaConfig.reduction_factor;
  if (factor === null || factor === undefined) {
    tekmiriaNote.textContent = "";
    tekmiriaNote.hidden = true;
    return;
  }

  tekmiriaNote.textContent = t("hints.tekmiria-note", {
    reduction: formatPercent(factor),
  });
  tekmiriaNote.hidden = false;
}

function updateTradeFeeNote(metadata) {
  if (!tradeFeeNote) {
    return;
  }

  const tradeFee = metadata?.freelance?.trade_fee || {};
  const standardAmount = tradeFee.standard_amount;
  const noteEnabled =
    Boolean(tradeFee.fee_sunset) ||
    (typeof standardAmount === "number" && standardAmount === 0);

  if (noteEnabled) {
    tradeFeeNote.textContent = t("hints.trade-fee-note");
    tradeFeeNote.hidden = false;
  } else {
    tradeFeeNote.textContent = "";
    tradeFeeNote.hidden = true;
  }
}

function isNumericInputElement(element) {
  return element instanceof HTMLInputElement && element.type === "number";
}

function getNumericInputs() {
  if (!calculatorForm) {
    return [];
  }
  return Array.from(calculatorForm.querySelectorAll('input[type="number"]'));
}

function isInputVisible(input) {
  if (!input) {
    return false;
  }
  if (input.hidden) {
    return false;
  }
  if (input.closest("[hidden]")) {
    return false;
  }
  if (input.closest('[aria-hidden="true"]')) {
    return false;
  }
  const control = input.closest(".form-control");
  if (control && control.hidden) {
    return false;
  }
  return true;
}

function isSectionActive(section) {
  return Boolean(section && !section.hidden);
}

function resetSectionInputs(section) {
  if (!section) {
    return;
  }
  section.querySelectorAll('input[type="number"]').forEach((input) => {
    if (!input) {
      return;
    }
    const defaultValue = input.defaultValue ?? "";
    input.value = defaultValue;
  });
  section.querySelectorAll('input[type="checkbox"]').forEach((input) => {
    if (!input) {
      return;
    }
    input.checked = Boolean(input.defaultChecked);
  });
  section.querySelectorAll("select").forEach((select) => {
    if (!select) {
      return;
    }
    const defaultValue = select.dataset.defaultValue;
    if (defaultValue !== undefined) {
      select.value = defaultValue;
    } else if (select.options.length > 0) {
      select.selectedIndex = 0;
    } else {
      select.value = "";
    }
  });
}

function hasPartialYearSelection(select) {
  if (!select || select.disabled) {
    return false;
  }
  const defaultValueRaw = select.dataset.defaultValue;
  if (!defaultValueRaw) {
    return false;
  }
  const defaultValue = Number.parseInt(defaultValueRaw, 10);
  const currentValue = Number.parseInt(select.value ?? "", 10);
  if (!Number.isFinite(defaultValue) || defaultValue <= 0) {
    return false;
  }
  if (!Number.isFinite(currentValue) || currentValue <= 0) {
    return false;
  }
  return currentValue < defaultValue;
}

function isPensionEnabled() {
  return Boolean(pensionModeSelect);
}

function shouldDisplayPartialYearWarning() {
  const employmentActive = isSectionActive(employmentSection);
  const pensionActive = isSectionActive(pensionSection);

  if (!employmentActive && !pensionActive) {
    return false;
  }
  if (employmentActive && hasPartialYearSelection(employmentPaymentsInput)) {
    return true;
  }
  if (!pensionActive) {
    return false;
  }
  if (!hasPensionEntries()) {
    return false;
  }
  return hasPartialYearSelection(pensionPaymentsInput);
}

function hasPensionEntries() {
  if (!isSectionActive(pensionSection)) {
    return false;
  }
  if (currentPensionMode === "monthly") {
    return readNumber(pensionMonthlyIncomeInput) > 0;
  }
  return readNumber(pensionIncomeInput) > 0;
}

function updatePartialYearWarningState() {
  const shouldShow = shouldDisplayPartialYearWarning();
  partialYearWarningActive = shouldShow;
  renderYearWarnings(currentYearMetadata, {
    showPartialYearWarning: shouldShow,
  });
}

function handleSectionToggle(toggle) {
  if (!toggle) {
    return;
  }
  const targetId = toggle.getAttribute("data-toggle-target");
  if (!targetId) {
    return;
  }
  const section = document.getElementById(targetId);
  if (!section) {
    return;
  }
  const isChecked = Boolean(toggle.checked);
  section.hidden = !isChecked;
  section.setAttribute("aria-hidden", String(!isChecked));
  if (!isChecked) {
    resetSectionInputs(section);
  }
  if (toggle === toggleEmployment || toggle === togglePension) {
    updatePartialYearWarningState();
  }
}

function initialiseSectionToggles() {
  const toggles = [
    toggleEmployment,
    toggleFreelance,
    toggleAgricultural,
    togglePension,
    toggleOther,
    toggleRental,
    toggleInvestment,
    toggleDeductions,
    toggleObligations,
  ];
  toggles.forEach((toggle) => {
    if (!toggle) {
      return;
    }
    handleSectionToggle(toggle);
    toggle.addEventListener("change", () => handleSectionToggle(toggle));
  });
}

function applyValueToElement(element, value) {
  if (!element) {
    return false;
  }

  if (element instanceof HTMLInputElement) {
    if (element.type === "checkbox") {
      const desired = Boolean(value);
      element.checked = desired;
      return element.checked === desired;
    }
    if (isNumericInputElement(element)) {
      const stringValue = value === null || value === undefined ? "" : String(value);
      element.value = stringValue;
      return element.value === stringValue;
    }
    const stringValue = value === null || value === undefined ? "" : String(value);
    element.value = stringValue;
    return element.value === stringValue;
  }

  if (element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement) {
    const stringValue = value === null || value === undefined ? "" : String(value);
    const previousValue = element.value;
    element.value = stringValue;
    if (element.value !== stringValue) {
      // Restore the previous value when the desired option is unavailable.
      element.value = previousValue;
      return false;
    }
    return true;
  }

  return false;
}

function applyStoredValueToKey(key, value) {
  const elements = getElementsByPersistenceKey(key);
  if (!elements.length) {
    return false;
  }

  if (elements.length === 1) {
    return applyValueToElement(elements[0], value);
  }

  const primary = elements[0];
  if (primary instanceof HTMLInputElement && primary.type === "radio") {
    const desiredValue =
      value === null || value === undefined ? "" : String(value);
    let matched = false;
    elements.forEach((element) => {
      if (!(element instanceof HTMLInputElement)) {
        return;
      }
      const isMatch = element.value === desiredValue;
      element.checked = isMatch;
      if (isMatch) {
        matched = true;
      }
    });
    return matched || desiredValue === "";
  }

  let applied = false;
  elements.forEach((element) => {
    if (applied) {
      return;
    }
    applied = applyValueToElement(element, value);
  });
  return applied;
}

function applyPendingCalculatorState() {
  if (!pendingCalculatorState) {
    return;
  }

  const sourceState = pendingCalculatorState;
  const remaining = {};
  let yearUpdated = false;
  const nameUsage = buildCalculatorFormNameUsage();
  const yearKey = getElementPersistenceKey(yearSelect, nameUsage);
  const yearKeyCandidates = new Set();
  if (yearKey) {
    yearKeyCandidates.add(yearKey);
  }
  if (yearSelect && typeof yearSelect.id === "string" && yearSelect.id) {
    yearKeyCandidates.add(yearSelect.id);
  }
  const pensionModeKey = getElementPersistenceKey(pensionModeSelect, nameUsage);
  const pensionModeKeys = new Set();
  if (pensionModeKey) {
    pensionModeKeys.add(pensionModeKey);
  }
  if (
    pensionModeSelect &&
    typeof pensionModeSelect.id === "string" &&
    pensionModeSelect.id
  ) {
    pensionModeKeys.add(pensionModeSelect.id);
  }
  const employmentModeKey = getElementPersistenceKey(
    employmentModeSelect,
    nameUsage,
  );
  const employmentModeKeys = new Set();
  if (employmentModeKey) {
    employmentModeKeys.add(employmentModeKey);
  }
  if (
    employmentModeSelect &&
    typeof employmentModeSelect.id === "string" &&
    employmentModeSelect.id
  ) {
    employmentModeKeys.add(employmentModeSelect.id);
  }

  const pickStoredValue = (keys) => {
    if (!sourceState || !keys || !keys.size) {
      return undefined;
    }
    for (const candidate of keys) {
      if (Object.prototype.hasOwnProperty.call(sourceState, candidate)) {
        return sourceState[candidate];
      }
    }
    return undefined;
  };

  Object.entries(sourceState).forEach(([key, storedValue]) => {
    const applied = applyStoredValueToKey(key, storedValue);
    if (!applied) {
      remaining[key] = storedValue;
      return;
    }

    if (yearKeyCandidates.has(key)) {
      yearUpdated = true;
    }
  });

  pendingCalculatorState = Object.keys(remaining).length ? remaining : null;

  if (yearUpdated) {
    const selectedYear = Number.parseInt(yearSelect?.value ?? "", 10);
    if (Number.isFinite(selectedYear)) {
      applyYearMetadata(selectedYear);
    }
  }

  if (pensionModeSelect) {
    if (pensionModeKeys.size) {
      const storedValue = pickStoredValue(pensionModeKeys);
      if (storedValue !== undefined) {
        updatePensionMode(storedValue || "annual");
      } else {
        updatePensionMode(pensionModeSelect.value || "annual");
      }
    } else {
      updatePensionMode(pensionModeSelect.value || "annual");
    }
  }

  if (employmentModeSelect) {
    if (employmentModeKeys.size) {
      const storedValue = pickStoredValue(employmentModeKeys);
      if (storedValue !== undefined) {
        updateEmploymentMode(storedValue || "annual");
      } else {
        updateEmploymentMode(employmentModeSelect.value || "annual");
      }
    } else {
      updateEmploymentMode(employmentModeSelect.value || "annual");
    }
  } else {
    updateEmploymentMode(currentEmploymentMode);
  }

  const toggles = [
    toggleEmployment,
    toggleFreelance,
    toggleAgricultural,
    toggleOther,
    toggleRental,
    toggleInvestment,
    toggleDeductions,
    toggleObligations,
  ];
  toggles.forEach((toggle) => {
    if (toggle && toggle.hasAttribute("data-toggle-target")) {
      handleSectionToggle(toggle);
    }
  });

  updateFreelanceCategoryHint();
  updateTradeFeeHint();
}

function handleCalculatorStateChange() {
  schedulePersistCalculatorState();
}

function updateSectionMode(section, mode, defaultMode = "") {
  const requestedMode = (mode || "").toString().toLowerCase();
  const fallbackMode = (defaultMode || "").toString().toLowerCase();
  const desiredMode = requestedMode || fallbackMode;
  document
    .querySelectorAll(`.form-control[data-section="${section}"]`)
    .forEach((control) => {
      const controlMode = control.getAttribute("data-mode");
      if (!controlMode) {
        return;
      }
      const isVisible = controlMode.toLowerCase() === desiredMode;
      control.hidden = !isVisible;
      if (!isVisible) {
        const input = control.querySelector("input");
        if (input) {
          clearFieldError(input);
        }
      }
    });
}

function updatePensionMode(mode) {
  currentPensionMode = mode === "monthly" ? "monthly" : "annual";
  if (pensionModeSelect) {
    pensionModeSelect.value = currentPensionMode;
  }
  updateSectionMode("pension", currentPensionMode, "annual");
}

function updateEmploymentMode(mode) {
  currentEmploymentMode = mode === "monthly" ? "monthly" : "annual";
  if (employmentModeSelect) {
    employmentModeSelect.value = currentEmploymentMode;
  }
  updateSectionMode("employment", currentEmploymentMode, "annual");
}

function populatePayrollSelect(select, payrollConfig) {
  if (!select) {
    return;
  }

  select.innerHTML = "";
  if (!payrollConfig) {
    select.value = "";
    select.disabled = true;
    return;
  }

  const { allowed_payments_per_year: allowed, default_payments_per_year: fallback } =
    payrollConfig;
  if (!Array.isArray(allowed) || allowed.length === 0) {
    select.value = "";
    select.disabled = true;
    return;
  }

  allowed.forEach((value) => {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = String(value);
    select.appendChild(option);
  });

  const defaultValue = fallback || allowed[allowed.length - 1];
  select.value = String(defaultValue);
  select.dataset.defaultValue = String(defaultValue);
  select.disabled = false;
}

function getPayrollMetadata(section) {
  if (!currentYearMetadata) {
    return null;
  }
  if (section === "employment") {
    return currentYearMetadata.employment || null;
  }
  if (section === "pension") {
    return currentYearMetadata.pension || null;
  }
  return null;
}

function resolvePaymentsValue(select, section) {
  const raw = Number.parseInt(select?.value ?? "", 10);
  if (Number.isFinite(raw) && raw > 0) {
    return raw;
  }
  const metadata = getPayrollMetadata(section);
  const fallback = metadata?.payroll?.default_payments_per_year;
  return typeof fallback === "number" && fallback > 0 ? fallback : undefined;
}

function renderYearWarnings(metadata, options = {}) {
  if (!yearAlertsContainer) {
    return;
  }

  yearAlertsContainer.innerHTML = "";
  const warnings = Array.isArray(metadata?.warnings) ? metadata.warnings : [];
  const showPartialWarning =
    options.showPartialYearWarning ?? partialYearWarningActive;

  let renderedCount = 0;

  warnings.forEach((warning) => {
    if (!warning) {
      return;
    }

    const warningId = typeof warning.id === "string" ? warning.id : "";
    if (
      warningId === "employment.partial_year_review" &&
      !showPartialWarning
    ) {
      return;
    }

    const severity = String(warning.severity || "info").toLowerCase();
    const classes = ["alert"];
    if (severity === "warning") {
      classes.push("alert--warning");
    } else if (severity === "error") {
      classes.push("alert--error");
    }

    const alert = document.createElement("div");
    alert.className = classes.join(" ");

    const message = document.createElement("p");
    message.className = "alert__message";
    const replacements = {};
    if (metadata?.year) {
      replacements.year = metadata.year;
    }
    if (Array.isArray(warning.applies_to) && warning.applies_to.length) {
      replacements.scope = warning.applies_to.join(", ");
    }
    const text = warning.message_key
      ? t(warning.message_key, replacements)
      : "";
    message.textContent = text || warning.message_key || "";
    alert.appendChild(message);

    if (warning.documentation_url) {
      const actions = document.createElement("div");
      actions.className = "alert__actions";
      const link = document.createElement("a");
      link.href = warning.documentation_url;
      link.target = "_blank";
      link.rel = "noreferrer noopener";
      const labelKey = warning.documentation_key || "warnings.learn_more";
      link.textContent = t(labelKey);
      actions.appendChild(link);
      alert.appendChild(actions);
    }

    yearAlertsContainer.appendChild(alert);
    renderedCount += 1;
  });

  yearAlertsContainer.hidden = renderedCount === 0;
}

function applyYearMetadata(year) {
  if (isApplyingYearMetadata) {
    return;
  }

  isApplyingYearMetadata = true;
  try {
    currentYearMetadata = yearMetadataByYear.get(year) || null;
    currentYearToggles = sanitiseToggleMap(
      (currentYearMetadata &&
        (currentYearMetadata.toggles || currentYearMetadata.meta?.toggles)) ||
        {},
    );
    currentYearToggleKeys = new Set(Object.keys(currentYearToggles));
    renderYearWarnings(currentYearMetadata, {
      showPartialYearWarning: partialYearWarningActive,
    });
    populatePayrollSelect(
      employmentPaymentsInput,
      currentYearMetadata?.employment?.payroll || null,
    );
    populatePayrollSelect(
      pensionPaymentsInput,
      currentYearMetadata?.pension?.payroll || null,
    );

    applyContributionDefaults(currentYearMetadata);
    updateDemographicToggles(currentYearMetadata, currentYearToggles);
    renderBracketSummaries(currentYearMetadata);
    updateYouthNotes(currentYearMetadata, currentYearToggles);
    updateTekmiriaNote(currentYearMetadata, currentYearToggles);

    updateEmploymentMode(currentEmploymentMode);
    updatePensionMode(currentPensionMode);
    populateFreelanceMetadata(currentYearMetadata?.freelance || null);
    updateTradeFeeNote(currentYearMetadata);
    applyPendingCalculatorState();
    updatePartialYearWarningState();
  } finally {
    isApplyingYearMetadata = false;
  }
}

function buildDownloadFilename(extension) {
  const year = lastCalculation?.meta?.year ?? "summary";
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `greektax-${year}-${timestamp}.${extension}`;
}

function clearFormHints() {
  document.querySelectorAll(".form-control .form-hint").forEach((element) => {
    if (element.dataset.staticHint === "true") {
      return;
    }
    element.remove();
  });
  document.querySelectorAll(".form-control .form-allowances").forEach((element) => {
    element.remove();
  });
}

function applyHintToField(hint) {
  if (!hint || !hint.input_id) {
    return;
  }

  const input = document.getElementById(hint.input_id);
  if (!input) {
    return;
  }

  const container = input.closest(".form-control");
  if (!container) {
    return;
  }

  let hintElement = container.querySelector(".form-hint");
  if (!hintElement) {
    hintElement = document.createElement("p");
    hintElement.className = "form-hint";
    container.appendChild(hintElement);
  }

  if (hint.description) {
    hintElement.textContent = hint.description;
    hintElement.hidden = false;
  } else {
    hintElement.textContent = "";
    hintElement.hidden = true;
  }

  let allowancesContainer = container.querySelector(".form-allowances");
  if (Array.isArray(hint.allowances) && hint.allowances.length) {
    if (!allowancesContainer) {
      allowancesContainer = document.createElement("div");
      allowancesContainer.className = "form-allowances";
      container.appendChild(allowancesContainer);
    }
    allowancesContainer.innerHTML = "";
    hint.allowances.forEach((allowance) => {
      if (!allowance) {
        return;
      }
      const wrapper = document.createElement("div");
      wrapper.className = "allowance-item";

      if (allowance.label) {
        const heading = document.createElement("strong");
        heading.textContent = allowance.label;
        wrapper.appendChild(heading);
      }

      if (allowance.description) {
        const description = document.createElement("p");
        description.textContent = allowance.description;
        wrapper.appendChild(description);
      }

      if (Array.isArray(allowance.thresholds) && allowance.thresholds.length) {
        const list = document.createElement("ul");
        allowance.thresholds.forEach((threshold) => {
          if (!threshold) {
            return;
          }
          const item = document.createElement("li");
          const parts = [];
          if (threshold.amount !== undefined) {
            parts.push(formatCurrency(threshold.amount));
          }
          if (threshold.percentage !== undefined) {
            parts.push(formatPercent(threshold.percentage));
          }
          let text = threshold.label || "";
          if (parts.length) {
            text = `${text}${text ? ": " : ""}${parts.join(" / ")}`;
          }
          if (threshold.notes) {
            text = `${text}${text ? " — " : ""}${threshold.notes}`;
          }
          item.textContent = text;
          list.appendChild(item);
        });
        wrapper.appendChild(list);
      }

      allowancesContainer.appendChild(wrapper);
    });
    allowancesContainer.hidden = false;
  } else if (allowancesContainer) {
    allowancesContainer.remove();
  }

  const validation = hint.validation || {};
  if (validation.type === "integer") {
    input.setAttribute("step", "1");
  }
  if (validation.type === "currency" && !input.getAttribute("step")) {
    input.setAttribute("step", "0.01");
  }
  if (validation.min !== undefined) {
    input.setAttribute("min", String(validation.min));
  }
  if (validation.max !== undefined) {
    input.setAttribute("max", String(validation.max));
  }
}

async function loadYearOptions() {
  if (!yearSelect) {
    return;
  }

  setCalculatorStatus(t("status.loading_years"));
  try {
    const response = await fetch(CONFIG_YEARS_ENDPOINT);
    if (!response.ok) {
      throw new Error(`Unable to load years (${response.status})`);
    }

    const payload = await response.json();
    const years = Array.isArray(payload.years) ? payload.years : [];
    yearSelect.innerHTML = "";
    yearMetadataByYear.clear();

    years.forEach((entry) => {
      const option = document.createElement("option");
      option.value = String(entry.year);
      option.textContent = `${entry.year}`;
      yearSelect.appendChild(option);
      if (entry && typeof entry.year === "number") {
        yearMetadataByYear.set(entry.year, entry);
      }
    });

    const currentYear = new Date().getFullYear();
    let selectedYear = null;

    if (yearMetadataByYear.has(currentYear)) {
      yearSelect.value = String(currentYear);
      selectedYear = currentYear;
    } else if (
      payload.default_year &&
      yearMetadataByYear.has(Number.parseInt(payload.default_year, 10))
    ) {
      const defaultYear = Number.parseInt(payload.default_year, 10);
      yearSelect.value = String(defaultYear);
      selectedYear = defaultYear;
    } else if (years.length) {
      const firstYear = Number.parseInt(years[0]?.year ?? "", 10);
      if (Number.isFinite(firstYear)) {
        yearSelect.value = String(firstYear);
        selectedYear = firstYear;
      }
    }

    if (selectedYear === null) {
      const parsed = Number.parseInt(yearSelect.value ?? "", 10);
      if (Number.isFinite(parsed)) {
        selectedYear = parsed;
      }
    }

    if (selectedYear !== null) {
      applyYearMetadata(selectedYear);
    }

    setCalculatorStatus(t("status.ready"));
  } catch (error) {
    console.error("Failed to load year metadata", error);
    setCalculatorStatus(t("status.year_error"), { isError: true });
  }
}

async function refreshApplicationVersion() {
  const versionElement = document.querySelector("[data-app-version]");
  if (!versionElement) {
    return;
  }

  const fallbackText =
    versionElement.dataset.versionFallback?.trim() || versionElement.textContent || "";

  try {
    const response = await fetch(CONFIG_META_ENDPOINT, { credentials: "omit" });
    if (!response.ok) {
      throw new Error(`Unable to load application metadata (${response.status})`);
    }

    const payload = await response.json();
    const version =
      typeof payload?.version === "string" ? payload.version.trim() : "";
    if (version) {
      versionElement.textContent = version;
      return;
    }
  } catch (error) {
    console.error("Failed to refresh application metadata", error);
  }

  versionElement.textContent = fallbackText || "unavailable";
}

function renderInvestmentFields(categories) {
  if (!investmentFieldsContainer) {
    return;
  }

  preserveCurrentFormValues();
  investmentFieldsContainer.innerHTML = "";
  if (!categories.length) {
    const message = document.createElement("p");
    message.textContent = t("forms.no_investment_categories");
    investmentFieldsContainer.appendChild(message);
    return;
  }

  categories.forEach((category) => {
    const wrapper = document.createElement("div");
    wrapper.className = "form-control";

    const label = document.createElement("label");
    label.setAttribute("for", `investment-${category.id}`);
    label.textContent = `${category.label} (${formatPercent(category.rate)})`;

    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.step = "0.01";
    input.id = `investment-${category.id}`;
    input.name = `investment.${category.id}`;
    input.value = "0";

    wrapper.appendChild(label);
    wrapper.appendChild(input);
    investmentFieldsContainer.appendChild(wrapper);
  });

  applyPendingCalculatorState();
}

async function refreshInvestmentCategories() {
  if (!yearSelect) {
    return;
  }

  const year = Number.parseInt(yearSelect.value, 10);
  if (!Number.isFinite(year)) {
    renderInvestmentFields([]);
    return;
  }

  try {
    const response = await fetch(
      CONFIG_INVESTMENT_ENDPOINT(year, currentLocale || "en"),
    );
    if (!response.ok) {
      throw new Error(`Unable to load investment categories (${response.status})`);
    }

    const payload = await response.json();
    currentInvestmentCategories = Array.isArray(payload.categories)
      ? payload.categories
      : [];
    renderInvestmentFields(currentInvestmentCategories);
  } catch (error) {
    console.error("Failed to load investment categories", error);
    currentInvestmentCategories = [];
    renderInvestmentFields([]);
  }
}

function getFreelanceCategoryById(id) {
  if (!id || !currentFreelanceMetadata) {
    return null;
  }

  const categories = currentFreelanceMetadata.efka_categories;
  if (!Array.isArray(categories)) {
    return null;
  }

  return categories.find((entry) => entry && entry.id === id) || null;
}

function parseFreelanceContributionMonths() {
  if (!freelanceEfkaMonthsInput) {
    return 0;
  }

  const value = Number.parseInt(freelanceEfkaMonthsInput.value ?? "", 10);
  if (!Number.isFinite(value) || value < 0) {
    return 0;
  }
  return value;
}

function getFreelanceStartYear() {
  if (!freelanceActivityStartInput) {
    return null;
  }

  const rawValue = (freelanceActivityStartInput.value ?? "").trim();
  if (!rawValue) {
    return null;
  }

  const parsed = Number.parseInt(rawValue, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }

  return parsed;
}

function syncFreelanceActivityDerivedState() {
  const startYear = getFreelanceStartYear();
  let yearsActive = null;
  const selectedYear = Number.parseInt(yearSelect?.value ?? "", 10);
  if (Number.isFinite(selectedYear) && startYear !== null) {
    yearsActive = selectedYear - startYear + 1;
    if (yearsActive < 0) {
      yearsActive = 0;
    }
  }

  derivedFreelanceYearsActive = yearsActive;

  if (freelanceYearsActiveInput) {
    if (yearsActive === null || yearsActive <= 0) {
      freelanceYearsActiveInput.value = "0";
    } else {
      freelanceYearsActiveInput.value = String(yearsActive);
    }
  }

  const reductionYears =
    currentFreelanceMetadata?.trade_fee?.newly_self_employed_reduction_years ?? null;
  derivedFreelanceNewlySelfEmployed =
    reductionYears !== null &&
    reductionYears !== undefined &&
    yearsActive !== null &&
    yearsActive > 0 &&
    yearsActive <= reductionYears;
}

function updateFreelanceCategoryHint() {
  const categoryId = freelanceEfkaSelect?.value || "";
  const category = getFreelanceCategoryById(categoryId);
  const months = parseFreelanceContributionMonths();

  const summaryMessages = [];
  if (category && months >= 0) {
    const baseMonthly = Number(category.monthly_amount || 0);
    const auxiliaryMonthly = Number(category.auxiliary_monthly_amount || 0);
    const lumpMonthly = Number(category.lump_sum_monthly_amount || 0);
    const totalMonthly = baseMonthly + auxiliaryMonthly + lumpMonthly;

    if (baseMonthly > 0) {
      summaryMessages.push(
        t("hints.freelance-efka-summary-base", {
          monthly: formatCurrency(baseMonthly),
          months,
          total: formatCurrency(baseMonthly * months),
        }),
      );
    }

    if (auxiliaryMonthly > 0) {
      summaryMessages.push(
        t("hints.freelance-efka-summary-auxiliary", {
          monthly: formatCurrency(auxiliaryMonthly),
          months,
          total: formatCurrency(auxiliaryMonthly * months),
        }),
      );
    }

    if (lumpMonthly > 0) {
      summaryMessages.push(
        t("hints.freelance-efka-summary-lump", {
          monthly: formatCurrency(lumpMonthly),
          months,
          total: formatCurrency(lumpMonthly * months),
        }),
      );
    }

    if (totalMonthly > 0) {
      summaryMessages.push(
        t("hints.freelance-efka-summary-total", {
          total: formatCurrency(totalMonthly * months),
        }),
      );
    }
    if (category?.estimate) {
      const estimateSummary = t("hints.freelance-efka-summary-estimate");
      if (estimateSummary) {
        summaryMessages.push(estimateSummary);
      }
    }
  }

  if (freelanceEfkaSummary) {
    if (summaryMessages.length > 0) {
      freelanceEfkaSummary.textContent = summaryMessages.join(" ");
      freelanceEfkaSummary.hidden = false;
    } else {
      const message = t("hints.freelance-efka-summary-empty");
      if (message) {
        freelanceEfkaSummary.textContent = message;
        freelanceEfkaSummary.hidden = false;
      } else {
        freelanceEfkaSummary.textContent = "";
        freelanceEfkaSummary.hidden = true;
      }
    }
  }

  if (freelanceEfkaHint) {
    const messages = [];
    if (category?.description_key) {
      const description = t(category.description_key);
      if (description) {
        messages.push(description);
      }
    } else {
      const defaultMessage = t("hints.freelance-efka-category");
      if (!category && defaultMessage) {
        messages.push(defaultMessage);
      }
    }
    if (category?.estimate) {
      const estimateMessage = t("hints.freelance-efka-estimate");
      if (estimateMessage) {
        messages.push(estimateMessage);
      }
    }
    if (messages.length) {
      freelanceEfkaHint.textContent = messages.join(" ");
      freelanceEfkaHint.hidden = false;
    } else {
      freelanceEfkaHint.textContent = "";
      freelanceEfkaHint.hidden = true;
    }
  }
}

function updateTradeFeeHint() {
  if (!freelanceTradeFeeHint) {
    return;
  }

  const tradeFee = currentFreelanceMetadata?.trade_fee || {};
  let amount = tradeFee.standard_amount ?? null;
  const location = freelanceTradeFeeLocationSelect?.value || "standard";
  if (
    location === "reduced" &&
    tradeFee.reduced_amount !== null &&
    tradeFee.reduced_amount !== undefined
  ) {
    amount = tradeFee.reduced_amount;
  }

  const messages = [];
  const baseHint = t("hints.freelance-trade-fee-location");
  if (baseHint) {
    messages.push(baseHint);
  }

  if (typeof amount === "number" && Number.isFinite(amount)) {
    if (amount > 0) {
      messages.push(
        t("hints.freelance-trade-fee", { amount: formatCurrency(amount) }),
      );
    } else if (amount === 0) {
      messages.push(t("hints.freelance-trade-fee-waived"));
    }
  }

  if (tradeFee.newly_self_employed_reduction_years) {
    const reductionYears = tradeFee.newly_self_employed_reduction_years;
    messages.push(
      t("hints.freelance-trade-fee-new", {
        years: reductionYears,
      }),
    );
    if (derivedFreelanceYearsActive !== null && derivedFreelanceYearsActive > 0) {
      if (derivedFreelanceNewlySelfEmployed) {
        messages.push(t("hints.freelance-trade-fee-new-eligible"));
      } else if (derivedFreelanceYearsActive > reductionYears) {
        messages.push(
          t("hints.freelance-trade-fee-new-expired", { years: reductionYears }),
        );
      }
    }
  }

  if (tradeFee.sunset?.description_key) {
    const replacements = {};
    if (tradeFee.sunset.year) {
      replacements.year = tradeFee.sunset.year;
    }
    if (tradeFee.sunset.status_key) {
      replacements.status = t(tradeFee.sunset.status_key);
    }
    messages.push(t(tradeFee.sunset.description_key, replacements));
  }

  const combined = messages.join(" ");
  freelanceTradeFeeHint.textContent = combined;
  freelanceTradeFeeHint.hidden = !combined;
}

function populateFreelanceMetadata(metadata) {
  currentFreelanceMetadata = metadata || null;

  preserveCurrentFormValues();

  if (freelanceEfkaSelect) {
    const previousValue = freelanceEfkaSelect.value || "";
    freelanceEfkaSelect.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = t("fields.freelance-efka-category-placeholder");
    freelanceEfkaSelect.appendChild(placeholder);

    const categories = Array.isArray(metadata?.efka_categories)
      ? metadata.efka_categories
      : [];

    categories.forEach((category) => {
      if (!category) {
        return;
      }
      const option = document.createElement("option");
      option.value = category.id;
      const label = t(category.label_key);
      const monthly = formatCurrency(category.monthly_amount || 0);
      let optionLabel = `${label} (${monthly}/month)`;
      if (category.estimate) {
        optionLabel = `${optionLabel} ${t("ui.estimate_tag")}`;
      }
      option.textContent = optionLabel;
      option.dataset.monthlyAmount = String(category.monthly_amount || 0);
      option.dataset.auxiliaryMonthlyAmount = String(
        category.auxiliary_monthly_amount || 0,
      );
      if (category.description_key) {
        option.dataset.descriptionKey = category.description_key;
      }
      option.dataset.estimate = String(Boolean(category.estimate));
      freelanceEfkaSelect.appendChild(option);
    });

    if (previousValue) {
      freelanceEfkaSelect.value = previousValue;
      if (freelanceEfkaSelect.value !== previousValue) {
        freelanceEfkaSelect.selectedIndex = 0;
      }
    } else {
      freelanceEfkaSelect.selectedIndex = 0;
    }
  }

  if (freelanceTradeFeeLocationSelect) {
    const previousLocation = freelanceTradeFeeLocationSelect.value || "standard";
    freelanceTradeFeeLocationSelect.innerHTML = "";

    const tradeFee = metadata?.trade_fee || {};

    const standardOption = document.createElement("option");
    standardOption.value = "standard";
    standardOption.textContent = t("fields.freelance-trade-fee-standard");
    freelanceTradeFeeLocationSelect.appendChild(standardOption);

    if (tradeFee.reduced_amount !== null && tradeFee.reduced_amount !== undefined) {
      const reducedOption = document.createElement("option");
      reducedOption.value = "reduced";
      reducedOption.textContent = t("fields.freelance-trade-fee-reduced");
      freelanceTradeFeeLocationSelect.appendChild(reducedOption);
    }

    freelanceTradeFeeLocationSelect.value = previousLocation;
    if (!freelanceTradeFeeLocationSelect.value) {
      freelanceTradeFeeLocationSelect.value = "standard";
    }
  }

  applyPendingCalculatorState();
  syncFreelanceActivityDerivedState();
  updateFreelanceCategoryHint();
  updateTradeFeeHint();
}

async function refreshDeductionHints() {
  if (!yearSelect) {
    return;
  }

  const year = Number.parseInt(yearSelect.value, 10);
  if (!Number.isFinite(year)) {
    clearFormHints();
    currentDeductionHints = [];
    dynamicFieldLabels = {};
    deductionValidationByInput = {};
    return;
  }

  try {
    const response = await fetch(
      CONFIG_DEDUCTIONS_ENDPOINT(year, currentLocale || "en"),
    );
    if (!response.ok) {
      throw new Error(`Unable to load deduction hints (${response.status})`);
    }

    const payload = await response.json();
    currentDeductionHints = Array.isArray(payload.hints) ? payload.hints : [];
    dynamicFieldLabels = {};
    deductionValidationByInput = {};
    clearFormHints();

    currentDeductionHints.forEach((hint) => {
      if (hint && hint.input_id) {
        dynamicFieldLabels[hint.input_id] = hint.label;
        deductionValidationByInput[hint.input_id] = hint.validation || {};
      }
      applyHintToField(hint);
    });
  } catch (error) {
    console.error("Failed to load deduction hints", error);
    currentDeductionHints = [];
    dynamicFieldLabels = {};
    deductionValidationByInput = {};
    clearFormHints();
  }
}

function getFieldLabel(input) {
  if (!input) {
    return "";
  }

  if (dynamicFieldLabels[input.id]) {
    return dynamicFieldLabels[input.id];
  }

  const messages = getMessagesSection(currentLocale, "fields");
  if (messages[input.id]) {
    return messages[input.id];
  }

  const fallbackMessages = getMessagesSection(fallbackLocale, "fields");
  if (fallbackMessages[input.id]) {
    return fallbackMessages[input.id];
  }

  const label = input.labels && input.labels[0];
  if (label) {
    return label.textContent.trim();
  }

  return input.name || input.id;
}

function clearFieldError(input) {
  if (!input) {
    return;
  }

  const container = input.closest(".form-control");
  if (!container) {
    return;
  }

  container.classList.remove("has-error");
  input.removeAttribute("aria-invalid");

  const errorElement = container.querySelector(".form-error");
  if (errorElement) {
    errorElement.remove();
  }
}

function setFieldError(input, message) {
  if (!input) {
    return;
  }

  const container = input.closest(".form-control");
  if (!container) {
    return;
  }

  container.classList.add("has-error");
  input.setAttribute("aria-invalid", "true");

  let errorElement = container.querySelector(".form-error");
  if (!errorElement) {
    errorElement = document.createElement("p");
    errorElement.className = "form-error";
    container.appendChild(errorElement);
  }
  errorElement.textContent = message;
}

function validateNumberInput(input) {
  if (!isNumericInputElement(input)) {
    return true;
  }

  if (!isInputVisible(input)) {
    return true;
  }

  clearFieldError(input);

  const rawValue = (input.value ?? "").trim();
  if (rawValue === "") {
    return true;
  }

  const number = input.valueAsNumber;
  const fieldLabel = getFieldLabel(input);

  if (!Number.isFinite(number)) {
    setFieldError(input, t("errors.invalid_number", { field: fieldLabel }));
    return false;
  }

  if (number < 0) {
    setFieldError(input, t("errors.negative_number", { field: fieldLabel }));
    return false;
  }

  const minAttr = input.getAttribute("min");
  if (minAttr !== null) {
    const minValue = Number.parseFloat(minAttr);
    if (Number.isFinite(minValue) && number < minValue) {
      setFieldError(
        input,
        t("errors.min_number", { field: fieldLabel, min: formatNumber(minValue) }),
      );
      return false;
    }
  }

  const maxAttr = input.getAttribute("max");
  if (maxAttr !== null) {
    const maxValue = Number.parseFloat(maxAttr);
    if (Number.isFinite(maxValue) && number > maxValue) {
      setFieldError(
        input,
        t("errors.max_number", { field: fieldLabel, max: formatNumber(maxValue) }),
      );
      return false;
    }
  }

  const validation = deductionValidationByInput[input.id] || {};
  if (validation.type === "integer" && !Number.isInteger(number)) {
    setFieldError(input, t("errors.non_integer", { field: fieldLabel }));
    return false;
  }

  return true;
}

function validateForm() {
  if (!calculatorForm) {
    return true;
  }

  const inputs = calculatorForm.querySelectorAll('input[type="number"]');
  let isValid = true;
  inputs.forEach((input) => {
    if (!isInputVisible(input)) {
      return;
    }
    if (!validateNumberInput(input)) {
      isValid = false;
    }
  });
  return isValid;
}

function attachValidationHandlers() {
  if (!calculatorForm) {
    return;
  }

  calculatorForm.addEventListener("input", (event) => {
    const target = event.target;
    if (isNumericInputElement(target)) {
      clearFieldError(target);
    }
  });

  calculatorForm.addEventListener(
    "blur",
    (event) => {
      const target = event.target;
      if (isNumericInputElement(target)) {
        validateNumberInput(target);
      }
    },
    true,
  );
}

function readNumber(input) {
  if (!input) {
    return 0;
  }
  if (!isInputVisible(input)) {
    return 0;
  }
  const value = input.valueAsNumber;
  if (!Number.isFinite(value) || value < 0) {
    return 0;
  }
  return value;
}

function readInteger(input) {
  if (!input) {
    return 0;
  }
  if (!isInputVisible(input)) {
    return 0;
  }
  const raw = (input.value ?? "").trim();
  if (!raw) {
    return 0;
  }
  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value) || value < 0) {
    return 0;
  }
  return value;
}

function buildCalculationPayload() {
  const year = Number.parseInt(yearSelect?.value ?? "0", 10);
  const payload = { year, locale: currentLocale };

  const demographics = {};
  const toggles = {};

  if (currentYearToggleKeys.size) {
    currentYearToggleKeys.forEach((key) => {
      toggles[key] = Boolean(currentYearToggles[key]);
    });
  }

  const children = Number.parseInt(childrenInput?.value ?? "0", 10);
  if (Number.isFinite(children) && children > 0) {
    payload.dependents = { children };
  }

  const birthYear = readInteger(birthYearInput);
  if (birthYear >= 1900 && birthYear <= 2100) {
    demographics.birth_year = birthYear;
  }

  const ageBand = ageBandSelect?.value || "";
  if (ageBand) {
    demographics.age_band = ageBand;
  }

  if (youthEligibilityToggle && isInputVisible(youthEligibilityToggle)) {
    toggles.youth_eligibility = Boolean(youthEligibilityToggle.checked);
  }

  if (smallVillageToggle && isInputVisible(smallVillageToggle)) {
    const value = Boolean(smallVillageToggle.checked);
    toggles.small_village = value;
    demographics.small_village = value;
  }

  if (newMotherToggle && isInputVisible(newMotherToggle)) {
    const value = Boolean(newMotherToggle.checked);
    toggles.new_mother = value;
    demographics.new_mother = value;
  }

  payload.demographics = demographics;

  const employmentPayload = {};
  const grossIncome = readNumber(employmentIncomeInput);
  if (grossIncome > 0) {
    employmentPayload.gross_income = grossIncome;
  }

  const monthlyIncome = readNumber(employmentMonthlyIncomeInput);
  if (monthlyIncome > 0) {
    employmentPayload.monthly_income = monthlyIncome;
  }

  const manualEmployeeContributions = readNumber(
    employmentEmployeeContributionsInput,
  );
  if (manualEmployeeContributions > 0) {
    employmentPayload.employee_contributions = manualEmployeeContributions;
  }

  const includeSocial = employmentIncludeSocialToggle
    ? Boolean(employmentIncludeSocialToggle.checked)
    : true;
  if (!includeSocial) {
    employmentPayload.include_social_contributions = false;
  }

  const employmentPayments = resolvePaymentsValue(
    employmentPaymentsInput,
    "employment",
  );
  const hasEmploymentIncome =
    employmentPayload.gross_income !== undefined ||
    employmentPayload.monthly_income !== undefined;

  if (employmentPayments && hasEmploymentIncome) {
    employmentPayload.payments_per_year = employmentPayments;
  }

  if (Object.keys(employmentPayload).length > 0) {
    payload.employment = employmentPayload;
  }

  const withholdingTax = readNumber(employmentWithholdingInput);
  if (withholdingTax > 0) {
    payload.withholding_tax = withholdingTax;
  }

  if (isSectionActive(pensionSection) && isPensionEnabled()) {
    const pensionPayload = {};
    const pensionMode = pensionModeSelect?.value || currentPensionMode;
    if (pensionMode === "monthly") {
      const pensionMonthly = readNumber(pensionMonthlyIncomeInput);
      if (pensionMonthly > 0) {
        pensionPayload.monthly_income = pensionMonthly;
      }
    } else {
      const pensionGross = readNumber(pensionIncomeInput);
      if (pensionGross > 0) {
        pensionPayload.gross_income = pensionGross;
      }
    }

    const pensionPayments = resolvePaymentsValue(
      pensionPaymentsInput,
      "pension",
    );
    if (
      pensionPayments &&
      (pensionPayload.gross_income !== undefined ||
        pensionPayload.monthly_income !== undefined)
    ) {
      pensionPayload.payments_per_year = pensionPayments;
    }

    if (Object.keys(pensionPayload).length > 0) {
      payload.pension = pensionPayload;
    }
  }

  if (isSectionActive(freelanceSection)) {
    const freelancePayload = {};
    const revenue = readNumber(freelanceRevenueInput);
    const expenses = readNumber(freelanceExpensesInput);
    const contributions = readNumber(freelanceContributionsInput);
    const auxiliary = readNumber(freelanceAuxiliaryContributionsInput);
    const lumpSum = readNumber(freelanceLumpSumContributionsInput);
    const efkaCategory = freelanceEfkaSelect?.value;
    const efkaMonths = readInteger(freelanceEfkaMonthsInput);
    const tradeFeeLocation = freelanceTradeFeeLocationSelect?.value;
    const yearsActive =
      derivedFreelanceYearsActive !== null && derivedFreelanceYearsActive > 0
        ? derivedFreelanceYearsActive
        : readInteger(freelanceYearsActiveInput);

    if (revenue > 0) {
      freelancePayload.gross_revenue = revenue;
    }
    if (expenses > 0) {
      freelancePayload.deductible_expenses = expenses;
    }
    if (contributions > 0) {
      freelancePayload.mandatory_contributions = contributions;
    }
    if (auxiliary > 0) {
      freelancePayload.auxiliary_contributions = auxiliary;
    }
    if (lumpSum > 0) {
      freelancePayload.lump_sum_contributions = lumpSum;
    }
    if (efkaCategory) {
      freelancePayload.efka_category = efkaCategory;
    }
    if (efkaMonths > 0) {
      freelancePayload.efka_months = efkaMonths;
    }
    if (tradeFeeLocation && tradeFeeLocation !== "standard") {
      freelancePayload.trade_fee_location = tradeFeeLocation;
    }
    if (yearsActive > 0) {
      freelancePayload.years_active = yearsActive;
    }
    if (derivedFreelanceNewlySelfEmployed) {
      freelancePayload.newly_self_employed = true;
    }

    freelancePayload.include_trade_fee = Boolean(tradeFeeToggle?.checked);

    if (Object.keys(freelancePayload).length > 1 || revenue > 0 || expenses > 0) {
      payload.freelance = freelancePayload;
    }
  }

  if (isSectionActive(agriculturalSection)) {
    const revenue = readNumber(agriculturalRevenueInput);
    const expenses = readNumber(agriculturalExpensesInput);
    const professionalFarmer = Boolean(
      agriculturalProfessionalFarmerInput?.checked,
    );
    if (revenue > 0 || expenses > 0 || professionalFarmer) {
      payload.agricultural = {
        gross_revenue: revenue,
        deductible_expenses: expenses,
      };
      if (professionalFarmer) {
        payload.agricultural.professional_farmer = true;
      }
    }
  }

  if (isSectionActive(otherSection)) {
    const otherIncome = readNumber(otherIncomeInput);
    if (otherIncome > 0) {
      payload.other = { taxable_income: otherIncome };
    }
  }

  if (isSectionActive(rentalSection)) {
    const rentalPayload = {
      gross_income: readNumber(rentalIncomeInput),
      deductible_expenses: readNumber(rentalExpensesInput),
    };
    if (rentalPayload.gross_income > 0 || rentalPayload.deductible_expenses > 0) {
      payload.rental = rentalPayload;
    }
  }

  if (isSectionActive(investmentSection) && currentInvestmentCategories.length) {
    const investmentPayload = {};
    currentInvestmentCategories.forEach((category) => {
      const field = document.getElementById(`investment-${category.id}`);
      const amount = readNumber(field);
      if (amount > 0) {
        investmentPayload[category.id] = amount;
      }
    });
    if (Object.keys(investmentPayload).length > 0) {
      payload.investment = investmentPayload;
    }
  }

  if (isSectionActive(deductionsSection)) {
    const deductionsPayload = {
      donations: readNumber(deductionsDonationsInput),
      medical: readNumber(deductionsMedicalInput),
      education: readNumber(deductionsEducationInput),
      insurance: readNumber(deductionsInsuranceInput),
    };
    if (Object.values(deductionsPayload).some((value) => value > 0)) {
      payload.deductions = deductionsPayload;
    }
  }

  if (isSectionActive(obligationsSection)) {
    const obligationsPayload = {
      enfia: readNumber(enfiaInput),
      luxury: readNumber(luxuryInput),
    };
    if (Object.values(obligationsPayload).some((value) => value > 0)) {
      payload.obligations = obligationsPayload;
    }
  }

  currentYearToggles = { ...toggles };
  payload.toggles = toggles;

  return payload;
}

function updateSankeyLegend(categories) {
  if (!sankeyLegend) {
    return;
  }

  sankeyLegend.innerHTML = "";

  categories.forEach(({ key, label, baseColor }) => {
    if (!label) {
      return;
    }

    const item = document.createElement("div");
    item.className = "sankey-legend__item";
    item.dataset.flow = key;
    item.setAttribute("role", "listitem");

    const swatch = document.createElement("span");
    swatch.className = "sankey-legend__swatch";
    swatch.setAttribute("aria-hidden", "true");
    if (baseColor) {
      swatch.style.background = baseColor;
    }
    item.appendChild(swatch);

    const labelSpan = document.createElement("span");
    labelSpan.textContent = label;
    item.appendChild(labelSpan);

    sankeyLegend.appendChild(item);
  });
}

function buildSankeyAriaLabel(categoryLabels) {
  const formatted = formatListForLocale(categoryLabels);
  if (!formatted) {
    return t("sankey.aria_label");
  }

  const templateKey = "sankey.aria_label_template";
  const template = t(templateKey, { categories: formatted });
  if (template && template !== templateKey) {
    return template;
  }

  return t("sankey.aria_label");
}

function renderSankey(result) {
  if (!sankeyWrapper || !sankeyChart) {
    return;
  }

  const details = Array.isArray(result?.details) ? result.details : [];
  const renderToken = ++sankeyRenderSequence;
  const nodeLabels = [];
  const nodeIndex = new Map();
  const sources = [];
  const targets = [];
  const values = [];
  const linkLabels = [];
  const linkColors = [];

  const flowTaxes = getCssVariable("--flow-taxes", "#d63384");
  const textColor = getCssVariable("--text-body", "#212529");
  const subtleColor = getCssVariable("--text-subtle", "#495057");
  const nodeLineColor = getCssVariable("--sankey-node-outline", "#adb5bd");
  const linkOutlineColor = getCssVariable(
    "--sankey-link-outline",
    "rgba(255, 255, 255, 0.9)",
  );
  const tooltipBackground = getCssVariable("--tooltip-bg", "#212529");
  const tooltipText = getCssVariable("--tooltip-text", "#ffffff");
  const linkColorPalette = {
    default: colorWithAlpha(subtleColor, 0.6, "rgba(73, 80, 87, 0.6)"),
  };

  const categoryMeta = DISTRIBUTION_CATEGORIES.map(({ key, colorVar }) => {
    const translationKey = `distribution.${key}`;
    const translated = t(translationKey);
    const label =
      translated && translated !== translationKey
        ? translated
        : key
            .split("_")
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(" ");
    const fallbackBase = DISTRIBUTION_FALLBACK_COLORS[key] || flowTaxes;
    const cssColor = getCssVariable(colorVar, fallbackBase);
    const baseColor = cssColor && cssColor.trim() ? cssColor.trim() : fallbackBase;
    const fallbackLink = colorWithAlpha(
      fallbackBase,
      0.72,
      "rgba(73, 80, 87, 0.6)",
    );
    const fallbackNode = colorWithAlpha(
      fallbackBase,
      0.18,
      "rgba(33, 37, 41, 0.08)",
    );
    const linkColor = colorWithAlpha(baseColor, 0.72, fallbackLink);
    const nodeColor = colorWithAlpha(baseColor, 0.18, fallbackNode);

    return {
      key,
      label,
      baseColor,
      linkColor,
      nodeColor,
    };
  });

  updateSankeyLegend(categoryMeta);

  const nodeAccentColors = {};
  const categoryLabels = [];

  categoryMeta.forEach((meta) => {
    if (meta.label) {
      nodeAccentColors[meta.label] = meta.nodeColor;
      categoryLabels.push(meta.label);
    }
    linkColorPalette[meta.key] = meta.linkColor;
  });

  const ensureNode = (label) => {
    const resolved = label || "";
    if (nodeIndex.has(resolved)) {
      return nodeIndex.get(resolved);
    }
    const index = nodeLabels.length;
    nodeLabels.push(resolved);
    nodeIndex.set(resolved, index);
    return index;
  };

  const categoryIndex = new Map();

  const getCategoryIndex = (key) => {
    if (categoryIndex.has(key)) {
      return categoryIndex.get(key);
    }
    const meta = categoryMeta.find((entry) => entry.key === key);
    const label = meta?.label || key;
    const index = ensureNode(label);
    categoryIndex.set(key, index);
    return index;
  };

  const toChartValue = (value) => {
    const number = Number.parseFloat(value ?? 0);
    if (!Number.isFinite(number) || number <= 0) {
      return 0;
    }
    return Math.round(number * 100) / 100;
  };

  const addLink = (source, target, value, label, categoryKey = "default") => {
    const chartValue = toChartValue(value);
    if (!chartValue) {
      return;
    }
    sources.push(source);
    targets.push(target);
    values.push(chartValue);
    linkLabels.push(label);
    linkColors.push(
      linkColorPalette[categoryKey] || linkColorPalette.default,
    );
  };

  details.forEach((detail) => {
    if (!detail) {
      return;
    }

    const sourceLabel = detail.label || detail.category;
    if (!sourceLabel) {
      return;
    }

    const sourceIndex = ensureNode(sourceLabel);
    const breakdown = computeDistributionForDetail(detail);
    if (!breakdown || breakdown.gross <= 0) {
      return;
    }

    categoryMeta.forEach(({ key, label }) => {
      const amount = Math.max(breakdown[key] || 0, 0);
      if (amount <= 0.005) {
        return;
      }
      const targetIndex = getCategoryIndex(key);
      const tooltipLabel = `${sourceLabel} → ${label}: ${formatCurrency(amount)}`;
      addLink(sourceIndex, targetIndex, amount, tooltipLabel, key);
    });
  });

  if (!values.length) {
    if (sankeyEmptyState) {
      sankeyEmptyState.hidden = false;
    }
    sankeyWrapper.hidden = false;
    sankeyChart.setAttribute("aria-hidden", "true");
    sankeyChart.removeAttribute("aria-label");
    if (pendingPlotlyJob !== null) {
      cancelIdleWork(pendingPlotlyJob);
      pendingPlotlyJob = null;
    }
    if (typeof Plotly !== "undefined") {
      Plotly.purge(sankeyChart);
    }
    return;
  }

  if (sankeyEmptyState) {
    sankeyEmptyState.hidden = true;
  }

  if (sankeyWrapper.hidden) {
    sankeyWrapper.hidden = false;
  }

  const nodeColors = nodeLabels.map(
    (label) =>
      nodeAccentColors[label] || colorWithAlpha(subtleColor, 0.12, "rgba(33, 37, 41, 0.08)"),
  );

  const { width: resolvedWidth, height: chartHeight } = computeSankeyDimensions();

  const ariaLabel = buildSankeyAriaLabel(categoryLabels);

  const data = [
    {
      type: "sankey",
      orientation: "h",
      node: {
        pad: 12,
        thickness: 26,
        label: nodeLabels,
        line: { color: nodeLineColor, width: 1 },
        color: nodeColors,
      },
      link: {
        source: sources,
        target: targets,
        value: values,
        label: linkLabels,
        color: linkColors,
        line: { color: linkOutlineColor, width: 1.2 },
        hovertemplate: "%{label}<extra></extra>",
      },
      hoverlabel: {
        bgcolor: tooltipBackground,
        font: { color: tooltipText },
      },
    },
  ];

  const layout = {
    margin: { l: 6, r: 6, t: 8, b: 8 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { size: 12, color: textColor },
    height: chartHeight,
    width: resolvedWidth,
  };

  sankeyChart.style.minHeight = `${chartHeight}px`;
  sankeyChart.style.height = `${chartHeight}px`;
  sankeyChart.style.minWidth = "0";
  sankeyChart.style.width = "100%";

  const executeRender = () => {
    ensurePlotlyLoaded()
      .then((plotly) => {
        if (renderToken !== sankeyRenderSequence) {
          return;
        }
        plotly.react(sankeyChart, data, layout, { displayModeBar: false, responsive: true });
        sankeyPlotlyRef = plotly;
        ensureSankeyResizeHandlers();
        const scheduleResize =
          typeof requestAnimationFrame === "function"
            ? requestAnimationFrame
            : (callback) => setTimeout(callback, 16);

        scheduleResize(() => {
          if (renderToken === sankeyRenderSequence) {
            applySankeyDimensions(plotly);
          }
        });
        sankeyWrapper.hidden = false;
        sankeyChart.setAttribute("aria-hidden", "false");
        sankeyChart.setAttribute("aria-label", ariaLabel);
      })
      .catch((error) => {
        console.error("Unable to initialise the Sankey diagram", error);
        if (renderToken === sankeyRenderSequence) {
          sankeyWrapper.hidden = true;
          sankeyChart.setAttribute("aria-hidden", "true");
          sankeyChart.removeAttribute("aria-label");
        }
      });
  };

  if (pendingPlotlyJob !== null) {
    cancelIdleWork(pendingPlotlyJob);
    pendingPlotlyJob = null;
  }

  if (typeof Plotly === "undefined") {
    pendingPlotlyJob = scheduleIdleWork(() => {
      pendingPlotlyJob = null;
      if (renderToken !== sankeyRenderSequence) {
        return;
      }
      executeRender();
    });
  } else {
    executeRender();
  }
}

const DISTRIBUTION_EXPENSE_FIELDS = ["deductible_expenses"];
const DISTRIBUTION_TAX_CATEGORIES = new Set(["luxury", "enfia"]);

const DISTRIBUTION_CATEGORIES = [
  { key: "net_income", colorVar: "--flow-net" },
  { key: "taxes", colorVar: "--flow-taxes" },
  { key: "insurance", colorVar: "--flow-contributions" },
  { key: "expenses", colorVar: "--flow-expenses" },
];

const DISTRIBUTION_FALLBACK_COLORS = {
  net_income: "#0f6dff",
  taxes: "#ff4d6a",
  insurance: "#00bfa6",
  expenses: "#f5a524",
};

function toFiniteNumber(value) {
  const parsed = Number.parseFloat(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function resolveEmploymentContributionPreviewMessage(type, replacements = {}) {
  const config = EMPLOYMENT_CONTRIBUTION_PREVIEW_MESSAGES[type];
  if (!config) {
    return "";
  }

  const message = t(config.key, replacements);
  if (typeof message === "string" && message && message !== config.key) {
    return message;
  }

  const locale = getActiveLocale();
  const fallbackTemplate =
    (config.fallback && (config.fallback[locale] || config.fallback.en)) || "";
  if (!fallbackTemplate) {
    return "";
  }

  return formatTemplate(fallbackTemplate, replacements);
}

function getManualEmploymentContributionValue() {
  if (!employmentEmployeeContributionsInput) {
    return 0;
  }

  const raw = (employmentEmployeeContributionsInput.value ?? "").trim();
  if (!raw) {
    return 0;
  }

  const normalised = raw.replace(",", ".");
  const value = Number.parseFloat(normalised);
  if (!Number.isFinite(value) || value <= 0) {
    return 0;
  }

  return value;
}

function applyEmploymentContributionPreview(message) {
  if (!employmentEmployeeContributionsPreview) {
    return;
  }

  if (typeof message === "string" && message.trim()) {
    employmentEmployeeContributionsPreview.textContent = message;
    employmentEmployeeContributionsPreview.hidden = false;
  } else {
    employmentEmployeeContributionsPreview.textContent = "";
    employmentEmployeeContributionsPreview.hidden = true;
  }
}

function applyEmploymentModeLabels() {
  if (!employmentModeSelect) {
    return;
  }

  const annualOption = employmentModeSelect.querySelector(
    'option[value="annual"]',
  );
  const monthlyOption = employmentModeSelect.querySelector(
    'option[value="monthly"]',
  );

  if (annualOption) {
    annualOption.textContent = "Ανά έτος";
  }
  if (monthlyOption) {
    monthlyOption.textContent = "Ανά καταβολή (μήνα)";
  }
}

function updateEmploymentContributionPreview(details) {
  if (!employmentEmployeeContributionsPreview) {
    return;
  }

  const includeSocial = employmentIncludeSocialToggle
    ? Boolean(employmentIncludeSocialToggle.checked)
    : true;

  if (!includeSocial) {
    const excludedMessage = resolveEmploymentContributionPreviewMessage(
      "excluded",
    );
    applyEmploymentContributionPreview(excludedMessage);
    return;
  }

  const manualValue = getManualEmploymentContributionValue();
  if (manualValue > 0) {
    const manualMessage = resolveEmploymentContributionPreviewMessage(
      "manual",
      {
        amount: formatCurrency(manualValue),
      },
    );
    applyEmploymentContributionPreview(manualMessage);
    return;
  }

  const detailsList = Array.isArray(details) ? details : [];
  const employmentDetail = detailsList.find(
    (detail) => detail && detail.category === "employment",
  );

  if (employmentDetail) {
    const totalContributions = toFiniteNumber(
      employmentDetail.employee_contributions,
    );
    const manualPortion = toFiniteNumber(
      employmentDetail.employee_contributions_manual,
    );
    const automaticContributions = Math.max(
      totalContributions - manualPortion,
      0,
    );

    if (automaticContributions > 0) {
      const message = resolveEmploymentContributionPreviewMessage(
        "automatic",
        {
          amount: formatCurrency(automaticContributions),
        },
      );
      applyEmploymentContributionPreview(message);
      return;
    }
  }

  const fallbackMessage = resolveEmploymentContributionPreviewMessage("empty");
  applyEmploymentContributionPreview(fallbackMessage);
}

function sumDetailFields(detail, fields) {
  if (!detail) {
    return 0;
  }
  return fields.reduce((total, field) => {
    const amount = toFiniteNumber(detail[field]);
    return amount > 0 ? total + amount : total;
  }, 0);
}

function computeDistributionForDetail(detail) {
  const empty = { net_income: 0, taxes: 0, insurance: 0, expenses: 0, gross: 0 };
  if (!detail) {
    return empty;
  }

  const taxCandidate =
    detail.total_tax !== undefined && detail.total_tax !== null
      ? detail.total_tax
      : detail.tax;
  const taxes = Math.max(toFiniteNumber(taxCandidate), 0);

  const contributionCandidates = [
    toFiniteNumber(detail.employee_contributions),
    toFiniteNumber(detail.deductible_contributions),
    toFiniteNumber(detail.contributions),
  ];
  let insurance = contributionCandidates.reduce((total, value) => {
    return value > 0 ? total + value : total;
  }, 0);

  const rawNet = toFiniteNumber(detail.net_income);
  let netIncome = rawNet > 0 ? rawNet : 0;

  let expenses = sumDetailFields(detail, DISTRIBUTION_EXPENSE_FIELDS);

  const isTaxDetail =
    taxes > 0 ||
    (typeof detail.category === "string" &&
      DISTRIBUTION_TAX_CATEGORIES.has(detail.category));

  if (rawNet < 0) {
    if (!isTaxDetail && insurance <= 0) {
      expenses += Math.abs(rawNet);
    }
    netIncome = 0;
  }

  if (insurance <= 0) {
    const gross = Math.max(toFiniteNumber(detail.gross_income), 0);
    if (gross > 0) {
      const impliedInsurance = gross - (taxes + expenses + netIncome);
      if (impliedInsurance > 0) {
        insurance = impliedInsurance;
      }
    }
  }

  const breakdown = {
    net_income: Math.max(netIncome, 0),
    taxes: Math.max(taxes, 0),
    insurance: Math.max(insurance, 0),
    expenses: Math.max(expenses, 0),
  };

  const grossTotal =
    breakdown.net_income +
    breakdown.taxes +
    breakdown.insurance +
    breakdown.expenses;

  return { ...breakdown, gross: grossTotal > 0 ? grossTotal : 0 };
}

function resolveDistributionDetailLabel(detail) {
  if (!detail || typeof detail !== "object") {
    return t("distribution.total_income");
  }

  const candidateKeys = [
    "label",
    "category_label",
    "category",
    "section_label",
    "section",
    "name",
    "type_label",
    "type",
  ];

  for (const key of candidateKeys) {
    const value = detail[key];
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (trimmed) {
        return trimmed;
      }
    }
  }

  return t("distribution.total_income");
}

function computeDistributionTotals(details) {
  const totals = { net_income: 0, taxes: 0, insurance: 0, expenses: 0 };
  const breakdownMaps = {
    net_income: new Map(),
    taxes: new Map(),
    insurance: new Map(),
    expenses: new Map(),
  };
  const entries = Array.isArray(details) ? details : [];
  let grossTotal = 0;

  entries.forEach((detail) => {
    const breakdown = computeDistributionForDetail(detail);

    grossTotal += breakdown.gross;

    Object.entries(breakdown).forEach(([key, value]) => {
      if (key === "gross") {
        return;
      }

      const safeValue = Math.max(value || 0, 0);

      if (!Object.prototype.hasOwnProperty.call(totals, key)) {
        totals[key] = 0;
      }
      if (!Object.prototype.hasOwnProperty.call(breakdownMaps, key)) {
        breakdownMaps[key] = new Map();
      }

      totals[key] += safeValue;

      if (safeValue <= 0) {
        return;
      }

      const label = resolveDistributionDetailLabel(detail);
      const categoryBreakdown = breakdownMaps[key];
      const existingValue = categoryBreakdown.get(label) || 0;
      categoryBreakdown.set(label, existingValue + safeValue);
    });
  });

  const breakdowns = Object.fromEntries(
    Object.entries(breakdownMaps).map(([key, valueMap]) => {
      const entriesForCategory = Array.from(valueMap.entries()).map(
        ([label, value]) => ({ label, value }),
      );
      return [key, entriesForCategory];
    }),
  );

  const totalValue = grossTotal;

  return { totals, totalValue, breakdowns };
}

function renderDistributionChart(details) {
  if (!distributionWrapper || !distributionList || !distributionChart) {
    return;
  }

  distributionList.innerHTML = "";
  distributionChart.innerHTML = "";
  distributionChart.removeAttribute("aria-label");
  distributionChart.setAttribute("aria-hidden", "true");

  let tooltip = distributionWrapper.querySelector(".distribution-chart__tooltip");
  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.className = "distribution-chart__tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.hidden = true;
    const tooltipLabel = document.createElement("span");
    tooltipLabel.className = "distribution-chart__tooltip-label";
    tooltip.appendChild(tooltipLabel);
    const tooltipValue = document.createElement("span");
    tooltipValue.className = "distribution-chart__tooltip-value";
    tooltip.appendChild(tooltipValue);
    distributionWrapper.appendChild(tooltip);
  }

  const tooltipLabel = tooltip.querySelector(".distribution-chart__tooltip-label");
  const tooltipValue = tooltip.querySelector(".distribution-chart__tooltip-value");
  let tooltipBreakdown = tooltip.querySelector(
    ".distribution-chart__tooltip-breakdown",
  );
  if (!tooltipBreakdown) {
    tooltipBreakdown = document.createElement("ul");
    tooltipBreakdown.className = "distribution-chart__tooltip-breakdown";
    tooltip.appendChild(tooltipBreakdown);
  }

  let activeElement = null;
  let activeElementClass = null;
  const tooltipDataByCategory = new Map();

  const hideTooltip = () => {
    if (activeElement && activeElementClass) {
      activeElement.classList.remove(activeElementClass);
    }
    activeElement = null;
    activeElementClass = null;
    if (tooltipLabel) {
      tooltipLabel.textContent = "";
    }
    if (tooltipValue) {
      tooltipValue.textContent = "";
    }
    if (tooltipBreakdown) {
      tooltipBreakdown.innerHTML = "";
    }
    tooltip.hidden = true;
    tooltip.removeAttribute("data-visible");
  };

  const updateTooltipPosition = (event, fallbackTarget) => {
    if (tooltip.hidden) {
      return;
    }
    const reference =
      (event && event.currentTarget instanceof Element
        ? event.currentTarget
        : null) || fallbackTarget;
    const wrapperRect = distributionWrapper.getBoundingClientRect();
    let clientX = null;
    let clientY = null;
    if (event && typeof event.clientX === "number" && typeof event.clientY === "number") {
      clientX = event.clientX;
      clientY = event.clientY;
    }
    if ((clientX === null || clientY === null) && reference instanceof Element) {
      const rect = reference.getBoundingClientRect();
      clientX = rect.left + rect.width / 2;
      clientY = rect.top + rect.height / 2;
    }
    if (clientX === null || clientY === null) {
      return;
    }
    const x = clientX - wrapperRect.left;
    const y = clientY - wrapperRect.top;
    tooltip.style.setProperty("--tooltip-x", `${x}px`);
    tooltip.style.setProperty("--tooltip-y", `${y}px`);
  };

  const showTooltip = (event) => {
    const target = event.currentTarget;
    if (!(target instanceof Element)) {
      return;
    }
    const category = target.dataset.category;
    if (!category) {
      return;
    }

    const tooltipData = tooltipDataByCategory.get(category);
    if (!tooltipData) {
      return;
    }

    if (tooltipLabel) {
      tooltipLabel.textContent = tooltipData.label || "";
    }
    if (tooltipValue) {
      const hasPercent = tooltipData.percent && tooltipData.percent.trim();
      tooltipValue.textContent = hasPercent
        ? `${tooltipData.amount} · ${tooltipData.percent}`
        : tooltipData.amount || tooltipData.percent || "";
    }
    if (tooltipBreakdown) {
      tooltipBreakdown.innerHTML = "";
      tooltipData.breakdown.forEach((entry) => {
        const item = document.createElement("li");
        item.className = "distribution-chart__tooltip-item";

        const entryLabel = document.createElement("span");
        entryLabel.className = "distribution-chart__tooltip-item-label";
        entryLabel.textContent = entry.label;
        item.appendChild(entryLabel);

        const entryValue = document.createElement("span");
        entryValue.className = "distribution-chart__tooltip-item-value";
        entryValue.textContent = entry.percent
          ? `${entry.amount} · ${entry.percent}`
          : entry.amount;
        item.appendChild(entryValue);

        tooltipBreakdown.appendChild(item);
      });
    }

    if (activeElement && activeElementClass) {
      activeElement.classList.remove(activeElementClass);
    }

    const nextActiveClass =
      target instanceof SVGElement
        ? "distribution-chart__segment--active"
        : "distribution-legend__item--active";

    activeElement = target;
    activeElementClass = nextActiveClass;
    activeElement.classList.add(nextActiveClass);

    tooltip.hidden = false;
    tooltip.setAttribute("data-visible", "true");
    updateTooltipPosition(event, target);
  };

  const trackPointer = (event) => {
    if (activeElement) {
      updateTooltipPosition(event, activeElement);
    }
  };

  hideTooltip();

  const { totals, totalValue, breakdowns } = computeDistributionTotals(details);
  const safeTotal = totalValue > 0 ? totalValue : 0;

  if (!safeTotal) {
    if (distributionEmptyState) {
      distributionEmptyState.hidden = false;
    }
    if (distributionVisual) {
      distributionVisual.hidden = true;
    }
    distributionList.hidden = true;
    distributionChart.hidden = true;
    distributionWrapper.hidden = false;
    return;
  }

  const rootStyles =
    typeof window !== "undefined"
      ? window.getComputedStyle(document.documentElement)
      : null;
  const center = 120;
  const radius = 90;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  const labelParts = [];

  const baseCategoryOrder = DISTRIBUTION_CATEGORIES.map(({ key }) => key);
  const totalsKeys = Object.keys(totals);
  const seenCategories = new Set();
  const categoryOrder = [];

  const addCategoryKey = (key) => {
    if (!key || seenCategories.has(key)) {
      return;
    }
    seenCategories.add(key);
    categoryOrder.push(key);
  };

  baseCategoryOrder.forEach((key) => addCategoryKey(key));
  totalsKeys.forEach((key) => addCategoryKey(key));

  const ring = document.createElementNS(SVG_NS, "circle");
  ring.setAttribute("class", "distribution-chart__ring");
  ring.setAttribute("cx", center);
  ring.setAttribute("cy", center);
  ring.setAttribute("r", radius);
  distributionChart.appendChild(ring);

  categoryOrder.forEach((key) => {
    const value = Math.max(totals[key] || 0, 0);
    const ratio = safeTotal > 0 ? value / safeTotal : 0;
    const clampedRatio = Math.max(0, Math.min(ratio, 1));
    const strokeLength = clampedRatio * circumference;
    const categoryConfig = DISTRIBUTION_CATEGORIES.find(
      (entry) => entry.key === key,
    );
    const colorVar = categoryConfig?.colorVar || `--distribution-${key}`;
    const labelText = (() => {
      const translationKey = `distribution.${key}`;
      const translated = t(translationKey);
      if (translated && translated !== translationKey) {
        return translated;
      }
      return key.replace(/_/g, " ");
    })();

    const cssColor = rootStyles ? rootStyles.getPropertyValue(colorVar) : "";
    const normalizedColor = cssColor && cssColor.trim().length
      ? cssColor.trim()
      : DISTRIBUTION_FALLBACK_COLORS[key] || "#0f6dff";

    if (!(value > 0)) {
      offset = Math.min(offset + strokeLength, circumference);
      return;
    }

    const formattedAmount = formatCurrency(value);
    const formattedPercent = formatPercent(ratio);
    const breakdownEntries = Array.isArray(breakdowns[key])
      ? breakdowns[key]
      : [];
    const normalizedBreakdown = breakdownEntries
      .filter((entry) => entry && entry.value > 0)
      .sort((a, b) => b.value - a.value)
      .map((entry) => ({
        label: entry.label,
        amount: formatCurrency(entry.value),
        percent: formatPercent(value > 0 ? entry.value / value : 0),
      }));

    tooltipDataByCategory.set(key, {
      label: labelText,
      amount: formattedAmount,
      percent: formattedPercent,
      breakdown: normalizedBreakdown,
    });

    if (strokeLength > 0) {
      const segment = document.createElementNS(SVG_NS, "circle");
      segment.setAttribute("class", "distribution-chart__segment");
      segment.dataset.category = key;
      segment.setAttribute("cx", center);
      segment.setAttribute("cy", center);
      segment.setAttribute("r", radius);
      segment.setAttribute("stroke", normalizedColor);
      segment.setAttribute(
        "stroke-dasharray",
        `${strokeLength} ${Math.max(circumference - strokeLength, 0)}`,
      );
      segment.setAttribute("stroke-dashoffset", `${-offset}`);
      segment.setAttribute("tabindex", "0");
      segment.setAttribute("focusable", "true");
      segment.setAttribute("role", "img");
      segment.setAttribute(
        "aria-label",
        `${labelText}: ${formattedAmount} (${formattedPercent})`,
      );
      segment.addEventListener("mouseenter", showTooltip);
      segment.addEventListener("mouseleave", hideTooltip);
      segment.addEventListener("focus", showTooltip);
      segment.addEventListener("blur", hideTooltip);
      segment.addEventListener("mousemove", trackPointer);
      distributionChart.appendChild(segment);
    }

    offset = Math.min(offset + strokeLength, circumference);

    const item = document.createElement("li");
    item.className = "distribution-legend__item";
    item.dataset.category = key;
    item.style.setProperty("--distribution-color", normalizedColor);
    item.setAttribute("tabindex", "0");

    const swatch = document.createElement("span");
    swatch.className = "distribution-legend__swatch";
    swatch.setAttribute("aria-hidden", "true");
    item.appendChild(swatch);

    const labelSpan = document.createElement("span");
    labelSpan.className = "distribution-legend__label";
    labelSpan.textContent = labelText;
    item.appendChild(labelSpan);

    const amountSpan = document.createElement("span");
    amountSpan.className = "distribution-legend__amount";
    amountSpan.textContent = formattedAmount;
    item.appendChild(amountSpan);

    const percentSpan = document.createElement("span");
    percentSpan.className = "distribution-legend__percent";
    percentSpan.textContent = formattedPercent;
    item.appendChild(percentSpan);

    item.addEventListener("mouseenter", showTooltip);
    item.addEventListener("mouseleave", hideTooltip);
    item.addEventListener("focus", showTooltip);
    item.addEventListener("blur", hideTooltip);
    item.addEventListener("mousemove", trackPointer);

    distributionList.appendChild(item);

    labelParts.push(`${labelText} ${formattedPercent}`);
  });

  if (safeTotal > 0) {
    labelParts.unshift(
      `${t("distribution.gross_income")} ${formatCurrency(safeTotal)}`,
    );
  }

  const totalLabel = document.createElementNS(SVG_NS, "text");
  totalLabel.classList.add("distribution-chart__center-label");
  totalLabel.setAttribute("x", center);
  totalLabel.setAttribute("y", center - 6);
  totalLabel.setAttribute("text-anchor", "middle");
  totalLabel.textContent = t("distribution.gross_income");
  distributionChart.appendChild(totalLabel);

  const totalValueText = document.createElementNS(SVG_NS, "text");
  totalValueText.classList.add("distribution-chart__center-value");
  totalValueText.setAttribute("x", center);
  totalValueText.setAttribute("y", center + 18);
  totalValueText.setAttribute("text-anchor", "middle");
  totalValueText.textContent = formatCurrency(safeTotal);
  distributionChart.appendChild(totalValueText);

  if (labelParts.length) {
    distributionChart.setAttribute(
      "aria-label",
      `${t("distribution.heading")}: ${labelParts.join(", ")}`,
    );
    distributionChart.setAttribute("aria-hidden", "false");
  }

  if (distributionEmptyState) {
    distributionEmptyState.hidden = true;
  }
  if (distributionVisual) {
    distributionVisual.hidden = false;
  }
  distributionList.hidden = false;
  distributionChart.hidden = false;
  distributionWrapper.hidden = false;
}

function resolveSummaryLabel(key, labels = {}, localeOverride = currentLocale) {
  if (labels && typeof labels[key] === "string" && labels[key].trim()) {
    return labels[key];
  }
  const translationKey = `summary.${key}`;
  const translated = t(translationKey, {}, localeOverride);
  if (translated && translated !== translationKey) {
    return translated;
  }
  return key;
}

function resolveDetailLabel(detail, key, labels = {}, localeOverride = currentLocale) {
  if (key === "trade_fee" && detail && typeof detail.trade_fee_label === "string") {
    return detail.trade_fee_label;
  }
  if (labels && typeof labels[key] === "string" && labels[key].trim()) {
    return labels[key];
  }
  const translationKey = `detailFields.${key}`;
  const translated = t(translationKey, {}, localeOverride);
  if (translated && translated !== translationKey) {
    return translated;
  }
  return key;
}

function renderSummary(summary) {
  if (!summaryGrid) {
    return;
  }

  summaryGrid.innerHTML = "";
  const labels = summary.labels || {};
  const summaryFields = [
    { key: "income_total", formatter: formatCurrency },
    { key: "taxable_income", formatter: formatCurrency },
    { key: "deductions_entered", formatter: formatCurrency },
    { key: "deductions_applied", formatter: formatCurrency },
    { key: "tax_total", formatter: formatCurrency, className: "accent" },
    { key: "withholding_tax", formatter: formatCurrency },
    { key: "balance_due", formatter: formatCurrency, className: "accent" },
    { key: "net_income", formatter: formatCurrency, className: "primary" },
    { key: "net_monthly_income", formatter: formatCurrency },
    { key: "average_monthly_tax", formatter: formatCurrency },
    { key: "effective_tax_rate", formatter: formatPercent },
  ];

  summaryFields.forEach(({ key, formatter, className }) => {
    if (!(key in summary)) {
      return;
    }
    const wrapper = document.createElement("dl");
    const classes = ["summary-item"];
    if (className) {
      classes.push(`summary-item--${className}`);
    }
    wrapper.className = classes.join(" ");
    wrapper.dataset.field = key;
    if (key === "balance_due") {
      wrapper.dataset.variant = summary.balance_due_is_refund ? "refund" : "due";
    }

    const dt = document.createElement("dt");
    dt.textContent = resolveSummaryLabel(key, labels);
    dt.dataset.field = key;

    const dd = document.createElement("dd");
    dd.textContent = formatter(summary[key]);
    dd.dataset.field = key;

    wrapper.appendChild(dt);
    wrapper.appendChild(dd);
    summaryGrid.appendChild(wrapper);
  });
}

function renderDetailCard(detail) {
  const card = document.createElement("article");
  card.className = "detail-card";

  const title = document.createElement("h3");
  title.textContent = detail.label || detail.category;
  card.appendChild(title);

  const detailLabels = getMessagesSection(currentLocale, "detailFields");

  const dl = document.createElement("dl");
  const fieldOrder = [
    "gross_income",
    "deductible_contributions",
    "category_contributions",
    "additional_contributions",
    "auxiliary_contributions",
    "lump_sum_contributions",
    "employee_contributions",
    "employee_contributions_manual",
    "employer_contributions",
    "deductible_expenses",
    "taxable_income",
    "tax_before_credits",
    "credits",
    "tax",
    "trade_fee",
    "total_tax",
    "net_income",
    "net_income_per_payment",
    "deductions_applied",
  ];
  const labels = {
    gross_income: detailLabels.gross_income || "Gross income",
    deductible_contributions:
      detailLabels.deductible_contributions || "Mandatory contributions",
    category_contributions:
      detailLabels.category_contributions || "Category contributions",
    additional_contributions:
      detailLabels.additional_contributions || "Additional contributions",
    auxiliary_contributions:
      detailLabels.auxiliary_contributions || "Auxiliary contributions",
    lump_sum_contributions:
      detailLabels.lump_sum_contributions || "Lump-sum contributions",
    employee_contributions:
      detailLabels.employee_contributions || "Employee contributions",
    employee_contributions_manual:
      detailLabels.employee_contributions_manual ||
      "Additional employee contributions",
    employer_contributions:
      detailLabels.employer_contributions || "Employer contributions",
    deductible_expenses:
      detailLabels.deductible_expenses || "Deductible expenses",
    taxable_income: detailLabels.taxable_income || "Taxable income",
    tax_before_credits: detailLabels.tax_before_credits || "Tax before credits",
    credits: detailLabels.credits || "Credits",
    tax: detailLabels.tax || "Tax",
    trade_fee:
      detail.trade_fee_label || detailLabels.trade_fee || "Business activity fee",
    total_tax: detailLabels.total_tax || "Total tax",
    net_income: detailLabels.net_income || "Net impact",
    net_income_per_payment:
      detailLabels.net_income_per_payment || "Net per payment",
    deductions_applied:
      detailLabels.deductions_applied || "Deductions applied",
  };

  fieldOrder.forEach((key) => {
    if (!(key in detail)) {
      return;
    }

    const value = detail[key];
    if (value === null || value === undefined) {
      return;
    }

    if (
      typeof value === "number" &&
      Number.isFinite(value) &&
      key !== "payments_per_year" &&
      Math.abs(value) < 0.005
    ) {
      return;
    }

    const dt = document.createElement("dt");
    dt.textContent = labels[key];
    dt.dataset.field = key;

    const dd = document.createElement("dd");
    dd.textContent = formatCurrency(value);
    dd.dataset.field = key;

    dl.appendChild(dt);
    dl.appendChild(dd);
  });

  if (detail.items && Array.isArray(detail.items) && detail.items.length) {
    const dt = document.createElement("dt");
    dt.textContent = detailLabels.breakdown || "Breakdown";
    dt.dataset.field = "breakdown";

    const dd = document.createElement("dd");
    dd.dataset.field = "breakdown";

    const breakdown = document.createElement("div");
    breakdown.className = "detail-breakdown";

    detail.items.forEach((item) => {
      if (!item) {
        return;
      }

      const entry = document.createElement("div");
      entry.className = "detail-breakdown__item";

      const label = document.createElement("span");
      label.className = "detail-breakdown__label";
      label.textContent = item.label || "";

      const flow = document.createElement("span");
      flow.className = "detail-breakdown__flow";

      const amount = document.createElement("span");
      amount.className = "detail-breakdown__amount";
      amount.textContent = formatCurrency(item.amount);

      const arrow = document.createElement("span");
      arrow.className = "detail-breakdown__arrow";
      arrow.textContent = "→";

      const tax = document.createElement("span");
      tax.className = "detail-breakdown__tax";
      tax.textContent = formatCurrency(item.tax);

      flow.appendChild(amount);
      flow.appendChild(arrow);
      flow.appendChild(tax);

      entry.appendChild(label);
      entry.appendChild(flow);

      const rateValue = Number.parseFloat(item.rate);
      if (Number.isFinite(rateValue)) {
        const rate = document.createElement("span");
        rate.className = "detail-breakdown__rate";
        const formattedRate = formatPercent(rateValue);
        rate.textContent = formattedRate;
        rate.title = `${label.textContent} ${formattedRate}`.trim();
        rate.setAttribute("aria-label", `${label.textContent} ${formattedRate}`.trim());
        entry.appendChild(rate);
      }

      breakdown.appendChild(entry);
    });

    if (breakdown.childElementCount > 0) {
      dd.appendChild(breakdown);
      dl.appendChild(dt);
      dl.appendChild(dd);
    }
  }

  card.appendChild(dl);
  return card;
}

function renderDetails(details) {
  if (!detailsList) {
    return;
  }

  detailsList.innerHTML = "";
  details.forEach((detail) => {
    if (!detail) {
      return;
    }
    const card = renderDetailCard(detail);
    if (card) {
      detailsList.appendChild(card);
    }
  });
}

function renderCalculation(result) {
  if (!result) {
    return;
  }

  if (resultsSection) {
    resultsSection.hidden = false;
  }

  lastCalculation = result;
  updateEmploymentContributionPreview(result.details || []);
  downloadButton?.removeAttribute("disabled");
  downloadCsvButton?.removeAttribute("disabled");
  printButton?.removeAttribute("disabled");

  renderSankey(result);
  renderDistributionChart(result.details || []);
  renderSummary(result.summary || {});
  renderDetails(result.details || []);
}

function resetResults() {
  if (resultsSection) {
    resultsSection.hidden = true;
  }
  if (summaryGrid) {
    summaryGrid.innerHTML = "";
  }
  if (detailsList) {
    detailsList.innerHTML = "";
  }
  if (distributionList) {
    distributionList.innerHTML = "";
    distributionList.hidden = true;
  }
  if (distributionChart) {
    distributionChart.innerHTML = "";
    distributionChart.hidden = true;
    distributionChart.removeAttribute("aria-label");
    distributionChart.setAttribute("aria-hidden", "true");
  }
  if (distributionVisual) {
    distributionVisual.hidden = true;
  }
  if (distributionEmptyState) {
    distributionEmptyState.hidden = false;
  }
  if (distributionWrapper) {
    distributionWrapper.hidden = true;
  }
  downloadButton?.setAttribute("disabled", "true");
  downloadCsvButton?.setAttribute("disabled", "true");
  printButton?.setAttribute("disabled", "true");
  lastCalculation = null;
  updateEmploymentContributionPreview([]);
}

function clearCalculatorForm() {
  if (!calculatorForm) {
    return;
  }

  calculatorForm.reset();

  const toggles = [
    toggleEmployment,
    toggleFreelance,
    toggleAgricultural,
    toggleOther,
    toggleRental,
    toggleInvestment,
    toggleDeductions,
    toggleObligations,
  ];

  toggles.forEach((toggle) => {
    if (!toggle) {
      return;
    }
    if (typeof toggle.defaultChecked === "boolean") {
      toggle.checked = toggle.defaultChecked;
    }
    handleSectionToggle(toggle);
  });

  getNumericInputs().forEach((input) => {
    clearFieldError(input);
    const defaultValue = input.defaultValue ?? "0";
    input.value = defaultValue;
  });

  calculatorForm
    .querySelectorAll(".form-control.has-error")
    .forEach((control) => control.classList.remove("has-error"));

  calculatorForm
    .querySelectorAll(".form-error")
    .forEach((element) => element.remove());

  resetResults();
  setCalculatorStatus(t("status.ready"));

  if (yearSelect) {
    const selectedYear = Number.parseInt(yearSelect.value ?? "", 10);
    if (Number.isFinite(selectedYear)) {
      applyYearMetadata(selectedYear);
    }
  }

  refreshInvestmentCategories();
  refreshDeductionHints();
  syncFreelanceActivityDerivedState();
  updateFreelanceCategoryHint();
  updateTradeFeeHint();
  updatePartialYearWarningState();

  try {
    window.localStorage.removeItem(CALCULATOR_STORAGE_KEY);
  } catch (error) {
    console.warn("Unable to clear stored calculator state", error);
  }
  updateEmploymentContributionPreview([]);
  assignLoadedCalculatorState(null);
  pendingCalculatorState = null;
  if (calculatorStatePersistHandle) {
    window.clearTimeout(calculatorStatePersistHandle);
    calculatorStatePersistHandle = null;
  }
}

async function submitCalculation(event) {
  event.preventDefault();
  resetResults();

  if (!calculatorForm) {
    return;
  }

  if (!validateForm()) {
    setCalculatorStatus(t("status.validation_errors"), { isError: true });
    return;
  }

  const payload = buildCalculationPayload();
  if (!payload.year) {
    setCalculatorStatus(t("status.select_year"), { isError: true });
    return;
  }

  setCalculatorStatus(t("status.calculating"));

  try {
    const response = await fetch(CALCULATIONS_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept-Language": currentLocale,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.message || response.statusText);
    }

    const result = await response.json();
    renderCalculation(result);
    setCalculatorStatus(t("status.calculation_complete"));
  } catch (error) {
    console.error("Calculation request failed", error);
    setCalculatorStatus(
      error instanceof Error ? error.message : t("status.calculation_failed"),
      { isError: true },
    );
  }
}

function downloadJsonSummary() {
  if (!lastCalculation) {
    return;
  }

  const exportData = buildSummaryExportData(lastCalculation, {
    useNonBreakingSpace: false,
    includeSource: true,
  });
  if (!exportData) {
    return;
  }

  const filename = buildDownloadFilename("json");
  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);

  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);

  URL.revokeObjectURL(url);
}

function escapeCsvValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  const string = String(value);
  if (/[",\n]/.test(string)) {
    return `"${string.replace(/"/g, '""')}"`;
  }
  return string;
}

const SUMMARY_EXPORT_FIELDS = [
  { key: "income_total", type: "currency" },
  { key: "taxable_income", type: "currency" },
  { key: "tax_total", type: "currency" },
  { key: "withholding_tax", type: "currency", optional: true },
  { key: "balance_due", type: "currency", optional: true },
  { key: "net_income", type: "currency" },
  { key: "net_monthly_income", type: "currency" },
  { key: "average_monthly_tax", type: "currency" },
  {
    key: "effective_tax_rate",
    type: "percent",
    formatOptions: { maximumFractionDigits: 1, minimumFractionDigits: 0 },
  },
  { key: "deductions_entered", type: "currency" },
  { key: "deductions_applied", type: "currency" },
];

const DETAIL_EXPORT_FIELDS = [
  { key: "gross_income", type: "currency" },
  { key: "monthly_gross_income", type: "currency", skipZero: true },
  { key: "payments_per_year", type: "integer" },
  { key: "gross_income_per_payment", type: "currency", skipZero: true },
  { key: "deductible_contributions", type: "currency", skipZero: true },
  { key: "category_contributions", type: "currency", skipZero: true },
  { key: "additional_contributions", type: "currency", skipZero: true },
  { key: "auxiliary_contributions", type: "currency", skipZero: true },
  { key: "lump_sum_contributions", type: "currency", skipZero: true },
  { key: "employee_contributions", type: "currency", skipZero: true },
  { key: "employee_contributions_manual", type: "currency", skipZero: true },
  { key: "employee_contributions_per_payment", type: "currency", skipZero: true },
  { key: "employer_contributions", type: "currency", skipZero: true },
  { key: "employer_contributions_per_payment", type: "currency", skipZero: true },
  { key: "deductible_expenses", type: "currency", skipZero: true },
  { key: "taxable_income", type: "currency" },
  { key: "tax_before_credits", type: "currency", skipZero: true },
  { key: "credits", type: "currency", skipZero: true },
  { key: "tax", type: "currency", skipZero: true },
  { key: "trade_fee", type: "currency", skipZero: true },
  { key: "total_tax", type: "currency", skipZero: true },
  { key: "net_income", type: "currency" },
  { key: "net_income_per_payment", type: "currency", skipZero: true },
  { key: "deductions_applied", type: "currency", skipZero: true },
];

const DEDUCTION_EXPORT_FIELDS = [
  { key: "entered", type: "currency", translationKey: "export.deductions.entered" },
  { key: "eligible", type: "currency", translationKey: "export.deductions.eligible" },
  {
    key: "credit_rate",
    type: "percent",
    translationKey: "export.deductions.credit_rate",
    formatOptions: { maximumFractionDigits: 2, minimumFractionDigits: 0 },
  },
  {
    key: "credit_requested",
    type: "currency",
    translationKey: "export.deductions.credit_requested",
  },
  {
    key: "credit_applied",
    type: "currency",
    translationKey: "export.deductions.credit_applied",
  },
];

function shouldSkipValue(value, skipZero) {
  if (!skipZero) {
    return false;
  }
  const numeric = coerceFiniteNumber(value);
  return Math.abs(numeric) < 0.005;
}

function createFormattedEntry({
  key,
  label,
  value,
  type,
  locale,
  useNonBreakingSpace,
  formatOptions = {},
  skipZero = false,
}) {
  if (value === null || value === undefined) {
    return null;
  }
  if (shouldSkipValue(value, skipZero)) {
    return null;
  }

  let formatted;
  switch (type) {
    case "currency":
      formatted = formatCurrency(value, {
        locale,
        useNonBreakingSpace,
        ...formatOptions,
      });
      break;
    case "percent":
      formatted = formatPercent(value, {
        locale,
        useNonBreakingSpace,
        maximumFractionDigits: formatOptions.maximumFractionDigits,
        minimumFractionDigits: formatOptions.minimumFractionDigits,
      });
      break;
    case "integer":
      formatted = formatInteger(value, { locale });
      break;
    default:
      formatted = String(value);
      break;
  }

  return {
    key,
    label,
    raw: value,
    formatted,
    type,
  };
}

function buildSummaryExportData(calculation, {
  locale: localeOverride,
  useNonBreakingSpace = true,
  includeSource = false,
} = {}) {
  if (!calculation) {
    return null;
  }

  const locale = normaliseLocaleChoice(localeOverride || getActiveLocale());
  const summary = calculation.summary || {};
  const summaryLabels = summary.labels || {};
  const details = Array.isArray(calculation.details) ? calculation.details : [];
  const meta = calculation.meta || {};
  const generatedAtDate = new Date();
  const generatedAtIso = generatedAtDate.toISOString();

  const exportData = {
    locale,
    localeTag: resolveLocaleTag(locale),
    currency: DEFAULT_CURRENCY,
    generatedAt: generatedAtIso,
    summary: [],
    details: [],
    deductions: [],
    meta: { entries: [], raw: meta },
    summaryRaw: summary,
    detailsRaw: details,
  };

  if (includeSource) {
    exportData.source = calculation;
  }

  SUMMARY_EXPORT_FIELDS.forEach((field) => {
    if (!(field.key in summary)) {
      if (field.optional) {
        return;
      }
    }
    const value = summary[field.key];
    if (value === undefined || value === null) {
      if (field.optional) {
        return;
      }
    }
    const label = resolveSummaryLabel(field.key, summaryLabels, locale);
    const entry = createFormattedEntry({
      key: field.key,
      label,
      value,
      type: field.type,
      locale,
      useNonBreakingSpace,
      formatOptions: field.formatOptions,
      skipZero: field.skipZero,
    });
    if (entry) {
      exportData.summary.push(entry);
    }
  });

  if (Array.isArray(summary.deductions_breakdown)) {
    summary.deductions_breakdown.forEach((entry) => {
      if (!entry) {
        return;
      }
      const sectionLabel =
        (typeof entry.label === "string" && entry.label.trim()) || entry.type ||
        t("export.csv.section.deductions", {}, locale) ||
        "Deductions";
      const fields = [];
      DEDUCTION_EXPORT_FIELDS.forEach((field) => {
        const value = entry[field.key];
        const label =
          t(field.translationKey, {}, locale) || field.translationKey || field.key;
        const formatted = createFormattedEntry({
          key: field.key,
          label,
          value,
          type: field.type,
          locale,
          useNonBreakingSpace,
          formatOptions: field.formatOptions,
        });
        if (formatted) {
          fields.push(formatted);
        }
      });
      const notes =
        typeof entry.notes === "string" && entry.notes.trim()
          ? entry.notes.trim()
          : null;
      if (fields.length || notes) {
        exportData.deductions.push({
          key: entry.type || sectionLabel,
          label: sectionLabel,
          entries: fields,
          notes,
        });
      }
    });
  }

  const detailLabels = getMessagesSection(locale, "detailFields");
  details.forEach((detail, index) => {
    if (!detail) {
      return;
    }
    const sectionLabel =
      (typeof detail.label === "string" && detail.label.trim()) ||
      detail.category ||
      `${t("export.csv.section.detail", {}, locale) || "Detail"} ${index + 1}`;

    const entries = [];
    DETAIL_EXPORT_FIELDS.forEach((field) => {
      const value = detail[field.key];
      const label = resolveDetailLabel(detail, field.key, detailLabels, locale);
      const formatted = createFormattedEntry({
        key: field.key,
        label,
        value,
        type: field.type,
        locale,
        useNonBreakingSpace,
        formatOptions: field.formatOptions,
        skipZero: field.skipZero,
      });
      if (formatted) {
        entries.push(formatted);
      }
    });

    const items = [];
    if (Array.isArray(detail.items)) {
      detail.items.forEach((item) => {
        if (!item) {
          return;
        }
        const amountValue = coerceFiniteNumber(item.amount);
        const taxValue = coerceFiniteNumber(item.tax);
        if (!Number.isFinite(amountValue) && !Number.isFinite(taxValue)) {
          return;
        }
        const label =
          (typeof item.label === "string" && item.label.trim()) ||
          resolveDetailLabel(detail, "breakdown", detailLabels, locale);
        const amount = {
          raw: item.amount,
          formatted: formatCurrency(amountValue, {
            locale,
            useNonBreakingSpace,
          }),
        };
        const tax = {
          raw: item.tax,
          formatted: formatCurrency(taxValue, {
            locale,
            useNonBreakingSpace,
          }),
        };
        let rate = null;
        const rateValue = coerceFiniteNumber(item.rate);
        if (Number.isFinite(rateValue) && Math.abs(rateValue) > 0) {
          rate = {
            raw: item.rate,
            formatted: formatPercent(rateValue, {
              locale,
              useNonBreakingSpace,
              maximumFractionDigits: 2,
              minimumFractionDigits: 0,
            }),
          };
        }
        items.push({ label, amount, tax, rate });
      });
    }

    if (entries.length || items.length) {
      exportData.details.push({
        key: detail.category || detail.label || `detail-${index}`,
        label: sectionLabel,
        entries,
        items,
      });
    }
  });

  const metaEntries = [];
  const generatedLabel = t("export.meta.generated_at", {}, locale) || "Generated";
  metaEntries.push({
    key: "generated_at",
    label: generatedLabel,
    raw: generatedAtIso,
    formatted: formatDateTime(generatedAtDate, { locale }),
    type: "datetime",
  });

  if (meta.year !== undefined && meta.year !== null) {
    metaEntries.push({
      key: "year",
      label: t("export.meta.year", {}, locale) || "Tax year",
      raw: meta.year,
      formatted: formatInteger(meta.year, { locale }),
      type: "integer",
    });
  }

  const metaLocale = normaliseLocaleChoice(meta.locale || locale);
  metaEntries.push({
    key: "locale",
    label: t("export.meta.locale", {}, locale) || "Locale",
    raw: resolveLocaleTag(metaLocale),
    formatted: resolveLocaleTag(metaLocale),
    type: "text",
  });

  metaEntries.push({
    key: "currency",
    label: t("export.meta.currency", {}, locale) || "Currency",
    raw: DEFAULT_CURRENCY,
    formatted: DEFAULT_CURRENCY,
    type: "text",
  });

  if (meta.youth_relief_category) {
    metaEntries.push({
      key: "youth_relief_category",
      label: t("export.meta.youth_relief_category", {}, locale) ||
        "Youth relief category",
      raw: meta.youth_relief_category,
      formatted: String(meta.youth_relief_category),
      type: "text",
    });
  }

  if (Array.isArray(meta.presumptive_adjustments) && meta.presumptive_adjustments.length) {
    metaEntries.push({
      key: "presumptive_adjustments",
      label:
        t("export.meta.presumptive_adjustments", {}, locale) ||
        "Presumptive adjustments",
      raw: meta.presumptive_adjustments,
      formatted: formatList(meta.presumptive_adjustments, locale),
      type: "list",
    });
  }

  exportData.meta.entries = metaEntries;

  return exportData;
}

function escapeHtml(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function downloadCsvSummary() {
  if (!lastCalculation) {
    return;
  }

  const exportData = buildSummaryExportData(lastCalculation, {
    useNonBreakingSpace: false,
  });
  if (!exportData) {
    return;
  }

  const locale = exportData.locale;
  const header = [
    t("export.csv.header_section", {}, locale) || "Section",
    t("export.csv.header_label", {}, locale) || "Label",
    t("export.csv.header_value", {}, locale) || "Value",
  ];

  const sectionLabels = {
    meta: t("export.csv.section.meta", {}, locale) || "Meta",
    summary: t("export.csv.section.summary", {}, locale) || "Summary",
    deductions: t("export.csv.section.deductions", {}, locale) || "Deductions",
    detail: t("export.csv.section.detail", {}, locale) || "Detail",
  };

  const lines = [header];

  if (exportData.meta.entries.length) {
    exportData.meta.entries.forEach((entry) => {
      lines.push([sectionLabels.meta, entry.label, entry.formatted]);
    });
  }

  exportData.summary.forEach((entry) => {
    lines.push([sectionLabels.summary, entry.label, entry.formatted]);
  });

  exportData.deductions.forEach((deduction) => {
    deduction.entries.forEach((entry) => {
      lines.push([
        sectionLabels.deductions,
        `${deduction.label} – ${entry.label}`,
        entry.formatted,
      ]);
    });
    if (deduction.notes) {
      const notesLabel =
        t("export.deductions.notes", {}, locale) || "Notes";
      lines.push([
        sectionLabels.deductions,
        `${deduction.label} – ${notesLabel}`,
        deduction.notes,
      ]);
    }
  });

  exportData.details.forEach((detail) => {
    detail.entries.forEach((entry) => {
      lines.push([
        sectionLabels.detail,
        `${detail.label} – ${entry.label}`,
        entry.formatted,
      ]);
    });
    detail.items.forEach((item) => {
      const ratePart = item.rate && item.rate.formatted ? ` (${item.rate.formatted})` : "";
      const formattedValue = `${item.amount.formatted} → ${item.tax.formatted}${ratePart}`;
      lines.push([
        sectionLabels.detail,
        `${detail.label} – ${item.label}`,
        formattedValue,
      ]);
    });
  });

  const csvContent = lines
    .map((row) => row.map((value) => escapeCsvValue(value)).join(","))
    .join("\n");

  const blob = new Blob([csvContent], { type: "text/csv; charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = buildDownloadFilename("csv");
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function printSummary() {
  if (!lastCalculation) {
    return;
  }

  const exportData = buildSummaryExportData(lastCalculation, {
    useNonBreakingSpace: false,
  });
  if (!exportData) {
    return;
  }

  const locale = exportData.locale;
  const translate = (key, replacements = {}) => t(key, replacements, locale);
  const printWindow = window.open("", "_blank", "noopener=yes,noreferrer=yes");

  if (!printWindow) {
    window.print();
    return;
  }

  const title = translate("print.title") || "GreekTax summary";
  const heading = translate("print.heading") || title;
  const generatedLabel = translate("print.generated_on") || "Generated";
  const generatedDisplay = formatDateTime(exportData.generatedAt, { locale });
  const footerText =
    translate("print.footer", { year: new Date().getFullYear() }) ||
    "© 2025 Christos Ntanos for CogniSys. Released under the GNU GPL v3.";

  const tableHeaderSection =
    translate("export.csv.header_section") || "Section";
  const tableHeaderLabel = translate("export.csv.header_label") || "Label";
  const tableHeaderValue = translate("export.csv.header_value") || "Value";

  const sectionLabels = {
    meta: translate("export.csv.section.meta") || "Meta",
    summary: translate("export.csv.section.summary") || "Summary",
    deductions: translate("export.csv.section.deductions") || "Deductions",
    detail: translate("export.csv.section.detail") || "Detail",
  };

  const rows = [];
  const pushRow = (section, label, value) => {
    if (label === undefined || label === null) {
      return;
    }
    if (value === undefined || value === null) {
      return;
    }
    const trimmedLabel = String(label).trim();
    const trimmedValue = String(value).trim();
    if (!trimmedLabel && !trimmedValue) {
      return;
    }
    rows.push({ section, label: trimmedLabel, value: trimmedValue });
  };

  exportData.meta.entries.forEach((entry) => {
    pushRow(sectionLabels.meta, entry.label, entry.formatted);
  });

  exportData.summary.forEach((entry) => {
    pushRow(sectionLabels.summary, entry.label, entry.formatted);
  });

  exportData.deductions.forEach((deduction) => {
    deduction.entries.forEach((entry) => {
      pushRow(
        sectionLabels.deductions,
        `${deduction.label} – ${entry.label}`,
        entry.formatted,
      );
    });
    if (deduction.notes) {
      const notesLabel =
        translate("export.deductions.notes") || "Notes";
      pushRow(
        sectionLabels.deductions,
        `${deduction.label} – ${notesLabel}`,
        deduction.notes,
      );
    }
  });

  exportData.details.forEach((detail) => {
    detail.entries.forEach((entry) => {
      pushRow(
        sectionLabels.detail,
        `${detail.label} – ${entry.label}`,
        entry.formatted,
      );
    });
    detail.items.forEach((item) => {
      const ratePart = item.rate && item.rate.formatted ? ` (${item.rate.formatted})` : "";
      const value = `${item.amount.formatted} → ${item.tax.formatted}${ratePart}`;
      pushRow(
        sectionLabels.detail,
        `${detail.label} – ${item.label}`,
        value,
      );
    });
  });

  const tableBody = rows
    .map(
      (row) =>
        `<tr><td class="section">${escapeHtml(row.section)}</td><td class="label">${escapeHtml(
          row.label,
        )}</td><td class="value">${escapeHtml(row.value)}</td></tr>`,
    )
    .join("");

  const documentHtml = `<!doctype html>
    <html lang="${escapeHtml(locale)}">
      <head>
        <meta charset="utf-8" />
        <title>${escapeHtml(title)}</title>
        <style>
          :root {
            color-scheme: light;
          }
          body {
            font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
            margin: 1.5rem;
            color: #1a1a1a;
            background: #ffffff;
          }
          .print-wrapper {
            max-width: 840px;
            margin: 0 auto;
          }
          header {
            margin-bottom: 1.25rem;
          }
          h1 {
            font-size: 1.75rem;
            margin: 0 0 0.25rem;
          }
          .print-generated {
            margin: 0;
            font-size: 0.95rem;
            color: #4f4f4f;
          }
          table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
          }
          thead th {
            text-align: left;
            padding: 0.5rem;
            border-bottom: 2px solid #1a1a1a;
            font-weight: 600;
            font-size: 0.95rem;
          }
          tbody td {
            padding: 0.5rem;
            border-bottom: 1px solid #d7d7d7;
            font-size: 0.95rem;
            vertical-align: top;
          }
          tbody td.section {
            width: 20%;
            font-weight: 600;
          }
          tbody td.label {
            width: 45%;
            color: #333333;
          }
          tbody td.value {
            width: 35%;
            text-align: right;
            font-variant-numeric: tabular-nums;
            color: #111111;
          }
          footer {
            margin-top: 1.5rem;
            font-size: 0.9rem;
            color: #4f4f4f;
            border-top: 1px solid #d7d7d7;
            padding-top: 0.75rem;
          }
          @media print {
            body {
              margin: 0.5in;
            }
            .print-wrapper {
              max-width: none;
            }
            footer {
              color: #6b6b6b;
            }
          }
        </style>
      </head>
      <body>
        <div class="print-wrapper">
          <header>
            <h1>${escapeHtml(heading)}</h1>
            <p class="print-generated">${escapeHtml(generatedLabel)}: ${escapeHtml(
    generatedDisplay,
  )}</p>
          </header>
          <table>
            <thead>
              <tr>
                <th>${escapeHtml(tableHeaderSection)}</th>
                <th>${escapeHtml(tableHeaderLabel)}</th>
                <th>${escapeHtml(tableHeaderValue)}</th>
              </tr>
            </thead>
            <tbody>
              ${tableBody}
            </tbody>
          </table>
          <footer>${escapeHtml(footerText)}</footer>
        </div>
      </body>
    </html>`;

  printWindow.document.open();
  printWindow.document.write(documentHtml);
  printWindow.document.close();
  printWindow.focus();

  const handlePrint = () => {
    try {
      printWindow.print();
    } finally {
      printWindow.close();
    }
  };

  if (printWindow.document.readyState === "complete") {
    handlePrint();
  } else {
    printWindow.addEventListener("load", handlePrint, { once: true });
  }
}

function initialiseCalculator() {
  if (!calculatorForm || !yearSelect) {
    return;
  }

  const storedCalculatorState = loadStoredCalculatorState();
  assignLoadedCalculatorState(storedCalculatorState);
  pendingCalculatorState = loadedCalculatorState
    ? Object.assign({}, loadedCalculatorState)
    : null;
  applyPendingCalculatorState();

  if (pensionModeSelect) {
    currentPensionMode = pensionModeSelect.value || "gross";
    updatePensionMode(currentPensionMode);
  }

  if (employmentModeSelect) {
    currentEmploymentMode = employmentModeSelect.value || "annual";
    updateEmploymentMode(currentEmploymentMode);
  } else {
    updateEmploymentMode(currentEmploymentMode);
  }

  initialiseSectionToggles();
  applyPendingCalculatorState();
  freelanceEfkaSelect?.addEventListener("change", updateFreelanceCategoryHint);
  freelanceEfkaMonthsInput?.addEventListener("input", updateFreelanceCategoryHint);
  freelanceActivityStartInput?.addEventListener("input", () => {
    syncFreelanceActivityDerivedState();
    updateTradeFeeHint();
  });
  freelanceTradeFeeLocationSelect?.addEventListener(
    "change",
    updateTradeFeeHint,
  );

  calculatorForm.addEventListener("submit", submitCalculation);
  calculatorForm.addEventListener("input", handleCalculatorStateChange);
  calculatorForm.addEventListener("change", handleCalculatorStateChange);
  yearSelect.addEventListener("change", () => {
    const selectedYear = Number.parseInt(yearSelect.value ?? "", 10);
    if (Number.isFinite(selectedYear)) {
      applyYearMetadata(selectedYear);
    }
    refreshInvestmentCategories();
    refreshDeductionHints();
    syncFreelanceActivityDerivedState();
    updateFreelanceCategoryHint();
    updateTradeFeeHint();
  });

  pensionModeSelect?.addEventListener("change", (event) => {
    const target = event.target;
    const value = typeof target?.value === "string" ? target.value : "annual";
    updatePensionMode(value);
    updatePartialYearWarningState();
  });
  pensionIncomeInput?.addEventListener("input", updatePartialYearWarningState);
  pensionMonthlyIncomeInput?.addEventListener(
    "input",
    updatePartialYearWarningState,
  );
  employmentPaymentsInput?.addEventListener("change", updatePartialYearWarningState);
  pensionPaymentsInput?.addEventListener("change", updatePartialYearWarningState);
  employmentModeSelect?.addEventListener("change", (event) => {
    const target = event.target;
    const value = typeof target?.value === "string" ? target.value : "annual";
    updateEmploymentMode(value);
  });
  employmentEmployeeContributionsInput?.addEventListener("input", () => {
    updateEmploymentContributionPreview(lastCalculation?.details || []);
  });
  employmentIncludeSocialToggle?.addEventListener("change", () => {
    updateEmploymentContributionPreview(lastCalculation?.details || []);
  });

  downloadButton?.addEventListener("click", downloadJsonSummary);
  downloadCsvButton?.addEventListener("click", downloadCsvSummary);
  printButton?.addEventListener("click", printSummary);
  clearButton?.addEventListener("click", clearCalculatorForm);

  attachValidationHandlers();
  updatePartialYearWarningState();

  updateEmploymentContributionPreview(lastCalculation?.details || []);
  applyEmploymentModeLabels();

  loadYearOptions()
    .then(async () => {
      applyPendingCalculatorState();
      await refreshInvestmentCategories();
      applyPendingCalculatorState();
      await refreshDeductionHints();
      applyPendingCalculatorState();
    })
    .finally(() => {
      updateEmploymentContributionPreview(lastCalculation?.details || []);
      applyEmploymentModeLabels();
    });
}

async function bootstrap() {
  const initialTheme = resolveStoredTheme();
  applyTheme(initialTheme);
  const initialLocale = resolveStoredLocale();
  await applyLocale(initialLocale);

  initialiseLocaleControls();
  initialiseThemeControls();
  initialiseCalculator();
  void refreshApplicationVersion();

  console.info("GreekTax interface initialised");
}

document.addEventListener("DOMContentLoaded", () => {
  void bootstrap();
});
