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
const CALCULATOR_STORAGE_KEY = "greektax.calculator.v1";
const CALCULATOR_STORAGE_TTL_MS = 2 * 60 * 60 * 1000; // 2 hours

const UI_MESSAGES = {
  en: {
    ui: {
      tagline: "Unofficial tax estimation toolkit for Greece",
      overview_heading: "Overview",
      overview_description:
        "Estimate annual income taxes for Greece across employment, freelance, rental, and investment categories. Select a tax year, choose your language, and provide the income figures relevant to your situation to receive a bilingual breakdown of obligations.",
      disclaimer:
        "Disclaimer: This tool is unofficial and provided as-is. Inputs are stored locally on your device for up to two hours and are never sent to a server. Please consult a professional accountant for formal filings.",
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
        agricultural: "Agricultural income",
        other: "Other income",
        rental: "Rental income",
        investment: "Investment income",
        obligations: "Additional obligations",
        deductions: "Deductions",
      },
    },
    forms: {
      no_investment_categories: "No investment categories configured for this year.",
    },
    detailFields: {
      gross_income: "Gross income",
      deductible_contributions: "Mandatory contributions",
      category_contributions: "EFKA category contributions",
      additional_contributions: "Additional contributions",
      auxiliary_contributions: "Auxiliary contributions",
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
      employee_contributions: "Employee contributions",
      employer_contributions: "Employer contributions",
      employee_contributions_per_payment: "Employee contributions per payment",
      employer_contributions_per_payment: "Employer contributions per payment",
      breakdown: "Breakdown",
      deductions_applied: "Deductions applied",
    },
    fields: {
      "year-select": "Tax year",
      "children-input": "Dependent children",
      "employment-income": "Employment gross income (€)",
      "employment-monthly-income": "Monthly gross income (€)",
      "employment-payments": "Salary payments per year",
      "employment-mode": "Salary input type",
      "employment-mode-gross": "Enter gross amounts",
      "employment-mode-net": "Enter net amounts",
      "employment-net-income": "Annual net income (€)",
      "employment-net-monthly-income": "Net income per payment (€)",
      "pension-income": "Pension gross income (€)",
      "pension-mode": "Pension input type",
      "pension-mode-gross": "Enter gross amounts",
      "pension-mode-net": "Enter net amounts",
      "pension-payments": "Pension payments per year",
      "pension-net-income": "Annual net pension (€)",
      "pension-net-monthly-income": "Net pension per payment (€)",
      "freelance-revenue": "Freelance gross revenue (€)",
      "freelance-expenses": "Freelance deductible expenses (€)",
      "freelance-contributions": "Mandatory social contributions (€)",
      "freelance-auxiliary-contributions": "Auxiliary fund contributions (€)",
      "freelance-efka-category": "EFKA contribution category",
      "freelance-efka-category-placeholder": "Select EFKA category (optional)",
      "freelance-efka-months": "Contribution months",
      "freelance-trade-fee-location": "Trade fee location",
      "freelance-trade-fee-standard": "Standard amount",
      "freelance-trade-fee-reduced": "Reduced amount",
      "freelance-years-active": "Years self-employed",
      "freelance-newly-self-employed": "Newly self-employed",
      "trade-fee-toggle": "Include business activity fee",
      "toggle-freelance": "Include freelance income",
      "toggle-agricultural": "Include agricultural income",
      "toggle-other": "Include other income",
      "toggle-rental": "Include rental income",
      "toggle-investment": "Include investment income",
      "toggle-deductions": "Include deductions",
      "toggle-obligations": "Include additional obligations",
      "agricultural-revenue": "Agricultural revenue (€)",
      "agricultural-expenses": "Agricultural expenses (€)",
      "other-income": "Other taxable income (€)",
      "rental-income": "Rental gross income (€)",
      "rental-expenses": "Rental deductible expenses (€)",
      "deductions-donations": "Charitable donations (€)",
      "deductions-medical": "Medical expenses (€)",
      "deductions-education": "Education expenses (€)",
      "deductions-insurance": "Insurance premiums (€)",
      "vat-due": "VAT due (€)",
      "enfia-due": "ENFIA amount (€)",
      "luxury-due": "Luxury living tax (€)",
      freelance: {
        efka: {
          category: {
            general_a: "Category A (standard tier)",
            general_a_description:
              "Includes base EFKA contributions plus small auxiliary fund coverage.",
            general_b: "Category B (enhanced tier)",
            reduced: "Reduced contributions",
            reduced_description:
              "Available to eligible professionals with reduced EFKA obligations.",
          },
        },
      },
    },
    hints: {
      "employment-payments":
        "Most salaried roles use 14 payments (12 monthly plus bonuses). Adjust if your contract pays a different number of times per year.",
      "freelance-efka-category": "Select a contribution class to prefill mandatory EFKA payments.",
      "freelance-efka-category-base": "Base EFKA contribution: {{amount}} per month.",
      "freelance-efka-category-auxiliary": "Auxiliary fund contribution: {{amount}} per month.",
      "freelance-trade-fee": "Trade fee applied: {{amount}}.",
      "freelance-trade-fee-new": "Reduced rate applies for the first {{years}} years of activity.",
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
        "Αποποίηση ευθύνης: Το εργαλείο είναι ανεπίσημο και παρέχεται ως έχει. Τα δεδομένα εισόδου αποθηκεύονται τοπικά στη συσκευή σας για έως δύο ώρες και δεν αποστέλλονται σε διακομιστή. Συμβουλευτείτε λογιστή για επίσημες δηλώσεις.",
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
        agricultural: "Αγροτικό εισόδημα",
        other: "Λοιπά εισοδήματα",
        rental: "Εισόδημα από ενοίκια",
        investment: "Επενδυτικά εισοδήματα",
        obligations: "Πρόσθετες υποχρεώσεις",
        deductions: "Εκπτώσεις",
      },
    },
    forms: {
      no_investment_categories:
        "Δεν έχουν οριστεί επενδυτικές κατηγορίες για αυτό το έτος.",
    },
    detailFields: {
      gross_income: "Ακαθάριστο εισόδημα",
      deductible_contributions: "Υποχρεωτικές εισφορές",
      category_contributions: "Εισφορές κατηγορίας ΕΦΚΑ",
      additional_contributions: "Επιπλέον εισφορές",
      auxiliary_contributions: "Εισφορές επικουρικού",
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
      employee_contributions: "Εισφορές εργαζομένου",
      employer_contributions: "Εισφορές εργοδότη",
      employee_contributions_per_payment: "Εισφορές εργαζομένου ανά καταβολή",
      employer_contributions_per_payment: "Εισφορές εργοδότη ανά καταβολή",
      breakdown: "Ανάλυση",
      deductions_applied: "Εφαρμοσμένες εκπτώσεις",
    },
    fields: {
      "year-select": "Φορολογικό έτος",
      "children-input": "Εξαρτώμενα τέκνα",
      "employment-income": "Ακαθάριστο εισόδημα μισθωτών (€)",
      "employment-monthly-income": "Μηνιαίο ακαθάριστο εισόδημα (€)",
      "employment-payments": "Μισθολογικές καταβολές ανά έτος",
      "employment-mode": "Τύπος εισαγωγής μισθού",
      "employment-mode-gross": "Καταχώρηση ακαθάριστων ποσών",
      "employment-mode-net": "Καταχώρηση καθαρών ποσών",
      "employment-net-income": "Ετήσιο καθαρό εισόδημα (€)",
      "employment-net-monthly-income": "Καθαρό ποσό ανά καταβολή (€)",
      "pension-income": "Ακαθάριστο εισόδημα συντάξεων (€)",
      "pension-mode": "Τύπος εισαγωγής σύνταξης",
      "pension-mode-gross": "Καταχώρηση ακαθάριστων ποσών",
      "pension-mode-net": "Καταχώρηση καθαρών ποσών",
      "pension-payments": "Καταβολές συντάξεων ανά έτος",
      "pension-net-income": "Ετήσιο καθαρό ποσό σύνταξης (€)",
      "pension-net-monthly-income": "Καθαρό ποσό σύνταξης ανά καταβολή (€)",
      "freelance-revenue": "Ακαθάριστα έσοδα ελευθέρου επαγγελματία (€)",
      "freelance-expenses": "Εκπιπτόμενες δαπάνες ελευθέρου επαγγελματία (€)",
      "freelance-contributions": "Υποχρεωτικές εισφορές (€)",
      "freelance-auxiliary-contributions": "Εισφορές επικουρικού ταμείου (€)",
      "freelance-efka-category": "Κατηγορία εισφορών ΕΦΚΑ",
      "freelance-efka-category-placeholder": "Επιλέξτε κατηγορία ΕΦΚΑ (προαιρετικά)",
      "freelance-efka-months": "Μήνες εισφορών",
      "freelance-trade-fee-location": "Περιοχή τέλους επιτηδεύματος",
      "freelance-trade-fee-standard": "Τυπικό ποσό",
      "freelance-trade-fee-reduced": "Μειωμένο ποσό",
      "freelance-years-active": "Έτη ως ελεύθερος επαγγελματίας",
      "freelance-newly-self-employed": "Νεοσύστατος επαγγελματίας",
      "trade-fee-toggle": "Συμπερίληψη τέλους επιτηδεύματος",
      "toggle-freelance": "Συμπερίληψη εισοδήματος ελευθέρων επαγγελματιών",
      "toggle-agricultural": "Συμπερίληψη αγροτικού εισοδήματος",
      "toggle-other": "Συμπερίληψη λοιπών εισοδημάτων",
      "toggle-rental": "Συμπερίληψη εισοδήματος από ενοίκια",
      "toggle-investment": "Συμπερίληψη επενδυτικών εισοδημάτων",
      "toggle-deductions": "Συμπερίληψη εκπτώσεων",
      "toggle-obligations": "Συμπερίληψη πρόσθετων υποχρεώσεων",
      "agricultural-revenue": "Ακαθάριστα αγροτικά έσοδα (€)",
      "agricultural-expenses": "Εκπιπτόμενες αγροτικές δαπάνες (€)",
      "other-income": "Λοιπά φορολογητέα εισοδήματα (€)",
      "rental-income": "Ακαθάριστα έσοδα ενοικίων (€)",
      "rental-expenses": "Εκπιπτόμενες δαπάνες ενοικίων (€)",
      "deductions-donations": "Δωρεές (€)",
      "deductions-medical": "Ιατρικές δαπάνες (€)",
      "deductions-education": "Εκπαιδευτικές δαπάνες (€)",
      "deductions-insurance": "Ασφαλιστικά ασφάλιστρα (€)",
      "vat-due": "Οφειλόμενος ΦΠΑ (€)",
      "enfia-due": "Ποσό ΕΝΦΙΑ (€)",
      "luxury-due": "Φόρος πολυτελούς διαβίωσης (€)",
      freelance: {
        efka: {
          category: {
            general_a: "Κατηγορία Α (τυπική)",
            general_a_description:
              "Περιλαμβάνει βασικές εισφορές ΕΦΚΑ και μικρή επικουρική κάλυψη.",
            general_b: "Κατηγορία Β (ενισχυμένη)",
            reduced: "Μειωμένες εισφορές",
            reduced_description:
              "Διαθέσιμη σε επαγγελματίες με δικαίωμα μειωμένων εισφορών.",
          },
        },
      },
    },
    hints: {
      "employment-payments":
        "Συνήθως καταβάλλονται 14 μισθοί (12 μηνιαίοι και 2 δώρα). Προσαρμόστε τον αριθμό αν η σύμβασή σας προβλέπει διαφορετικές καταβολές ανά έτος.",
      "freelance-efka-category": "Επιλέξτε κατηγορία εισφορών για αυτόματη συμπλήρωση των υποχρεωτικών ποσών.",
      "freelance-efka-category-base": "Βασική εισφορά ΕΦΚΑ: {{amount}} ανά μήνα.",
      "freelance-efka-category-auxiliary": "Εισφορά επικουρικού ταμείου: {{amount}} ανά μήνα.",
      "freelance-trade-fee": "Εφαρμοζόμενο τέλος επιτηδεύματος: {{amount}}.",
      "freelance-trade-fee-new": "Ισχύει μειωμένο ποσό για τα πρώτα {{years}} έτη δραστηριότητας.",
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
const yearMetadataByYear = new Map();
let currentYearMetadata = null;
let currentEmploymentMode = "gross";
let currentPensionMode = "gross";
let currentInvestmentCategories = [];
let currentDeductionHints = [];
let currentFreelanceMetadata = null;
let dynamicFieldLabels = {};
let deductionValidationByInput = {};
let lastCalculation = null;
let pendingCalculatorState = null;
let calculatorStatePersistHandle = null;

const localeSelect = document.getElementById("locale-select");
const previewButton = document.getElementById("preview-button");
const previewStatus = document.getElementById("preview-status");
const previewJson = document.getElementById("preview-json");

const yearSelect = document.getElementById("year-select");
const childrenInput = document.getElementById("children-input");
const employmentModeSelect = document.getElementById("employment-mode");
const employmentIncomeInput = document.getElementById("employment-income");
const employmentMonthlyIncomeInput = document.getElementById(
  "employment-monthly-income",
);
const employmentNetIncomeInput = document.getElementById(
  "employment-net-income",
);
const employmentNetMonthlyIncomeInput = document.getElementById(
  "employment-net-monthly-income",
);
const employmentPaymentsInput = document.getElementById("employment-payments");
const pensionModeSelect = document.getElementById("pension-mode");
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
const tradeFeeToggle = document.getElementById("trade-fee-toggle");
const freelanceEfkaSelect = document.getElementById("freelance-efka-category");
const freelanceEfkaMonthsInput = document.getElementById("freelance-efka-months");
const freelanceEfkaHint = document.getElementById("freelance-efka-category-hint");
const freelanceTradeFeeLocationSelect = document.getElementById(
  "freelance-trade-fee-location",
);
const freelanceTradeFeeHint = document.getElementById("freelance-trade-fee-hint");
const freelanceYearsActiveInput = document.getElementById("freelance-years-active");
const freelanceNewlySelfEmployedToggle = document.getElementById(
  "freelance-newly-self-employed",
);
const rentalIncomeInput = document.getElementById("rental-income");
const rentalExpensesInput = document.getElementById("rental-expenses");
const investmentFieldsContainer = document.getElementById("investment-fields");
const agriculturalRevenueInput = document.getElementById("agricultural-revenue");
const agriculturalExpensesInput = document.getElementById("agricultural-expenses");
const otherIncomeInput = document.getElementById("other-income");
const deductionsDonationsInput = document.getElementById("deductions-donations");
const deductionsMedicalInput = document.getElementById("deductions-medical");
const deductionsEducationInput = document.getElementById("deductions-education");
const deductionsInsuranceInput = document.getElementById("deductions-insurance");
const vatInput = document.getElementById("vat-due");
const enfiaInput = document.getElementById("enfia-due");
const luxuryInput = document.getElementById("luxury-due");
const freelanceSection = document.getElementById("freelance-section");
const agriculturalSection = document.getElementById("agricultural-section");
const otherSection = document.getElementById("other-section");
const rentalSection = document.getElementById("rental-section");
const investmentSection = document.getElementById("investment-section");
const deductionsSection = document.getElementById("deductions-section");
const obligationsSection = document.getElementById("obligations-section");
const toggleFreelance = document.getElementById("toggle-freelance");
const toggleAgricultural = document.getElementById("toggle-agricultural");
const toggleOther = document.getElementById("toggle-other");
const toggleRental = document.getElementById("toggle-rental");
const toggleInvestment = document.getElementById("toggle-investment");
const toggleDeductions = document.getElementById("toggle-deductions");
const toggleObligations = document.getElementById("toggle-obligations");
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

function loadStoredCalculatorState() {
  try {
    const raw = window.localStorage.getItem(CALCULATOR_STORAGE_KEY);
    if (!raw) {
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
  populateFreelanceMetadata(currentFreelanceMetadata);
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

function isInputVisible(input) {
  if (!input) {
    return false;
  }
  if (input.hidden) {
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
    const defaultValue = input.defaultValue ?? "0";
    input.value = defaultValue || "0";
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
    select.selectedIndex = 0;
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
}

function initialiseSectionToggles() {
  const toggles = [
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

  if (employmentModeSelect) {
    updateEmploymentMode(employmentModeSelect.value || "gross");
  }
  if (pensionModeSelect) {
    updatePensionMode(pensionModeSelect.value || "gross");
  }

  const toggles = [
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

function updateSectionMode(section, mode) {
  const desiredMode = mode === "net" ? "net" : "gross";
  document
    .querySelectorAll(`.form-control[data-section="${section}"]`)
    .forEach((control) => {
      const controlMode = control.getAttribute("data-mode");
      if (!controlMode) {
        return;
      }
      const isVisible = controlMode === desiredMode;
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
  currentEmploymentMode = mode === "net" ? "net" : "gross";
  if (employmentModeSelect) {
    employmentModeSelect.value = currentEmploymentMode;
  }
  updateSectionMode("employment", currentEmploymentMode);
}

function updatePensionMode(mode) {
  currentPensionMode = mode === "net" ? "net" : "gross";
  if (pensionModeSelect) {
    pensionModeSelect.value = currentPensionMode;
  }
  updateSectionMode("pension", currentPensionMode);
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

function applyYearMetadata(year) {
  currentYearMetadata = yearMetadataByYear.get(year) || null;
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

function updateFreelanceCategoryHint() {
  if (!freelanceEfkaHint) {
    return;
  }

  if (!freelanceEfkaSelect || !freelanceEfkaSelect.value) {
    const message = t("hints.freelance-efka-category");
    if (message) {
      freelanceEfkaHint.textContent = message;
      freelanceEfkaHint.hidden = false;
    } else {
      freelanceEfkaHint.textContent = "";
      freelanceEfkaHint.hidden = true;
    }
    return;
  }

  const option = freelanceEfkaSelect.selectedOptions?.[0];
  if (!option) {
    freelanceEfkaHint.textContent = "";
    freelanceEfkaHint.hidden = true;
    return;
  }

  const monthlyAmount = Number.parseFloat(option.dataset.monthlyAmount || "0");
  const auxiliaryAmount = Number.parseFloat(
    option.dataset.auxiliaryMonthlyAmount || "0",
  );
  const descriptionKey = option.dataset.descriptionKey;

  const parts = [];
  if (Number.isFinite(monthlyAmount) && monthlyAmount > 0) {
    parts.push(
      t("hints.freelance-efka-category-base", {
        amount: formatCurrency(monthlyAmount),
      }),
    );
  }
  if (Number.isFinite(auxiliaryAmount) && auxiliaryAmount > 0) {
    parts.push(
      t("hints.freelance-efka-category-auxiliary", {
        amount: formatCurrency(auxiliaryAmount),
      }),
    );
  }
  if (descriptionKey) {
    parts.push(t(descriptionKey));
  }

  freelanceEfkaHint.textContent = parts.join(" ");
  freelanceEfkaHint.hidden = parts.length === 0;
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

  if (typeof amount !== "number" || Number.isNaN(amount)) {
    freelanceTradeFeeHint.textContent = "";
    freelanceTradeFeeHint.hidden = true;
    return;
  }

  const messages = [
    t("hints.freelance-trade-fee", { amount: formatCurrency(amount) }),
  ];

  if (tradeFee.newly_self_employed_reduction_years) {
    messages.push(
      t("hints.freelance-trade-fee-new", {
        years: tradeFee.newly_self_employed_reduction_years,
      }),
    );
  }

  freelanceTradeFeeHint.textContent = messages.join(" ");
  freelanceTradeFeeHint.hidden = false;
}

function populateFreelanceMetadata(metadata) {
  currentFreelanceMetadata = metadata || null;

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

  updateFreelanceCategoryHint();
  updateTradeFeeHint();
  applyPendingCalculatorState();
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

  if (!isInputVisible(input)) {
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
  if (!isInputVisible(input)) {
    return 0;
  }
  const normalised = (input.value ?? "0").toString().replace(",", ".");
  const value = Number.parseFloat(normalised);
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
  const normalised = (input.value ?? "0").toString().trim();
  const value = Number.parseInt(normalised, 10);
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
  const employmentMode = employmentModeSelect?.value || currentEmploymentMode;
  if (employmentMode === "net") {
    const netIncome = readNumber(employmentNetIncomeInput);
    if (netIncome > 0) {
      employmentPayload.net_income = netIncome;
    }
    const netMonthly = readNumber(employmentNetMonthlyIncomeInput);
    if (netMonthly > 0) {
      employmentPayload.net_monthly_income = netMonthly;
    }
  } else {
    const grossIncome = readNumber(employmentIncomeInput);
    if (grossIncome > 0) {
      employmentPayload.gross_income = grossIncome;
    }

    const monthlyIncome = readNumber(employmentMonthlyIncomeInput);
    if (monthlyIncome > 0) {
      employmentPayload.monthly_income = monthlyIncome;
    }
  }

  const employmentPayments = resolvePaymentsValue(
    employmentPaymentsInput,
    "employment",
  );
  if (
    employmentPayments &&
    (employmentPayload.net_income !== undefined ||
      employmentPayload.net_monthly_income !== undefined ||
      employmentPayload.gross_income !== undefined ||
      employmentPayload.monthly_income !== undefined)
  ) {
    employmentPayload.payments_per_year = employmentPayments;
  }

  if (Object.keys(employmentPayload).length > 0) {
    payload.employment = employmentPayload;
  }

  const pensionPayload = {};
  const pensionMode = pensionModeSelect?.value || currentPensionMode;
  if (pensionMode === "net") {
    const netIncome = readNumber(pensionNetIncomeInput);
    if (netIncome > 0) {
      pensionPayload.net_income = netIncome;
    }
    const netMonthly = readNumber(pensionNetMonthlyIncomeInput);
    if (netMonthly > 0) {
      pensionPayload.net_monthly_income = netMonthly;
    }
  } else {
    const pensionGross = readNumber(pensionIncomeInput);
    if (pensionGross > 0) {
      pensionPayload.gross_income = pensionGross;
    }
  }

  const pensionPayments = resolvePaymentsValue(pensionPaymentsInput, "pension");
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

  if (isSectionActive(freelanceSection)) {
    const freelancePayload = {};
    const revenue = readNumber(freelanceRevenueInput);
    const expenses = readNumber(freelanceExpensesInput);
    const contributions = readNumber(freelanceContributionsInput);
    const auxiliary = readNumber(freelanceAuxiliaryContributionsInput);
    const efkaCategory = freelanceEfkaSelect?.value;
    const efkaMonths = readInteger(freelanceEfkaMonthsInput);
    const tradeFeeLocation = freelanceTradeFeeLocationSelect?.value;
    const yearsActive = readInteger(freelanceYearsActiveInput);

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
    if (freelanceNewlySelfEmployedToggle?.checked) {
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
    if (revenue > 0 || expenses > 0) {
      payload.agricultural = {
        gross_revenue: revenue,
        deductible_expenses: expenses,
      };
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
      vat: readNumber(vatInput),
      enfia: readNumber(enfiaInput),
      luxury: readNumber(luxuryInput),
    };
    if (Object.values(obligationsPayload).some((value) => value > 0)) {
      payload.obligations = obligationsPayload;
    }
  }

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
    employee_contributions:
      detailLabels.employee_contributions || "Employee contributions",
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
    { key: "deductions_applied", formatter: formatCurrency },
    { key: "deductions_entered", formatter: formatCurrency },
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

  pendingCalculatorState = loadStoredCalculatorState();
  applyPendingCalculatorState();

  if (employmentModeSelect) {
    currentEmploymentMode = employmentModeSelect.value || "gross";
    updateEmploymentMode(currentEmploymentMode);
  }

  if (pensionModeSelect) {
    currentPensionMode = pensionModeSelect.value || "gross";
    updatePensionMode(currentPensionMode);
  }

  initialiseSectionToggles();
  applyPendingCalculatorState();
  freelanceEfkaSelect?.addEventListener("change", updateFreelanceCategoryHint);
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
  });

  employmentModeSelect?.addEventListener("change", (event) => {
    const target = event.target;
    const value = typeof target?.value === "string" ? target.value : "gross";
    updateEmploymentMode(value);
  });

  pensionModeSelect?.addEventListener("change", (event) => {
    const target = event.target;
    const value = typeof target?.value === "string" ? target.value : "gross";
    updatePensionMode(value);
  });

  downloadButton?.addEventListener("click", downloadJsonSummary);
  downloadCsvButton?.addEventListener("click", downloadCsvSummary);
  printButton?.addEventListener("click", printSummary);

  attachValidationHandlers();

  loadYearOptions().then(async () => {
    applyPendingCalculatorState();
    await refreshInvestmentCategories();
    applyPendingCalculatorState();
    await refreshDeductionHints();
    applyPendingCalculatorState();
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
