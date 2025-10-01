/* Entry point for the GreekTax front-end.
 *
 * TODO: Implement SPA-style interactions or progressive enhancement to connect
 * to the backend API for tax computations. Initial features will include:
 * - Fetching year configuration metadata
 * - Managing bilingual labels and locale switching
 * - Handling form inputs and displaying calculation results
 */

const API_BASE = "/api/v1";
const CALCULATIONS_ENDPOINT = `${API_BASE}/calculations`;
const CONFIG_YEARS_ENDPOINT = `${API_BASE}/config/years`;
const CONFIG_INVESTMENT_ENDPOINT = (year, locale) =>
  `${API_BASE}/config/${year}/investment-categories?locale=${encodeURIComponent(
    locale,
  )}`;
const STORAGE_KEY = "greektax.locale";

const localeSelect = document.getElementById("locale-select");
const previewButton = document.getElementById("preview-button");
const previewStatus = document.getElementById("preview-status");
const previewJson = document.getElementById("preview-json");

const yearSelect = document.getElementById("year-select");
const childrenInput = document.getElementById("children-input");
const employmentIncomeInput = document.getElementById("employment-income");
const pensionIncomeInput = document.getElementById("pension-income");
const freelanceRevenueInput = document.getElementById("freelance-revenue");
const freelanceExpensesInput = document.getElementById("freelance-expenses");
const freelanceContributionsInput = document.getElementById(
  "freelance-contributions",
);
const tradeFeeToggle = document.getElementById("trade-fee-toggle");
const rentalIncomeInput = document.getElementById("rental-income");
const rentalExpensesInput = document.getElementById("rental-expenses");
const investmentFieldsContainer = document.getElementById("investment-fields");
const vatInput = document.getElementById("vat-due");
const enfiaInput = document.getElementById("enfia-due");
const calculatorForm = document.getElementById("calculator-form");
const calculatorStatus = document.getElementById("calculator-status");
const resultsSection = document.getElementById("calculation-results");
const summaryGrid = document.getElementById("summary-grid");
const detailsList = document.getElementById("details-list");
const downloadButton = document.getElementById("download-button");
const printButton = document.getElementById("print-button");

let currentLocale = "en";
let currentInvestmentCategories = [];
let lastCalculation = null;

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
  const htmlLocale = locale === "el" ? "el" : "en";
  document.documentElement.lang = htmlLocale;
  currentLocale = locale;
  persistLocale(locale);
  refreshInvestmentCategories();
}

function setPreviewStatus(message, { isError = false, showJson = false } = {}) {
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
  setPreviewStatus("Requesting preview from the API…");

  try {
    const response = await fetch(CALCULATIONS_ENDPOINT, {
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
    setPreviewStatus("Preview updated using backend localisation.", {
      showJson: true,
    });
    if (previewJson) {
      previewJson.textContent = JSON.stringify(result, null, 2);
    }
  } catch (error) {
    console.error("Failed to load preview", error);
    setPreviewStatus("Unable to fetch preview. Is the backend running?", {
      isError: true,
    });
  }
}

function bootstrap() {
  const initialLocale = resolveStoredLocale();
  applyLocale(initialLocale);

  initialisePreviewControls();
  initialiseCalculator();

  console.info("GreekTax interface initialised");
}

function initialisePreviewControls() {
  if (!localeSelect || !previewButton || !previewStatus || !previewJson) {
    console.warn("Preview controls missing from DOM");
    return;
  }

  localeSelect.addEventListener("change", (event) => {
    const target = event.target;
    const locale = typeof target?.value === "string" ? target.value : "en";
    applyLocale(locale);
  });

  previewButton.addEventListener("click", () => {
    const locale = localeSelect.value || "en";
    requestPreview(locale);
  });
}

function setCalculatorStatus(message, { isError = false } = {}) {
  if (!calculatorStatus) {
    return;
  }

  calculatorStatus.textContent = message;
  calculatorStatus.setAttribute("data-status", isError ? "error" : "info");
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

function formatCurrency(value) {
  const formatter = new Intl.NumberFormat(resolveLocaleTag(currentLocale), {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return formatter.format(value || 0);
}

function formatPercent(value) {
  const formatter = new Intl.NumberFormat(resolveLocaleTag(currentLocale), {
    style: "percent",
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  });
  return formatter.format(value);
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
  downloadButton?.setAttribute("disabled", "true");
  printButton?.setAttribute("disabled", "true");
  lastCalculation = null;
}

async function loadYearOptions() {
  if (!yearSelect) {
    return;
  }

  setCalculatorStatus("Loading tax years…");
  try {
    const response = await fetch(CONFIG_YEARS_ENDPOINT);
    if (!response.ok) {
      throw new Error(`Unable to load years (${response.status})`);
    }

    const payload = await response.json();
    const years = Array.isArray(payload.years) ? payload.years : [];
    yearSelect.innerHTML = "";

    years.forEach((entry) => {
      const option = document.createElement("option");
      option.value = String(entry.year);
      option.textContent = `${entry.year}`;
      yearSelect.appendChild(option);
    });

    if (payload.default_year) {
      yearSelect.value = String(payload.default_year);
    }

    setCalculatorStatus("Configuration loaded. Enter your details to calculate.");
  } catch (error) {
    console.error("Failed to load year metadata", error);
    setCalculatorStatus("Unable to load tax year configuration metadata.", {
      isError: true,
    });
  }
}

function renderInvestmentFields(categories) {
  if (!investmentFieldsContainer) {
    return;
  }

  investmentFieldsContainer.innerHTML = "";
  if (!categories.length) {
    const message = document.createElement("p");
    message.textContent = "No investment categories configured for this year.";
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

function readNumber(input) {
  if (!input) {
    return 0;
  }
  const value = Number.parseFloat(input.value ?? "0");
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

  if (employmentIncomeInput) {
    payload.employment = {
      gross_income: readNumber(employmentIncomeInput),
    };
  }

  if (pensionIncomeInput) {
    payload.pension = {
      gross_income: readNumber(pensionIncomeInput),
    };
  }

  if (freelanceRevenueInput || freelanceContributionsInput) {
    payload.freelance = {
      gross_revenue: readNumber(freelanceRevenueInput),
      deductible_expenses: readNumber(freelanceExpensesInput),
      mandatory_contributions: readNumber(freelanceContributionsInput),
      include_trade_fee: Boolean(tradeFeeToggle?.checked),
    };
  }

  if (rentalIncomeInput || rentalExpensesInput) {
    payload.rental = {
      gross_income: readNumber(rentalIncomeInput),
      deductible_expenses: readNumber(rentalExpensesInput),
    };
  }

  if (currentInvestmentCategories.length) {
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

  payload.obligations = {
    vat: readNumber(vatInput),
    enfia: readNumber(enfiaInput),
  };

  return payload;
}

function renderSummary(summary) {
  if (!summaryGrid) {
    return;
  }

  summaryGrid.innerHTML = "";
  const labels = summary.labels || {};
  ["income_total", "tax_total", "net_income"].forEach((key) => {
    if (!(key in summary)) {
      return;
    }
    const wrapper = document.createElement("dl");
    wrapper.className = "summary-item";

    const dt = document.createElement("dt");
    dt.textContent = labels[key] || key;

    const dd = document.createElement("dd");
    dd.textContent = formatCurrency(summary[key]);

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

  const dl = document.createElement("dl");
  const fieldOrder = [
    "gross_income",
    "deductible_contributions",
    "deductible_expenses",
    "taxable_income",
    "tax_before_credits",
    "credits",
    "tax",
    "trade_fee",
    "total_tax",
    "net_income",
  ];
  const labels = {
    gross_income: "Gross income",
    deductible_contributions: "Mandatory contributions",
    deductible_expenses: "Deductible expenses",
    taxable_income: "Taxable income",
    tax_before_credits: "Tax before credits",
    credits: "Credits",
    tax: "Tax",
    trade_fee: detail.trade_fee_label || "Business activity fee",
    total_tax: "Total tax",
    net_income: "Net impact",
  };

  fieldOrder.forEach((key) => {
    if (!(key in detail)) {
      return;
    }

    const value = detail[key];
    if (value === null || value === undefined) {
      return;
    }

    const dt = document.createElement("dt");
    dt.textContent = labels[key];

    const dd = document.createElement("dd");
    dd.textContent = formatCurrency(value);

    dl.appendChild(dt);
    dl.appendChild(dd);
  });

  if (detail.items && Array.isArray(detail.items) && detail.items.length) {
    const list = document.createElement("ul");
    detail.items.forEach((item) => {
      const entry = document.createElement("li");
      entry.textContent = `${item.label}: ${formatCurrency(item.amount)} → ${formatCurrency(
        item.tax,
      )} (${formatPercent(item.rate)})`;
      list.appendChild(entry);
    });
    const dt = document.createElement("dt");
    dt.textContent = "Breakdown";
    const dd = document.createElement("dd");
    dd.appendChild(list);
    dl.appendChild(dt);
    dl.appendChild(dd);
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

  lastCalculation = result;
  downloadButton?.removeAttribute("disabled");
  printButton?.removeAttribute("disabled");

  renderSummary(result.summary || {});
  renderDetails(result.details || []);

  if (resultsSection) {
    resultsSection.hidden = false;
  }
}

async function submitCalculation(event) {
  event.preventDefault();
  resetResults();

  if (!calculatorForm) {
    return;
  }

  const payload = buildCalculationPayload();
  if (!payload.year) {
    setCalculatorStatus("Please select a tax year before calculating.", {
      isError: true,
    });
    return;
  }

  setCalculatorStatus("Calculating tax breakdown…");

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
    setCalculatorStatus("Calculation complete.");
  } catch (error) {
    console.error("Calculation request failed", error);
    setCalculatorStatus(
      error instanceof Error ? error.message : "Unable to process calculation.",
      { isError: true },
    );
  }
}

function downloadSummary() {
  if (!lastCalculation) {
    return;
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `greektax-${lastCalculation.meta?.year ?? "summary"}-${timestamp}.json`;
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

  calculatorForm.addEventListener("submit", submitCalculation);
  yearSelect.addEventListener("change", () => {
    refreshInvestmentCategories();
  });

  downloadButton?.addEventListener("click", downloadSummary);
  printButton?.addEventListener("click", printSummary);

  loadYearOptions().then(() => {
    refreshInvestmentCategories();
  });
}

document.addEventListener("DOMContentLoaded", bootstrap);
