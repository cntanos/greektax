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
const SUMMARIES_ENDPOINT = `${API_BASE}/summaries`;
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
      persisting_share: "Preparing shareable summary…",
      share_ready: "Share link ready.",
      share_failed: "Unable to prepare share link.",
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
      share_title: "GreekTax summary",
      share_heading: "Tax summary",
      summary_heading: "Overview",
      detail_heading: "Detailed breakdown",
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
      breakdown: "Breakdown",
    },
    fields: {
      "year-select": "Tax year",
      "children-input": "Dependent children",
      "employment-income": "Employment gross income (€)",
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
    actions: {
      calculate: "Calculate taxes",
      download: "Download summary (JSON)",
      download_csv: "Download summary (CSV)",
      download_pdf: "Download summary (PDF)",
      share: "Open shareable summary",
      print: "Print summary",
    },
    share: {
      open_failed: "Popup blocked. Please allow pop-ups to view the summary.",
      copy: "Copy link",
      copy_success: "Share link copied to clipboard.",
      copy_error: "Unable to copy link to clipboard.",
      link_label: "Shareable link",
      link_placeholder: "https://example.com/share/...",
      expiry_notice: "Share links remain available for 24 hours.",
      expires_at: "Link expires {{datetime}}.",
      expired: "Share link expired. Generate a new summary.",
      feedback_prompt: "Was the expiry message clear?",
      feedback_clear: "Yes, it was clear",
      feedback_unclear: "No, it needs work",
      feedback_notes_label: "Optional feedback",
      feedback_notes_placeholder: "Let us know how we can improve the expiry message.",
      feedback_submit: "Send feedback",
      feedback_sending: "Sending feedback…",
      feedback_submitted: "Feedback received — thank you!",
      feedback_error: "Unable to send feedback. Please try again.",
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
      persisting_share: "Προετοιμασία κοινόχρηστης σύνοψης…",
      share_ready: "Ο σύνδεσμος κοινοποίησης είναι έτοιμος.",
      share_failed: "Αδυναμία προετοιμασίας συνδέσμου.",
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
      share_title: "Σύνοψη GreekTax",
      share_heading: "Σύνοψη φόρων",
      summary_heading: "Επισκόπηση",
      detail_heading: "Αναλυτική παρουσίαση",
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
      breakdown: "Ανάλυση",
    },
    fields: {
      "year-select": "Φορολογικό έτος",
      "children-input": "Εξαρτώμενα τέκνα",
      "employment-income": "Ακαθάριστο εισόδημα μισθωτών (€)",
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
    actions: {
      calculate: "Υπολογισμός φόρων",
      download: "Λήψη σύνοψης (JSON)",
      download_csv: "Λήψη σύνοψης (CSV)",
      download_pdf: "Λήψη σύνοψης (PDF)",
      share: "Άνοιγμα κοινόχρηστης σύνοψης",
      print: "Εκτύπωση σύνοψης",
    },
    share: {
      open_failed:
        "Το αναδυόμενο παράθυρο μπλοκαρίστηκε. Επιτρέψτε τα αναδυόμενα για να δείτε τη σύνοψη.",
      copy: "Αντιγραφή συνδέσμου",
      copy_success: "Ο σύνδεσμος αντιγράφηκε στο πρόχειρο.",
      copy_error: "Αδυναμία αντιγραφής του συνδέσμου.",
      link_label: "Κοινόχρηστος σύνδεσμος",
      link_placeholder: "https://example.com/share/...",
      expiry_notice: "Οι σύνδεσμοι κοινοποίησης παραμένουν ενεργοί για 24 ώρες.",
      expires_at: "Ο σύνδεσμος λήγει {{datetime}}.",
      expired: "Ο σύνδεσμος έχει λήξει. Δημιουργήστε νέα σύνοψη.",
      feedback_prompt: "Ήταν σαφές το μήνυμα λήξης;",
      feedback_clear: "Ναι, ήταν σαφές",
      feedback_unclear: "Όχι, χρειάζεται βελτίωση",
      feedback_notes_label: "Προαιρετικά σχόλια",
      feedback_notes_placeholder: "Πείτε μας πώς μπορούμε να βελτιώσουμε το μήνυμα λήξης.",
      feedback_submit: "Αποστολή σχολίων",
      feedback_sending: "Αποστολή σχολίων…",
      feedback_submitted: "Ευχαριστούμε για τα σχόλιά σας!",
      feedback_error: "Δεν ήταν δυνατή η αποστολή των σχολίων.",
    },
  },
};

let currentLocale = "en";
let currentInvestmentCategories = [];
let currentDeductionHints = [];
let dynamicFieldLabels = {};
let deductionValidationByInput = {};
let lastCalculation = null;
let lastShareRecord = null;
let lastShareSignature = null;
let shareFeedbackSelection = null;

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
const luxuryInput = document.getElementById("luxury-due");
const calculatorForm = document.getElementById("calculator-form");
const calculatorStatus = document.getElementById("calculator-status");
const resultsSection = document.getElementById("calculation-results");
const summaryGrid = document.getElementById("summary-grid");
const detailsList = document.getElementById("details-list");
const downloadButton = document.getElementById("download-button");
const downloadCsvButton = document.getElementById("download-csv-button");
const downloadPdfButton = document.getElementById("download-pdf-button");
const shareButton = document.getElementById("share-button");
const printButton = document.getElementById("print-button");
const copyShareLinkButton = document.getElementById("copy-share-link-button");
const shareLinkInput = document.getElementById("share-link");
const shareExpiryElement = document.getElementById("share-expiry");
const shareFeedbackContainer = document.getElementById("share-feedback");
const shareFeedbackButtons = shareFeedbackContainer
  ? Array.from(shareFeedbackContainer.querySelectorAll("[data-feedback]"))
  : [];
const shareFeedbackNotes = document.getElementById("share-feedback-notes");
const shareFeedbackSubmit = document.getElementById("share-feedback-submit");
const shareFeedbackStatus = document.getElementById("share-feedback-status");

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
  if (lastShareRecord) {
    updateShareLink(lastShareRecord);
  } else {
    updateShareLink(null);
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

function formatDateTime(date) {
  const formatter = new Intl.DateTimeFormat(resolveLocaleTag(currentLocale), {
    dateStyle: "medium",
    timeStyle: "short",
  });
  return formatter.format(date);
}

function getShareExpiryDate(record) {
  if (!record || !record.meta || !record.meta.expires_at) {
    return null;
  }
  const expiryDate = new Date(record.meta.expires_at);
  if (Number.isNaN(expiryDate.getTime())) {
    return null;
  }
  return expiryDate;
}

function isShareRecordExpired(record) {
  const expiryDate = getShareExpiryDate(record);
  if (!expiryDate) {
    return false;
  }
  return expiryDate.getTime() <= Date.now();
}

function resetShareFeedback() {
  if (!shareFeedbackContainer) {
    return;
  }

  shareFeedbackContainer.dataset.shareId = "";
  shareFeedbackContainer.dataset.state = "";
  shareFeedbackContainer.setAttribute("hidden", "true");
  shareFeedbackSelection = null;
  shareFeedbackButtons.forEach((button) => {
    button.dataset.selected = "false";
    button.setAttribute("aria-pressed", "false");
    button.removeAttribute("disabled");
  });
  if (shareFeedbackSubmit) {
    shareFeedbackSubmit.setAttribute("disabled", "true");
  }
  if (shareFeedbackStatus) {
    shareFeedbackStatus.textContent = "";
    delete shareFeedbackStatus.dataset.status;
  }
  if (shareFeedbackNotes) {
    shareFeedbackNotes.value = "";
  }
}

function prepareShareFeedback(record) {
  if (!shareFeedbackContainer || !record?.id) {
    return;
  }

  shareFeedbackContainer.dataset.shareId = record.id;
  shareFeedbackContainer.dataset.state = "pending";
  shareFeedbackContainer.removeAttribute("hidden");
  shareFeedbackSelection = null;
  shareFeedbackButtons.forEach((button) => {
    button.dataset.selected = "false";
    button.setAttribute("aria-pressed", "false");
    button.removeAttribute("disabled");
  });
  if (shareFeedbackSubmit) {
    shareFeedbackSubmit.setAttribute("disabled", "true");
  }
  if (shareFeedbackStatus) {
    shareFeedbackStatus.textContent = "";
    delete shareFeedbackStatus.dataset.status;
  }
  if (shareFeedbackNotes) {
    shareFeedbackNotes.value = "";
  }
}

function disableShareFeedback() {
  if (!shareFeedbackContainer) {
    return;
  }
  shareFeedbackContainer.dataset.state = "disabled";
  shareFeedbackButtons.forEach((button) => button.setAttribute("disabled", "true"));
  if (shareFeedbackSubmit) {
    shareFeedbackSubmit.setAttribute("disabled", "true");
  }
}

function handleShareFeedbackChoice(value) {
  if (!shareFeedbackContainer || shareFeedbackContainer.dataset.state === "submitted") {
    return;
  }

  shareFeedbackSelection = value;
  shareFeedbackButtons.forEach((button) => {
    const selected = button.dataset.feedback === value;
    button.dataset.selected = selected ? "true" : "false";
    button.setAttribute("aria-pressed", selected ? "true" : "false");
  });
  if (shareFeedbackSubmit) {
    shareFeedbackSubmit.removeAttribute("disabled");
  }
  if (shareFeedbackStatus) {
    shareFeedbackStatus.textContent = "";
    delete shareFeedbackStatus.dataset.status;
  }
}

async function submitShareFeedback() {
  if (!shareFeedbackContainer || !shareFeedbackSubmit) {
    return;
  }

  const shareId = shareFeedbackContainer.dataset.shareId;
  if (!shareId || !shareFeedbackSelection) {
    return;
  }

  const notesValue = shareFeedbackNotes ? shareFeedbackNotes.value : "";
  const trimmedNotes = notesValue.trim();
  const body = { clarity: shareFeedbackSelection };
  if (trimmedNotes) {
    body.notes = trimmedNotes;
  }

  try {
    shareFeedbackSubmit.setAttribute("disabled", "true");
    shareFeedbackButtons.forEach((button) => button.setAttribute("disabled", "true"));
    if (shareFeedbackStatus) {
      shareFeedbackStatus.textContent = t("share.feedback_sending");
      shareFeedbackStatus.dataset.status = "pending";
    }

    const response = await fetch(`${SUMMARIES_ENDPOINT}/${shareId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.message || response.statusText);
    }

    shareFeedbackContainer.dataset.state = "submitted";
    if (shareFeedbackStatus) {
      shareFeedbackStatus.textContent = t("share.feedback_submitted");
      shareFeedbackStatus.dataset.status = "success";
    }
  } catch (error) {
    console.error("Failed to submit share feedback", error);
    shareFeedbackButtons.forEach((button) => button.removeAttribute("disabled"));
    if (shareFeedbackSubmit) {
      shareFeedbackSubmit.removeAttribute("disabled");
    }
    if (shareFeedbackStatus) {
      shareFeedbackStatus.textContent = t("share.feedback_error");
      shareFeedbackStatus.dataset.status = "error";
    }
  }
}

function updateShareLink(record) {
  const link = record?.links?.share_page || record?.links?.html || null;
  if (!shareLinkInput) {
    return;
  }

  if (link) {
    const absolute = link.startsWith("http")
      ? link
      : new URL(link, window.location.origin).toString();
    shareLinkInput.value = absolute;
    copyShareLinkButton?.removeAttribute("disabled");
  } else {
    shareLinkInput.value = "";
    copyShareLinkButton?.setAttribute("disabled", "true");
  }

  if (!shareExpiryElement) {
    return;
  }

  if (!record) {
    shareExpiryElement.textContent = t("share.expiry_notice");
    delete shareExpiryElement.dataset.status;
    resetShareFeedback();
    return;
  }

  const expiryDate = getShareExpiryDate(record);
  if (!expiryDate) {
    shareExpiryElement.textContent = t("share.expiry_notice");
    delete shareExpiryElement.dataset.status;
    resetShareFeedback();
    return;
  }

  if (expiryDate.getTime() <= Date.now()) {
    shareExpiryElement.textContent = t("share.expired");
    shareExpiryElement.dataset.status = "expired";
    copyShareLinkButton?.setAttribute("disabled", "true");
    disableShareFeedback();
    return;
  }

  shareExpiryElement.textContent = t("share.expires_at", {
    datetime: formatDateTime(expiryDate),
  });
  shareExpiryElement.dataset.status = "active";
  if (
    shareFeedbackContainer &&
    shareFeedbackContainer.dataset.state !== "submitted" &&
    shareFeedbackContainer.dataset.shareId === record.id
  ) {
    shareFeedbackContainer.removeAttribute("hidden");
  }
}

function buildDownloadFilename(extension) {
  const year = lastCalculation?.meta?.year ?? "summary";
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `greektax-${year}-${timestamp}.${extension}`;
}

function clearFormHints() {
  document.querySelectorAll(".form-control .form-hint").forEach((element) => {
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

  const detailLabels =
    UI_MESSAGES[currentLocale]?.detailFields || UI_MESSAGES.en.detailFields || {};

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
    gross_income: detailLabels.gross_income || "Gross income",
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
  downloadPdfButton?.removeAttribute("disabled");
  shareButton?.removeAttribute("disabled");
  printButton?.removeAttribute("disabled");
  copyShareLinkButton?.setAttribute("disabled", "true");
  lastShareRecord = null;
  lastShareSignature = null;
  updateShareLink(null);
  resetShareFeedback();

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
  downloadPdfButton?.setAttribute("disabled", "true");
  shareButton?.setAttribute("disabled", "true");
  printButton?.setAttribute("disabled", "true");
  copyShareLinkButton?.setAttribute("disabled", "true");
  lastCalculation = null;
  lastShareRecord = null;
  lastShareSignature = null;
  updateShareLink(null);
  resetShareFeedback();
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

async function downloadRemoteFile(url, filename) {
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    const message = errorPayload.message || response.statusText;
    throw new Error(message);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(objectUrl);
}

async function ensurePersistedSummary() {
  if (!lastCalculation) {
    return null;
  }

  const signature = JSON.stringify(lastCalculation);
  if (
    lastShareRecord &&
    lastShareSignature === signature &&
    !isShareRecordExpired(lastShareRecord)
  ) {
    updateShareLink(lastShareRecord);
    if (shareFeedbackContainer) {
      if (shareFeedbackContainer.dataset.shareId !== lastShareRecord.id) {
        prepareShareFeedback(lastShareRecord);
      } else if (shareFeedbackContainer.dataset.state !== "submitted") {
        shareFeedbackContainer.removeAttribute("hidden");
      }
    }
    return lastShareRecord;
  }

  setCalculatorStatus(t("status.persisting_share"));

  try {
    const response = await fetch(SUMMARIES_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result: lastCalculation }),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.message || response.statusText);
    }

    const record = await response.json();
    lastShareRecord = record;
    lastShareSignature = signature;
    updateShareLink(record);
    if (shareFeedbackContainer) {
      if (shareFeedbackContainer.dataset.shareId !== record.id) {
        prepareShareFeedback(record);
      } else if (shareFeedbackContainer.dataset.state !== "submitted") {
        shareFeedbackContainer.removeAttribute("hidden");
      }
    }
    setCalculatorStatus(t("status.share_ready"));
    return record;
  } catch (error) {
    console.error("Failed to persist shareable summary", error);
    setCalculatorStatus(t("status.share_failed"), { isError: true });
    throw error;
  }
}

async function downloadCsvSummary() {
  if (!lastCalculation) {
    return;
  }

  try {
    const record = await ensurePersistedSummary();
    if (!record?.links?.csv) {
      throw new Error("CSV export link missing");
    }
    await downloadRemoteFile(record.links.csv, buildDownloadFilename("csv"));
  } catch (error) {
    console.error("CSV download failed", error);
  }
}

async function downloadPdfSummary() {
  if (!lastCalculation) {
    return;
  }

  try {
    const record = await ensurePersistedSummary();
    if (!record?.links?.pdf) {
      throw new Error("PDF export link missing");
    }
    await downloadRemoteFile(record.links.pdf, buildDownloadFilename("pdf"));
  } catch (error) {
    console.error("PDF download failed", error);
  }
}

async function copyShareLink() {
  if (!shareLinkInput || !shareLinkInput.value) {
    return;
  }

  const text = shareLinkInput.value;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      shareLinkInput.focus();
      shareLinkInput.select();
      const success = document.execCommand("copy");
      if (!success) {
        throw new Error("copy command failed");
      }
    }
    setCalculatorStatus(t("share.copy_success"));
  } catch (error) {
    console.error("Clipboard interaction failed", error);
    setCalculatorStatus(t("share.copy_error"), { isError: true });
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildShareableSummaryHtml(result) {
  const summary = result.summary || {};
  const details = Array.isArray(result.details) ? result.details : [];
  const summaryLabels = summary.labels || {};
  const localeTag = resolveLocaleTag(currentLocale);
  const formsMessages = UI_MESSAGES[currentLocale]?.forms || UI_MESSAGES.en.forms;
  const detailLabels =
    UI_MESSAGES[currentLocale]?.detailFields || UI_MESSAGES.en.detailFields;

  const summaryRows = ["income_total", "tax_total", "net_income"]
    .filter((key) => key in summary)
    .map(
      (key) =>
        `<tr><th>${escapeHtml(summaryLabels[key] || key)}</th><td>${escapeHtml(
          formatCurrency(summary[key]),
        )}</td></tr>`,
    )
    .join("\n");

  const detailCards = details
    .map((detail) => {
      const cardRows = [];
      const mapping = {
        gross_income: detailLabels.gross_income || "Gross income",
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
      };
      Object.entries(mapping).forEach(([key, label]) => {
        if (detail[key] !== undefined && detail[key] !== null) {
          cardRows.push(
            `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(
              formatCurrency(detail[key]),
            )}</td></tr>`,
          );
        }
      });

      let breakdownHtml = "";
      if (detail.items && Array.isArray(detail.items) && detail.items.length) {
        const items = detail.items
          .map(
            (item) =>
              `<li>${escapeHtml(item.label)}: ${escapeHtml(
                formatCurrency(item.amount),
              )} → ${escapeHtml(formatCurrency(item.tax))} (${escapeHtml(
                formatPercent(item.rate),
              )})</li>`,
          )
          .join("\n");
        breakdownHtml = `<section class="breakdown"><h4>${escapeHtml(
          detailLabels.breakdown || "Breakdown",
        )}</h4><ul>${items}</ul></section>`;
      }

      return `<article class="detail-card"><h3>${escapeHtml(
        detail.label || detail.category,
      )}</h3><table>${cardRows.join("\n")}</table>${breakdownHtml}</article>`;
    })
    .join("\n");

  const generatedAt = new Date().toLocaleString(localeTag);

  return `<!DOCTYPE html>
<html lang="${escapeHtml(currentLocale === "el" ? "el" : "en")}">
  <head>
    <meta charset="utf-8" />
    <title>${escapeHtml(formsMessages.share_title || "GreekTax summary")}</title>
    <style>
      body { font-family: "Segoe UI", sans-serif; margin: 0; padding: 2rem; color: #212529; background: #f8f9fa; }
      h1, h2, h3, h4 { margin-top: 0; }
      header { margin-bottom: 1.5rem; }
      table { width: 100%; border-collapse: collapse; margin-bottom: 1rem; }
      th, td { padding: 0.5rem; text-align: left; border-bottom: 1px solid #dee2e6; }
      .summary-table th { width: 50%; }
      .detail-card { background: #fff; border: 1px solid #dee2e6; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; }
      .detail-card table { margin-bottom: 0; }
      .breakdown ul { margin: 0.5rem 0 0 1.25rem; }
      footer { margin-top: 2rem; font-size: 0.9rem; color: #6c757d; }
    </style>
  </head>
  <body>
    <header>
      <h1>${escapeHtml(formsMessages.share_heading || "Tax summary")}</h1>
      <p>${escapeHtml(generatedAt)}</p>
    </header>
    <section>
      <h2>${escapeHtml(formsMessages.summary_heading || "Overview")}</h2>
      <table class="summary-table">
        <tbody>
          ${summaryRows}
        </tbody>
      </table>
    </section>
    <section>
      <h2>${escapeHtml(formsMessages.detail_heading || "Detailed breakdown")}</h2>
      ${detailCards}
    </section>
    <footer>
      <p>${escapeHtml("Generated with the unofficial GreekTax calculator.")}</p>
    </footer>
  </body>
</html>`;
}

async function openShareableSummary() {
  if (!lastCalculation) {
    return;
  }

  try {
    const record = await ensurePersistedSummary();
    const shareLink = record?.links?.share_page || record?.links?.html;
    if (!shareLink) {
      throw new Error("Share link unavailable");
    }
    const absolute = shareLink.startsWith("http")
      ? shareLink
      : new URL(shareLink, window.location.origin).toString();
    const summaryWindow = window.open(absolute, "_blank", "noopener");
    if (!summaryWindow) {
      setCalculatorStatus(t("share.open_failed"), { isError: true });
    }
  } catch (error) {
    console.error("Failed to open share summary", error);
    setCalculatorStatus(t("share.open_failed"), { isError: true });
  }
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
  downloadPdfButton?.addEventListener("click", downloadPdfSummary);
  shareButton?.addEventListener("click", openShareableSummary);
  printButton?.addEventListener("click", printSummary);
  copyShareLinkButton?.addEventListener("click", copyShareLink);
  shareFeedbackButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const { feedback } = button.dataset;
      if (feedback) {
        handleShareFeedbackChoice(feedback);
      }
    });
  });
  shareFeedbackSubmit?.addEventListener("click", (event) => {
    event.preventDefault();
    submitShareFeedback();
  });

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
