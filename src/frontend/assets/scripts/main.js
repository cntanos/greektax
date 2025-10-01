/**
 * Front-end logic for the GreekTax prototype calculator.
 *
 * The script bootstraps localisation-aware metadata retrieval, provides client
 * validation for numeric fields, and renders interactive calculation results
 * returned by the Flask back-end.
 */

const API_BASE = "/api/v1";
const CALCULATIONS_ENDPOINT = `${API_BASE}/calculations`;
const CONFIG_YEARS_ENDPOINT = `${API_BASE}/config/years`;
const CONFIG_INVESTMENT_ENDPOINT = (year, locale) =>
  `${API_BASE}/config/${year}/investment-categories?locale=${encodeURIComponent(
    locale,
  )}`;
const CONFIG_DEDUCTIONS_ENDPOINT = (year, locale) =>
  `${API_BASE}/config/${year}/deductions?locale=${encodeURIComponent(locale)}`;
const STORAGE_KEY = "greektax.locale";

const UI_MESSAGES = {
  en: {
    ui: {
      tagline: "Unofficial tax estimation toolkit for Greece",
      overview_heading: "Overview",
      overview_description:
        "Estimate annual income taxes for Greece across employment, freelance, rental, and investment categories. Select a tax year, choose your language, and provide the income figures relevant to your situation to receive a bilingual breakdown of obligations.",
      disclaimer:
        "Disclaimer: This tool is unofficial and provided as-is without data storage. Please consult a professional accountant for formal filings.",
    },
    preview: {
      heading: "Preview localisation",
      description:
        "Choose your preferred language and request a sample calculation to see the backend translations in action. The preview uses demo data only.",
      locale_label: "Language",
      button: "Preview calculation",
      idle: "No preview requested yet.",
      requesting: "Requesting preview from the API…",
      success: "Preview updated using backend localisation.",
      error: "Unable to fetch preview. Is the backend running?",
    },
    status: {
      loading_years: "Loading tax years…",
      ready: "Configuration loaded. Enter your details to calculate.",
      year_error: "Unable to load tax year configuration metadata.",
      select_year: "Please select a tax year before calculating.",
      calculating: "Calculating tax breakdown…",
      calculation_complete: "Calculation complete.",
      validation_errors: "Please fix the highlighted fields and try again.",
      calculation_failed: "Unable to process calculation.",
    },
    errors: {
      invalid_number: "Please enter a valid number for {{field}}.",
      negative_number: "{{field}} cannot be negative.",
      min_number: "{{field}} must be at least {{min}}.",
      max_number: "{{field}} must be at most {{max}}.",
      non_integer: "{{field}} must be a whole number.",
    },
    calculator: {
      heading: "Tax calculator",
      results_heading: "Results",
      legends: {
        year_household: "Year and household",
        employment_pension: "Employment & pension income",
        freelance: "Freelance income",
        rental: "Rental income",
        investment: "Investment income",
        obligations: "Additional obligations",
      },
    },
    forms: {
      no_investment_categories: "No investment categories configured for this year.",
    },
    detailFields: {
      gross_income: "Gross income",
      deductible_contributions: "Mandatory contributions",
      deductible_expenses: "Deductible expenses",
      taxable_income: "Taxable income",
      tax_before_credits: "Tax before credits",
      credits: "Credits",
      tax: "Tax",
      trade_fee: "Business activity fee",
      total_tax: "Total tax",
      net_income: "Net impact",
      monthly_gross_income: "Monthly gross income",
      payments_per_year: "Payments per year",
      gross_income_per_payment: "Gross per payment",
      net_income_per_payment: "Net per payment",
      breakdown: "Breakdown",
    },
    fields: {
      "year-select": "Tax year",
      "children-input": "Dependent children",
      "employment-income": "Employment gross income (€)",
      "employment-monthly-income": "Monthly gross income (€)",
      "employment-payments": "Salary payments per year",
      "pension-income": "Pension gross income (€)",
      "freelance-revenue": "Freelance gross revenue (€)",
      "freelance-expenses": "Freelance deductible expenses (€)",
      "freelance-contributions": "Mandatory social contributions (€)",
      "trade-fee-toggle": "Include business activity fee",
      "rental-income": "Rental gross income (€)",
      "rental-expenses": "Rental deductible expenses (€)",
      "vat-due": "VAT due (€)",
      "enfia-due": "ENFIA amount (€)",
      "luxury-due": "Luxury living tax (€)",
    },
    hints: {
      "employment-payments":
        "Most salaried roles use 14 payments (12 monthly plus bonuses). Adjust if your contract pays a different number of times per year.",
    },
    actions: {
      calculate: "Calculate taxes",
      download: "Download summary (JSON)",
      download_csv: "Download summary (CSV)",
      print: "Print summary",
    },
  },
  el: {
    ui: {
      tagline: "Μη επίσημο εργαλείο εκτίμησης φόρων για την Ελλάδα",
      overview_heading: "Επισκόπηση",
      overview_description:
        "Υπολογίστε ετήσιες φορολογικές υποχρεώσεις στην Ελλάδα για μισθωτούς, ελεύθερους επαγγελματίες, ενοίκια και επενδύσεις. Επιλέξτε φορολογικό έτος, γλώσσα και εισάγετε τα ποσά για να λάβετε δίγλωσση ανάλυση.",
      disclaimer:
        "Αποποίηση ευθύνης: Το εργαλείο είναι ανεπίσημο και παρέχεται ως έχει χωρίς αποθήκευση δεδομένων. Συμβουλευτείτε λογιστή για επίσημες δηλώσεις.",
    },
    preview: {
      heading: "Προεπισκόπηση εντοπισμού",
      description:
        "Επιλέξτε γλώσσα και ζητήστε δείγμα υπολογισμού για να δείτε τις μεταφράσεις του διακομιστή. Η προεπισκόπηση χρησιμοποιεί μόνο δοκιμαστικά δεδομένα.",
      locale_label: "Γλώσσα",
      button: "Προεπισκόπηση υπολογισμού",
      idle: "Δεν έχει ζητηθεί προεπισκόπηση ακόμη.",
      requesting: "Αίτημα προεπισκόπησης προς το API…",
      success: "Η προεπισκόπηση ενημερώθηκε με τις μεταφράσεις του διακομιστή.",
      error: "Δεν ήταν δυνατή η λήψη της προεπισκόπησης. Εκτελείται ο διακομιστής;",
    },
    status: {
      loading_years: "Φόρτωση διαθέσιμων φορολογικών ετών…",
      ready: "Η διαμόρφωση ολοκληρώθηκε. Συμπληρώστε τα στοιχεία σας για υπολογισμό.",
      year_error: "Αδυναμία φόρτωσης των δεδομένων φορολογικού έτους.",
      select_year: "Επιλέξτε φορολογικό έτος πριν από τον υπολογισμό.",
      calculating: "Υπολογισμός ανάλυσης φόρου…",
      calculation_complete: "Ο υπολογισμός ολοκληρώθηκε.",
      validation_errors: "Διορθώστε τα επισημασμένα πεδία και προσπαθήστε ξανά.",
      calculation_failed: "Δεν ήταν δυνατή η επεξεργασία του υπολογισμού.",
    },
    errors: {
      invalid_number: "Εισαγάγετε έγκυρο αριθμό για {{field}}.",
      negative_number: "{{field}} δεν μπορεί να είναι αρνητικό.",
      min_number: "{{field}} πρέπει να είναι τουλάχιστον {{min}}.",
      max_number: "{{field}} πρέπει να είναι το πολύ {{max}}.",
      non_integer: "{{field}} πρέπει να είναι ακέραιος αριθμός.",
    },
    calculator: {
      heading: "Φορολογικός υπολογιστής",
      results_heading: "Αποτελέσματα",
      legends: {
        year_household: "Έτος και νοικοκυριό",
        employment_pension: "Εισόδημα μισθωτών & συντάξεων",
        freelance: "Εισόδημα ελεύθερου επαγγελματία",
        rental: "Εισόδημα από ενοίκια",
        investment: "Επενδυτικά εισοδήματα",
        obligations: "Πρόσθετες υποχρεώσεις",
      },
    },
    forms: {
      no_investment_categories:
        "Δεν έχουν οριστεί επενδυτικές κατηγορίες για αυτό το έτος.",
    },
    detailFields: {
      gross_income: "Ακαθάριστο εισόδημα",
      deductible_contributions: "Υποχρεωτικές εισφορές",
      deductible_expenses: "Εκπιπτόμενες δαπάνες",
      taxable_income: "Φορολογητέο εισόδημα",
      tax_before_credits: "Φόρος πριν τις εκπτώσεις",
      credits: "Εκπτώσεις",
      tax: "Φόρος",
      trade_fee: "Τέλος επιτηδεύματος",
      total_tax: "Συνολικός φόρος",
      net_income: "Καθαρή επίδραση",
      monthly_gross_income: "Μηνιαίο ακαθάριστο εισόδημα",
      payments_per_year: "Καταβολές ανά έτος",
      gross_income_per_payment: "Ακαθάριστο ανά καταβολή",
      net_income_per_payment: "Καθαρό ανά καταβολή",
      breakdown: "Ανάλυση",
    },
    fields: {
      "year-select": "Φορολογικό έτος",
      "children-input": "Εξαρτώμενα τέκνα",
      "employment-income": "Ακαθάριστο εισόδημα μισθωτών (€)",
      "employment-monthly-income": "Μηνιαίο ακαθάριστο εισόδημα (€)",
      "employment-payments": "Μισθολογικές καταβολές ανά έτος",
      "pension-income": "Ακαθάριστο εισόδημα συντάξεων (€)",
      "freelance-revenue": "Ακαθάριστα έσοδα ελευθέρου επαγγελματία (€)",
      "freelance-expenses": "Εκπιπτόμενες δαπάνες ελευθέρου επαγγελματία (€)",
      "freelance-contributions": "Υποχρεωτικές εισφορές (€)",
      "trade-fee-toggle": "Συμπερίληψη τέλους επιτηδεύματος",
      "rental-income": "Ακαθάριστα έσοδα ενοικίων (€)",
      "rental-expenses": "Εκπιπτόμενες δαπάνες ενοικίων (€)",
      "vat-due": "Οφειλόμενος ΦΠΑ (€)",
      "enfia-due": "Ποσό ΕΝΦΙΑ (€)",
      "luxury-due": "Φόρος πολυτελούς διαβίωσης (€)",
    },
    hints: {
      "employment-payments":
        "Συνήθως καταβάλλονται 14 μισθοί (12 μηνιαίοι και 2 δώρα). Προσαρμόστε τον αριθμό αν η σύμβασή σας προβλέπει διαφορετικές καταβολές ανά έτος.",
    },
    actions: {
      calculate: "Υπολογισμός φόρων",
      download: "Λήψη σύνοψης (JSON)",
      download_csv: "Λήψη σύνοψης (CSV)",
      print: "Εκτύπωση σύνοψης",
    },
  },
};

let currentLocale = "en";
let currentInvestmentCategories = [];
let currentDeductionHints = [];
let dynamicFieldLabels = {};
let deductionValidationByInput = {};
let lastCalculation = null;

const localeSelect = document.getElementById("locale-select");
const previewButton = document.getElementById("preview-button");
const previewStatus = document.getElementById("preview-status");
const previewJson = document.getElementById("preview-json");

const yearSelect = document.getElementById("year-select");
const childrenInput = document.getElementById("children-input");
const employmentIncomeInput = document.getElementById("employment-income");
const employmentMonthlyIncomeInput = document.getElementById(
  "employment-monthly-income",
);
const employmentPaymentsInput = document.getElementById("employment-payments");
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
const luxuryInput = document.getElementById("luxury-due");
const calculatorForm = document.getElementById("calculator-form");
const calculatorStatus = document.getElementById("calculator-status");
const resultsSection = document.getElementById("calculation-results");
const summaryGrid = document.getElementById("summary-grid");
const detailsList = document.getElementById("details-list");
const downloadButton = document.getElementById("download-button");
const downloadCsvButton = document.getElementById("download-csv-button");
const printButton = document.getElementById("print-button");

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

function lookupMessage(locale, keyParts) {
  let cursor = UI_MESSAGES[locale];
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
  const fallback = locale === "en" ? undefined : lookupMessage("en", keyParts);
  const template =
    typeof primary === "string"
      ? primary
      : typeof fallback === "string"
      ? fallback
      : key;
  return formatTemplate(template, replacements);
}

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

function resolveLocaleTag(locale) {
  if (locale === "el") {
    return "el-GR";
  }
  if (locale === "en") {
    return "en-GB";
  }
  return locale || "en-GB";
}

function applyLocale(locale) {
  currentLocale = locale;
  persistLocale(locale);
  document.documentElement.lang = locale === "el" ? "el" : "en";
  localiseStaticText();
  if (localeSelect) {
    localeSelect.value = locale;
  }
  if (previewStatus && previewStatus.dataset.initialised) {
    previewStatus.textContent = t("preview.idle");
  }
  refreshInvestmentCategories();
  refreshDeductionHints();
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

function updatePreviewIdleMessage() {
  if (previewStatus) {
    previewStatus.textContent = t("preview.idle");
    previewStatus.dataset.initialised = "true";
  }
}

function setPreviewStatus(message, { isError = false, showJson = false } = {}) {
  if (previewStatus) {
    previewStatus.textContent = message;
    previewStatus.setAttribute("data-status", isError ? "error" : "info");
  }
  if (previewJson) {
    previewJson.hidden = !showJson;
  }
}

async function requestPreview(locale) {
  const payload = { ...demoPayload, locale };
  setPreviewStatus(t("preview.requesting"));

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
    setPreviewStatus(t("preview.success"), { showJson: true });
    if (previewJson) {
      previewJson.textContent = JSON.stringify(result, null, 2);
    }
  } catch (error) {
    console.error("Failed to load preview", error);
    setPreviewStatus(t("preview.error"), { isError: true });
  }
}

function setCalculatorStatus(message, { isError = false } = {}) {
  if (!calculatorStatus) {
    return;
  }
  calculatorStatus.textContent = message;
  calculatorStatus.setAttribute("data-status", isError ? "error" : "info");
}

function formatNumber(value) {
  const formatter = new Intl.NumberFormat(resolveLocaleTag(currentLocale), {
    style: "decimal",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  return formatter.format(value || 0);
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

    years.forEach((entry) => {
      const option = document.createElement("option");
      option.value = String(entry.year);
      option.textContent = `${entry.year}`;
      yearSelect.appendChild(option);
    });

    if (payload.default_year) {
      yearSelect.value = String(payload.default_year);
    }

    setCalculatorStatus(t("status.ready"));
  } catch (error) {
    console.error("Failed to load year metadata", error);
    setCalculatorStatus(t("status.year_error"), { isError: true });
  }
}

function renderInvestmentFields(categories) {
  if (!investmentFieldsContainer) {
    return;
  }

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

  const messages = UI_MESSAGES[currentLocale]?.fields || {};
  if (messages[input.id]) {
    return messages[input.id];
  }

  const fallbackMessages = UI_MESSAGES.en.fields || {};
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
  if (!input) {
    return true;
  }

  clearFieldError(input);

  const rawValue = (input.value ?? "").trim();
  if (rawValue === "") {
    input.value = "0";
    return true;
  }

  const normalised = rawValue.replace(",", ".");
  const number = Number.parseFloat(normalised);
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

  input.value = String(number);
  return true;
}

function validateForm() {
  if (!calculatorForm) {
    return true;
  }

  const inputs = calculatorForm.querySelectorAll('input[type="number"]');
  let isValid = true;
  inputs.forEach((input) => {
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

  const inputs = calculatorForm.querySelectorAll('input[type="number"]');
  inputs.forEach((input) => {
    input.addEventListener("input", () => {
      clearFieldError(input);
    });
    input.addEventListener("blur", () => {
      validateNumberInput(input);
    });
  });
}

function readNumber(input) {
  if (!input) {
    return 0;
  }
  const normalised = (input.value ?? "0").toString().replace(",", ".");
  const value = Number.parseFloat(normalised);
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

  if (employmentIncomeInput || employmentMonthlyIncomeInput) {
    const employmentPayload = {};
    const grossIncome = readNumber(employmentIncomeInput);
    if (grossIncome > 0) {
      employmentPayload.gross_income = grossIncome;
    }

    const monthlyIncome = readNumber(employmentMonthlyIncomeInput);
    if (monthlyIncome > 0) {
      employmentPayload.monthly_income = monthlyIncome;
    }

    const paymentsValue = Number.parseInt(employmentPaymentsInput?.value ?? "", 10);
    if (Number.isFinite(paymentsValue) && paymentsValue > 0) {
      employmentPayload.payments_per_year = paymentsValue;
    }

    if (Object.keys(employmentPayload).length > 0) {
      payload.employment = employmentPayload;
    }
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
    luxury: readNumber(luxuryInput),
  };

  return payload;
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

    const dt = document.createElement("dt");
    dt.textContent = labels[key] || key;
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

  const detailLabels =
    UI_MESSAGES[currentLocale]?.detailFields || UI_MESSAGES.en.detailFields || {};

  const dl = document.createElement("dl");
  const fieldOrder = [
    "gross_income",
    "monthly_gross_income",
    "payments_per_year",
    "deductible_contributions",
    "deductible_expenses",
    "taxable_income",
    "tax_before_credits",
    "credits",
    "tax",
    "trade_fee",
    "total_tax",
    "net_income",
    "net_income_per_payment",
  ];
  const labels = {
    gross_income: detailLabels.gross_income || "Gross income",
    monthly_gross_income: detailLabels.monthly_gross_income || "Monthly gross income",
    payments_per_year: detailLabels.payments_per_year || "Payments per year",
    deductible_contributions:
      detailLabels.deductible_contributions || "Mandatory contributions",
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
    const list = document.createElement("ul");
    detail.items.forEach((item) => {
      const entry = document.createElement("li");
      entry.textContent = `${item.label}: ${formatCurrency(item.amount)} → ${formatCurrency(
        item.tax,
      )} (${formatPercent(item.rate)})`;
      list.appendChild(entry);
    });
    const dt = document.createElement("dt");
    dt.textContent = detailLabels.breakdown || "Breakdown";
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
  downloadCsvButton?.removeAttribute("disabled");
  printButton?.removeAttribute("disabled");

  renderSummary(result.summary || {});
  renderDetails(result.details || []);

  if (resultsSection) {
    resultsSection.hidden = false;
  }
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
  downloadCsvButton?.setAttribute("disabled", "true");
  printButton?.setAttribute("disabled", "true");
  lastCalculation = null;
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
  const detailLabels =
    UI_MESSAGES[currentLocale]?.detailFields || UI_MESSAGES.en.detailFields || {};

  const lines = [["Section", "Label", "Value"]];

  const summaryFields = [
    { key: "net_income", formatter: formatCurrency },
    { key: "tax_total", formatter: formatCurrency },
    { key: "net_monthly_income", formatter: formatCurrency },
    { key: "average_monthly_tax", formatter: formatCurrency },
    { key: "income_total", formatter: formatCurrency },
    { key: "effective_tax_rate", formatter: formatPercent },
  ];

  summaryFields.forEach(({ key, formatter }) => {
    if (summary[key] !== undefined && summary[key] !== null) {
      const label = summaryLabels[key] || key;
      lines.push(["Summary", label, formatter(summary[key])]);
    }
  });

  const detailFieldOrder = [
    "gross_income",
    "monthly_gross_income",
    "payments_per_year",
    "gross_income_per_payment",
    "deductible_contributions",
    "deductible_expenses",
    "taxable_income",
    "tax_before_credits",
    "credits",
    "tax",
    "trade_fee",
    "total_tax",
    "net_income",
    "net_income_per_payment",
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

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function printSummary() {
  if (!lastCalculation) {
    return;
  }
  window.print();
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

function initialiseCalculator() {
  if (!calculatorForm || !yearSelect) {
    return;
  }

  calculatorForm.addEventListener("submit", submitCalculation);
  yearSelect.addEventListener("change", () => {
    refreshInvestmentCategories();
    refreshDeductionHints();
  });

  downloadButton?.addEventListener("click", downloadJsonSummary);
  downloadCsvButton?.addEventListener("click", downloadCsvSummary);
  printButton?.addEventListener("click", printSummary);

  attachValidationHandlers();

  loadYearOptions().then(() => {
    refreshInvestmentCategories();
    refreshDeductionHints();
  });
}

function bootstrap() {
  const initialLocale = resolveStoredLocale();
  updatePreviewIdleMessage();
  applyLocale(initialLocale);

  initialisePreviewControls();
  initialiseCalculator();

  console.info("GreekTax interface initialised");
}

document.addEventListener("DOMContentLoaded", bootstrap);
