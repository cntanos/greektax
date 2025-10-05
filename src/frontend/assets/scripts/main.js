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
let currentPensionMode = "gross";
let currentPensionNetInputMode = "annual";
let currentInvestmentCategories = [];
let currentDeductionHints = [];
let currentFreelanceMetadata = null;
let derivedFreelanceYearsActive = null;
let derivedFreelanceNewlySelfEmployed = false;
let dynamicFieldLabels = {};
let deductionValidationByInput = {};
let lastCalculation = null;
let pendingCalculatorState = null;
let calculatorStatePersistHandle = null;
let isApplyingYearMetadata = false;
let partialYearWarningActive = false;

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
const employmentIncomeInput = document.getElementById("employment-income");
const employmentMonthlyIncomeInput = document.getElementById(
  "employment-monthly-income",
);
const employmentEmployeeContributionsInput = document.getElementById(
  "employment-employee-contributions",
);
const employmentPaymentsInput = document.getElementById("employment-payments");
const employmentWithholdingInput = document.getElementById(
  "employment-withholding",
);
const employmentModeSelect = document.getElementById("employment-mode");
const yearAlertsContainer = document.getElementById("year-alerts");
const pensionModeSelect = document.getElementById("pension-mode");
const pensionNetInputModeSelect = document.getElementById(
  "pension-net-input-mode",
);
const pensionPaymentsInput = document.getElementById("pension-payments");
const pensionIncomeInput = document.getElementById("pension-income");
const pensionNetIncomeInput = document.getElementById("pension-net-income");
const pensionNetMonthlyIncomeInput = document.getElementById(
  "pension-net-monthly-income",
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
const freelanceEfkaSelect = document.getElementById("freelance-efka-category");
const freelanceEfkaMonthsInput = document.getElementById("freelance-efka-months");
const freelanceEfkaHint = document.getElementById("freelance-efka-category-hint");
const freelanceTradeFeeLocationSelect = document.getElementById(
  "freelance-trade-fee-location",
);
const freelanceTradeFeeHint = document.getElementById("freelance-trade-fee-hint");
const freelanceYearsActiveInput = document.getElementById("freelance-years-active");
const freelanceEfkaSummary = document.getElementById("freelance-efka-summary");
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
const toggleFreelance = document.getElementById("toggle-freelance");
const toggleEmployment = document.getElementById("toggle-employment");
const toggleAgricultural = document.getElementById("toggle-agricultural");
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
  if (!element || !element.id) {
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
  elements.forEach((element) => {
    const value = captureElementValue(element);
    if (value === undefined) {
      return;
    }
    values[element.id] = value;
  });
  return values;
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
    ...(pendingCalculatorState || {}),
    ...snapshot,
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

const GREEK_GROUP_SEPARATOR = ".";
const GREEK_DECIMAL_SEPARATOR = ",";
const NON_BREAKING_SPACE = "\u00a0";
const GROUPING_REGEX = /\B(?=(\d{3})+(?!\d))/g;

function coerceFiniteNumber(value) {
  const parsed = Number.parseFloat(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
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
  renderYearWarnings(currentYearMetadata, {
    showPartialYearWarning: partialYearWarningActive,
  });
  preserveCurrentFormValues();
  refreshInvestmentCategories();
  refreshDeductionHints();
  populateFreelanceMetadata(currentFreelanceMetadata);
  if (lastCalculation) {
    renderCalculation(lastCalculation);
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

function formatNumber(value) {
  const numeric = coerceFiniteNumber(value);
  const rounded = Math.round(numeric * 100) / 100;
  const sign = rounded < 0 ? "-" : "";
  const absolute = Math.abs(rounded);
  let [integerPart, fractionPart = ""] = absolute.toFixed(2).split(".");
  integerPart = integerPart.replace(GROUPING_REGEX, GREEK_GROUP_SEPARATOR);
  fractionPart = fractionPart.replace(/0+$/, "");
  const decimalPart = fractionPart
    ? `${GREEK_DECIMAL_SEPARATOR}${fractionPart}`
    : "";
  return `${sign}${integerPart}${decimalPart}`;
}

function formatCurrency(value) {
  const numeric = coerceFiniteNumber(value);
  const sign = numeric < 0 ? "-" : "";
  const absolute = Math.abs(numeric);
  let [integerPart, fractionPart = ""] = absolute.toFixed(2).split(".");
  integerPart = integerPart.replace(GROUPING_REGEX, GREEK_GROUP_SEPARATOR);
  const formatted = `${integerPart}${GREEK_DECIMAL_SEPARATOR}${fractionPart}`;
  return `${sign}${formatted}${NON_BREAKING_SPACE}€`;
}

function formatPercent(value) {
  const numeric = coerceFiniteNumber(value) * 100;
  const rounded = Math.round(numeric * 10) / 10;
  const sign = rounded < 0 ? "-" : "";
  const absolute = Math.abs(rounded);
  let [integerPart, fractionPart = ""] = absolute.toFixed(1).split(".");
  integerPart = integerPart.replace(GROUPING_REGEX, GREEK_GROUP_SEPARATOR);
  fractionPart = fractionPart.replace(/0+$/, "");
  const decimalPart = fractionPart
    ? `${GREEK_DECIMAL_SEPARATOR}${fractionPart}`
    : "";
  return `${sign}${integerPart}${decimalPart}%`;
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
  if (!isSectionActive(employmentSection)) {
    return false;
  }
  if (hasPartialYearSelection(employmentPaymentsInput)) {
    return true;
  }
  if (!hasPensionEntries()) {
    return false;
  }
  return hasPartialYearSelection(pensionPaymentsInput);
}

function hasPensionEntries() {
  if (currentPensionMode === "net") {
    if (currentPensionNetInputMode === "per_payment") {
      return readNumber(pensionNetMonthlyIncomeInput) > 0;
    }
    return readNumber(pensionNetIncomeInput) > 0;
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
  if (toggle === toggleEmployment) {
    updatePartialYearWarningState();
  }
}

function initialiseSectionToggles() {
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

function applyPendingCalculatorState() {
  if (!pendingCalculatorState) {
    return;
  }

  const remaining = {};
  let yearUpdated = false;

  Object.entries(pendingCalculatorState).forEach(([id, storedValue]) => {
    const element = document.getElementById(id);
    if (!element) {
      remaining[id] = storedValue;
      return;
    }

    const applied = applyValueToElement(element, storedValue);
    if (!applied) {
      remaining[id] = storedValue;
      return;
    }

    if (id === "year-select") {
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
    updatePensionMode(pensionModeSelect.value || "gross");
  }

  if (employmentModeSelect) {
    updateEmploymentMode(employmentModeSelect.value || "annual");
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
  currentPensionMode = mode === "net" ? "net" : "gross";
  if (pensionModeSelect) {
    pensionModeSelect.value = currentPensionMode;
  }
  updateSectionMode("pension", currentPensionMode, "gross");
  updatePensionNetInputMode(pensionNetInputModeSelect?.value);
}

function updatePensionNetInputMode(mode) {
  const resolvedMode = mode === "per_payment" ? "per_payment" : "annual";
  currentPensionNetInputMode = resolvedMode;
  if (pensionNetInputModeSelect) {
    pensionNetInputModeSelect.value = currentPensionNetInputMode;
  }
  const shouldDisplayNetControls = currentPensionMode === "net";
  document
    .querySelectorAll(
      '.form-control[data-section="pension"][data-net-input-mode]',
    )
    .forEach((control) => {
      const controlMode = control.getAttribute("data-net-input-mode");
      const isVisible = shouldDisplayNetControls && controlMode === resolvedMode;
      control.hidden = !isVisible;
      if (!isVisible) {
        const input = control.querySelector("input");
        if (input) {
          clearFieldError(input);
        }
      }
    });
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

    updateEmploymentMode(currentEmploymentMode);
    updatePensionMode(currentPensionMode);
    populateFreelanceMetadata(currentYearMetadata?.freelance || null);
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

    if (payload.default_year) {
      yearSelect.value = String(payload.default_year);
    }

    const selectedYear = Number.parseInt(yearSelect.value ?? "", 10);
    if (Number.isFinite(selectedYear)) {
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
    if (category?.description_key) {
      freelanceEfkaHint.textContent = t(category.description_key);
      freelanceEfkaHint.hidden = false;
    } else {
      const defaultMessage = t("hints.freelance-efka-category");
      if (!category && defaultMessage) {
        freelanceEfkaHint.textContent = defaultMessage;
        freelanceEfkaHint.hidden = false;
      } else {
        freelanceEfkaHint.textContent = "";
        freelanceEfkaHint.hidden = true;
      }
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
      option.textContent = `${t(category.label_key)} (${formatCurrency(
        category.monthly_amount || 0,
      )}/month)`;
      option.dataset.monthlyAmount = String(category.monthly_amount || 0);
      option.dataset.auxiliaryMonthlyAmount = String(
        category.auxiliary_monthly_amount || 0,
      );
      if (category.description_key) {
        option.dataset.descriptionKey = category.description_key;
      }
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

  const children = Number.parseInt(childrenInput?.value ?? "0", 10);
  if (Number.isFinite(children) && children > 0) {
    payload.dependents = { children };
  }

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

  if (isSectionActive(employmentSection) && isPensionEnabled()) {
    const pensionPayload = {};
    const pensionMode = pensionModeSelect?.value || currentPensionMode;
    if (pensionMode === "net") {
      const netMode =
        pensionNetInputModeSelect?.value === "per_payment"
          ? "per_payment"
          : currentPensionNetInputMode;
      if (netMode === "per_payment") {
        const netMonthly = readNumber(pensionNetMonthlyIncomeInput);
        if (netMonthly > 0) {
          pensionPayload.net_monthly_income = netMonthly;
        }
      } else {
        const netIncome = readNumber(pensionNetIncomeInput);
        if (netIncome > 0) {
          pensionPayload.net_income = netIncome;
        }
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
      (pensionPayload.net_income !== undefined ||
        pensionPayload.net_monthly_income !== undefined ||
        pensionPayload.gross_income !== undefined)
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

  return payload;
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

  const sankeyTotals = {
    taxes: t("sankey.taxes"),
    contributions: t("sankey.contributions"),
    net: t("sankey.net"),
  };

  const flowTaxes = getCssVariable("--flow-taxes", "#d63384");
  const flowContributions = getCssVariable("--flow-contributions", "#20c997");
  const flowNet = getCssVariable("--flow-net", "#0d6efd");
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
    taxes: colorWithAlpha(flowTaxes, 0.72, "rgba(214, 51, 132, 0.72)"),
    contributions: colorWithAlpha(
      flowContributions,
      0.72,
      "rgba(32, 201, 151, 0.72)",
    ),
    net: colorWithAlpha(flowNet, 0.72, "rgba(13, 110, 253, 0.72)"),
    default: colorWithAlpha(subtleColor, 0.6, "rgba(73, 80, 87, 0.6)"),
  };

  const nodeAccentColors = {
    [sankeyTotals.taxes]: colorWithAlpha(
      flowTaxes,
      0.18,
      "rgba(214, 51, 132, 0.18)",
    ),
    [sankeyTotals.contributions]: colorWithAlpha(
      flowContributions,
      0.18,
      "rgba(32, 201, 151, 0.18)",
    ),
    [sankeyTotals.net]: colorWithAlpha(flowNet, 0.18, "rgba(13, 110, 253, 0.18)"),
  };

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

  const toChartValue = (value) => {
    const number = Number.parseFloat(value ?? 0);
    if (!Number.isFinite(number) || number <= 0) {
      return 0;
    }
    return Math.round(number * 100) / 100;
  };

  const addLink = (source, target, value, label, tone = "default") => {
    const chartValue = toChartValue(value);
    if (!chartValue) {
      return;
    }
    sources.push(source);
    targets.push(target);
    values.push(chartValue);
    linkLabels.push(label);
    linkColors.push(linkColorPalette[tone] || linkColorPalette.default);
  };

  let taxesIndex = null;
  let contributionsIndex = null;
  let netIndex = null;

  const getTaxesIndex = () => {
    if (taxesIndex === null) {
      taxesIndex = ensureNode(t("sankey.taxes"));
    }
    return taxesIndex;
  };

  const getContributionsIndex = () => {
    if (contributionsIndex === null) {
      contributionsIndex = ensureNode(t("sankey.contributions"));
    }
    return contributionsIndex;
  };

  const getNetIndex = () => {
    if (netIndex === null) {
      netIndex = ensureNode(t("sankey.net"));
    }
    return netIndex;
  };

  details.forEach((detail) => {
    if (!detail) {
      return;
    }

    const grossRaw = Number.parseFloat(detail.gross_income ?? 0);
    if (!Number.isFinite(grossRaw) || grossRaw <= 0) {
      return;
    }

    const sourceLabel = detail.label || detail.category;
    if (!sourceLabel) {
      return;
    }

    const sourceIndex = ensureNode(sourceLabel);

    const taxRaw = Math.max(Number.parseFloat(detail.total_tax ?? detail.tax ?? 0), 0);
    let netRaw = Math.max(Number.parseFloat(detail.net_income ?? 0), 0);
    let contributionsRaw = Math.max(grossRaw - taxRaw - netRaw, 0);

    const allocated = taxRaw + netRaw + contributionsRaw;
    const difference = grossRaw - allocated;
    if (difference > 0.01) {
      netRaw += difference;
    } else if (difference < -0.01) {
      const adjustment = Math.min(netRaw, Math.abs(difference));
      netRaw -= adjustment;
      const remaining = difference + adjustment;
      if (remaining < -0.01) {
        const contributionAdjustment = Math.min(contributionsRaw, Math.abs(remaining));
        contributionsRaw -= contributionAdjustment;
      }
    }

    addLink(
      sourceIndex,
      getTaxesIndex(),
      taxRaw,
      `${sourceLabel} → ${t("sankey.taxes")}: ${formatCurrency(taxRaw)}`,
      "taxes",
    );

    if (contributionsRaw > 0.005) {
      addLink(
        sourceIndex,
        getContributionsIndex(),
        contributionsRaw,
        `${sourceLabel} → ${t("sankey.contributions")}: ${formatCurrency(
          contributionsRaw,
        )}`,
        "contributions",
      );
    }

    if (netRaw > 0.005) {
      addLink(
        sourceIndex,
        getNetIndex(),
        netRaw,
        `${sourceLabel} → ${t("sankey.net")}: ${formatCurrency(netRaw)}`,
        "net",
      );
    }
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
        sankeyChart.setAttribute("aria-label", t("sankey.aria_label"));
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

const DISTRIBUTION_CONTRIBUTION_FIELDS = [
  "deductible_contributions",
  "category_contributions",
  "additional_contributions",
  "auxiliary_contributions",
  "lump_sum_contributions",
  "mandatory_contributions",
  "employee_contributions",
  "employee_contributions_manual",
  "employer_contributions",
];

const DISTRIBUTION_EXPENSE_FIELDS = ["deductible_expenses"];

const DISTRIBUTION_CATEGORIES = [
  { key: "profits", colorVar: "--flow-net" },
  { key: "taxes", colorVar: "--flow-taxes" },
  { key: "insurance", colorVar: "--flow-contributions" },
  { key: "expenses", colorVar: "--flow-expenses" },
];

const DISTRIBUTION_FALLBACK_COLORS = {
  profits: "#0f6dff",
  taxes: "#ff4d6a",
  insurance: "#00bfa6",
  expenses: "#f5a524",
};

function toFiniteNumber(value) {
  const parsed = Number.parseFloat(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
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

function computeDistributionTotals(details) {
  const totals = { profits: 0, taxes: 0, insurance: 0, expenses: 0 };
  const entries = Array.isArray(details) ? details : [];

  entries.forEach((detail) => {
    if (!detail) {
      return;
    }

    const gross = Math.max(toFiniteNumber(detail.gross_income), 0);
    const rawNet = toFiniteNumber(detail.net_income);
    let profitValue = rawNet > 0 ? rawNet : 0;

    const taxCandidate =
      detail.total_tax !== undefined && detail.total_tax !== null
        ? detail.total_tax
        : detail.tax;
    let taxValue = Math.max(toFiniteNumber(taxCandidate), 0);

    let insuranceValue = sumDetailFields(
      detail,
      DISTRIBUTION_CONTRIBUTION_FIELDS,
    );
    let expenseValue = sumDetailFields(detail, DISTRIBUTION_EXPENSE_FIELDS);

    if (rawNet < 0) {
      expenseValue += Math.abs(rawNet);
    }

    const allocated = taxValue + insuranceValue + expenseValue + profitValue;

    if (gross > 0) {
      const difference = gross - allocated;
      if (difference > 0.01) {
        profitValue += difference;
      } else if (difference < -0.01) {
        let remaining = Math.abs(difference);

        if (profitValue > 0) {
          const reduction = Math.min(profitValue, remaining);
          profitValue -= reduction;
          remaining -= reduction;
        }

        if (remaining > 0 && expenseValue > 0) {
          const reduction = Math.min(expenseValue, remaining);
          expenseValue -= reduction;
          remaining -= reduction;
        }

        if (remaining > 0 && insuranceValue > 0) {
          const reduction = Math.min(insuranceValue, remaining);
          insuranceValue -= reduction;
          remaining -= reduction;
        }

        if (remaining > 0 && taxValue > 0) {
          const reduction = Math.min(taxValue, remaining);
          taxValue -= reduction;
        }
      }
    }

    totals.profits += Math.max(profitValue, 0);
    totals.taxes += Math.max(taxValue, 0);
    totals.insurance += Math.max(insuranceValue, 0);
    totals.expenses += Math.max(expenseValue, 0);
  });

  const totalValue =
    totals.profits + totals.taxes + totals.insurance + totals.expenses;

  return { totals, totalValue };
}

function renderDistributionChart(details) {
  if (!distributionWrapper || !distributionList || !distributionChart) {
    return;
  }

  distributionList.innerHTML = "";
  distributionChart.innerHTML = "";
  distributionChart.removeAttribute("aria-label");
  distributionChart.setAttribute("aria-hidden", "true");

  const { totals, totalValue } = computeDistributionTotals(details);
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

  const ring = document.createElementNS(SVG_NS, "circle");
  ring.setAttribute("class", "distribution-chart__ring");
  ring.setAttribute("cx", center);
  ring.setAttribute("cy", center);
  ring.setAttribute("r", radius);
  distributionChart.appendChild(ring);

  DISTRIBUTION_CATEGORIES.forEach(({ key, colorVar }) => {
    const value = Math.max(totals[key] || 0, 0);
    const ratio = safeTotal > 0 ? value / safeTotal : 0;
    const clampedRatio = Math.max(0, Math.min(ratio, 1));
    const strokeLength = clampedRatio * circumference;

    const cssColor = rootStyles ? rootStyles.getPropertyValue(colorVar) : "";
    const normalizedColor = cssColor && cssColor.trim().length
      ? cssColor.trim()
      : DISTRIBUTION_FALLBACK_COLORS[key] || "#0f6dff";

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
      distributionChart.appendChild(segment);
    }

    offset = Math.min(offset + strokeLength, circumference);

    const item = document.createElement("li");
    item.className = "distribution-legend__item";
    item.dataset.category = key;
    item.style.setProperty("--distribution-color", normalizedColor);

    const swatch = document.createElement("span");
    swatch.className = "distribution-legend__swatch";
    swatch.setAttribute("aria-hidden", "true");
    item.appendChild(swatch);

    const labelSpan = document.createElement("span");
    labelSpan.className = "distribution-legend__label";
    const labelText = t(`distribution.${key}`);
    labelSpan.textContent = labelText;
    item.appendChild(labelSpan);

    const amountSpan = document.createElement("span");
    amountSpan.className = "distribution-legend__amount";
    amountSpan.textContent = formatCurrency(value);
    item.appendChild(amountSpan);

    const percentSpan = document.createElement("span");
    percentSpan.className = "distribution-legend__percent";
    percentSpan.textContent = formatPercent(ratio);
    item.appendChild(percentSpan);

    distributionList.appendChild(item);

    if (value > 0) {
      labelParts.push(`${labelText} ${percentSpan.textContent}`);
    }
  });

  const totalLabel = document.createElementNS(SVG_NS, "text");
  totalLabel.classList.add("distribution-chart__center-label");
  totalLabel.setAttribute("x", center);
  totalLabel.setAttribute("y", center - 6);
  totalLabel.setAttribute("text-anchor", "middle");
  totalLabel.textContent = t("calculator.results_heading");
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

function resolveSummaryLabel(key, labels = {}) {
  if (labels && typeof labels[key] === "string" && labels[key].trim()) {
    return labels[key];
  }
  const translationKey = `summary.${key}`;
  const translated = t(translationKey);
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
    { key: "net_income", formatter: formatCurrency, className: "primary" },
    { key: "tax_total", formatter: formatCurrency, className: "accent" },
    { key: "withholding_tax", formatter: formatCurrency },
    { key: "balance_due", formatter: formatCurrency, className: "accent" },
    { key: "deductions_applied", formatter: formatCurrency },
    { key: "deductions_entered", formatter: formatCurrency },
    { key: "net_monthly_income", formatter: formatCurrency },
    { key: "average_monthly_tax", formatter: formatCurrency },
    { key: "income_total", formatter: formatCurrency },
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
    "monthly_gross_income",
    "payments_per_year",
    "gross_income_per_payment",
    "deductible_contributions",
    "category_contributions",
    "additional_contributions",
    "auxiliary_contributions",
    "lump_sum_contributions",
    "employee_contributions",
    "employee_contributions_manual",
    "employee_contributions_per_payment",
    "employer_contributions",
    "employer_contributions_per_payment",
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
    monthly_gross_income: detailLabels.monthly_gross_income || "Monthly gross income",
    payments_per_year: detailLabels.payments_per_year || "Payments per year",
    gross_income_per_payment:
      detailLabels.gross_income_per_payment || "Gross per payment",
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
    employee_contributions_per_payment:
      detailLabels.employee_contributions_per_payment ||
      "Employee contributions per payment",
    employer_contributions:
      detailLabels.employer_contributions || "Employer contributions",
    employer_contributions_per_payment:
      detailLabels.employer_contributions_per_payment ||
      "Employer contributions per payment",
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
    if (key === "payments_per_year") {
      dd.textContent = value;
    } else {
      dd.textContent = formatCurrency(value);
    }
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

  const filename = buildDownloadFilename("json");
  const blob = new Blob([JSON.stringify(lastCalculation, null, 2)], {
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

function downloadCsvSummary() {
  if (!lastCalculation) {
    return;
  }

  const summary = lastCalculation.summary || {};
  const summaryLabels = summary.labels || {};
  const details = Array.isArray(lastCalculation.details) ? lastCalculation.details : [];
  const detailLabels = getMessagesSection(currentLocale, "detailFields");

  const lines = [["Section", "Label", "Value"]];

  const summaryFields = [
    { key: "net_income", formatter: formatCurrency },
    { key: "tax_total", formatter: formatCurrency },
    { key: "withholding_tax", formatter: formatCurrency },
    { key: "balance_due", formatter: formatCurrency },
    { key: "deductions_applied", formatter: formatCurrency },
    { key: "deductions_entered", formatter: formatCurrency },
    { key: "net_monthly_income", formatter: formatCurrency },
    { key: "average_monthly_tax", formatter: formatCurrency },
    { key: "income_total", formatter: formatCurrency },
    { key: "effective_tax_rate", formatter: formatPercent },
  ];

  summaryFields.forEach(({ key, formatter }) => {
    if (summary[key] !== undefined && summary[key] !== null) {
      const label = resolveSummaryLabel(key, summaryLabels);
      lines.push(["Summary", label, formatter(summary[key])]);
    }
  });

  const detailFieldOrder = [
    "gross_income",
    "monthly_gross_income",
    "payments_per_year",
    "gross_income_per_payment",
    "deductible_contributions",
    "category_contributions",
    "additional_contributions",
    "auxiliary_contributions",
    "employee_contributions",
    "employee_contributions_per_payment",
    "employer_contributions",
    "employer_contributions_per_payment",
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

  details.forEach((detail) => {
    const sectionLabel = detail.label || detail.category || "Detail";
    detailFieldOrder.forEach((field) => {
      if (detail[field] === undefined || detail[field] === null) {
        return;
      }

      const labelKey = field === "trade_fee" && detail.trade_fee_label
        ? detail.trade_fee_label
        : detailLabels[field] || field;

      let value;
      if (field === "payments_per_year") {
        value = detail[field];
      } else {
        value = formatCurrency(detail[field]);
      }

      lines.push(["Detail", `${sectionLabel} – ${labelKey}`, value]);
    });

    if (detail.items && Array.isArray(detail.items)) {
      detail.items.forEach((item) => {
        const formatted = `${formatCurrency(item.amount)} → ${formatCurrency(
          item.tax,
        )} (${formatPercent(item.rate)})`;
        lines.push(["Detail", `${sectionLabel} – ${item.label}`, formatted]);
      });
    }
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
  window.print();
}

function initialiseCalculator() {
  if (!calculatorForm || !yearSelect) {
    return;
  }

  pendingCalculatorState = loadStoredCalculatorState();
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
    const value = typeof target?.value === "string" ? target.value : "gross";
    updatePensionMode(value);
    updatePartialYearWarningState();
  });
  pensionNetInputModeSelect?.addEventListener("change", (event) => {
    const target = event.target;
    const value = typeof target?.value === "string" ? target.value : "annual";
    updatePensionNetInputMode(value);
    updatePartialYearWarningState();
  });
  pensionIncomeInput?.addEventListener("input", updatePartialYearWarningState);
  pensionNetIncomeInput?.addEventListener("input", updatePartialYearWarningState);
  pensionNetMonthlyIncomeInput?.addEventListener(
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

  downloadButton?.addEventListener("click", downloadJsonSummary);
  downloadCsvButton?.addEventListener("click", downloadCsvSummary);
  printButton?.addEventListener("click", printSummary);
  clearButton?.addEventListener("click", clearCalculatorForm);

  attachValidationHandlers();
  updatePartialYearWarningState();

  loadYearOptions().then(async () => {
    applyPendingCalculatorState();
    await refreshInvestmentCategories();
    applyPendingCalculatorState();
    await refreshDeductionHints();
    applyPendingCalculatorState();
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
