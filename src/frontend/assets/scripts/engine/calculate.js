/**
 * Client-side tax calculation, mirroring calculate_tax in
 * src/greektax/backend/app/services/calculation_service.py.
 *
 * calculateTax(payload) returns the same JSON structure as
 * POST /api/v1/calculations, or throws EngineError with the same message the
 * API returns in its 400 response.
 */

import { ENGINE_DATA } from "../data/engine-data.generated.js";
import { calculateProgressiveTax } from "./brackets.js";
import { calculateGeneralIncome } from "./generalIncome.js";
import { normalisePayload } from "./normalise.js";
import { pyRound } from "./pyMath.js";
import { EngineError, parseCalculationRequest } from "./request.js";

export { EngineError };

const BASE_LOCALE = "en";
const roundCurrency = (value) => pyRound(value, 2);

/** get_translator: locale catalogue with English fallback, then the key. */
export function getTranslator(locale) {
  const requested = locale ? String(locale).toLowerCase().split("-")[0] : BASE_LOCALE;
  const resolved = ENGINE_DATA.locales.includes(requested) ? requested : BASE_LOCALE;
  const messages = ENGINE_DATA.translations[resolved] || {};
  const fallback = ENGINE_DATA.translations[BASE_LOCALE] || {};
  const translate = (key) => {
    if (Object.prototype.hasOwnProperty.call(messages, key)) {
      return messages[key];
    }
    return Object.prototype.hasOwnProperty.call(fallback, key) ? fallback[key] : key;
  };
  translate.locale = resolved;
  return translate;
}

function rentalDetail(input, config, translate) {
  if (!input.has_rental_income) {
    return null;
  }
  const gross = input.rental_gross_income;
  const expenses = input.rental_deductible_expenses;
  const taxable = input.rental_taxable_income;
  const tax = calculateProgressiveTax(taxable, config.rental.brackets);
  return {
    category: "rental",
    label: translate("details.rental"),
    gross_income: roundCurrency(gross),
    deductible_expenses: roundCurrency(expenses),
    taxable_income: roundCurrency(taxable),
    tax: roundCurrency(tax),
    total_tax: roundCurrency(tax),
    net_income: roundCurrency(gross - expenses - tax),
  };
}

function investmentDetail(input, config, translate) {
  if (!input.has_investment_income) {
    return null;
  }
  const items = [];
  let grossTotal = 0;
  let taxTotal = 0;
  for (const [category, rate] of config.investment.rates) {
    const amount = Object.prototype.hasOwnProperty.call(input.investment_amounts, category)
      ? input.investment_amounts[category]
      : 0;
    if (amount <= 0) {
      continue;
    }
    const tax = amount * rate;
    grossTotal += amount;
    taxTotal += tax;
    items.push({
      type: category,
      label: translate(`details.investment.${category}`),
      amount: roundCurrency(amount),
      rate,
      tax: roundCurrency(tax),
    });
  }
  if (grossTotal <= 0) {
    return null;
  }
  return {
    category: "investment",
    label: translate("details.investment"),
    gross_income: roundCurrency(grossTotal),
    tax: roundCurrency(taxTotal),
    total_tax: roundCurrency(taxTotal),
    net_income: roundCurrency(grossTotal - taxTotal),
    items,
  };
}

function obligationDetail(category, amount, translate) {
  if (!(amount > 0)) {
    return null;
  }
  const rounded = roundCurrency(amount);
  return {
    category,
    label: translate(`details.${category}`),
    tax: rounded,
    total_tax: rounded,
    net_income: roundCurrency(-amount),
  };
}

/** Drop null values recursively, as model_dump(exclude_none=True) does. */
function excludeNone(value) {
  if (Array.isArray(value)) {
    return value.map(excludeNone);
  }
  if (value !== null && typeof value === "object") {
    const result = {};
    for (const [key, entry] of Object.entries(value)) {
      if (entry !== null && entry !== undefined) {
        result[key] = excludeNone(entry);
      }
    }
    return result;
  }
  return value;
}

export function calculateTax(payload) {
  const request = parseCalculationRequest(payload);
  const config = ENGINE_DATA.years[String(request.year)];
  if (!config) {
    throw new EngineError(`Configuration for year ${request.year} not found`);
  }

  const input = normalisePayload(request, config);
  const translate = getTranslator(input.locale);

  const general = calculateGeneralIncome(input, config, translate);
  const details = [...general.details];
  const totals = { income: 0, tax: 0, net: 0, taxable: 0 };
  totals.income += general.totals.income;
  totals.tax += general.totals.tax;
  totals.net += general.totals.net;
  totals.taxable += general.totals.taxable;

  const extraDetails = [
    rentalDetail(input, config, translate),
    investmentDetail(input, config, translate),
    obligationDetail("enfia", input.enfia_due, translate),
    obligationDetail("luxury", input.luxury_due, translate),
  ];
  for (const detail of extraDetails) {
    if (!detail) {
      continue;
    }
    details.push(detail);
    for (const [field, key] of [
      ["gross_income", "income"],
      ["total_tax", "tax"],
      ["net_income", "net"],
      ["taxable_income", "taxable"],
    ]) {
      if (typeof detail[field] === "number") {
        totals[key] += detail[field];
      }
    }
  }

  const incomeTotal = totals.income;
  const taxTotal = totals.tax;
  const netIncome = totals.net;
  const netMonthlyIncome = netIncome ? netIncome / 12 : 0;
  const averageMonthlyTax = taxTotal ? taxTotal / 12 : 0;
  const effectiveTaxRate = incomeTotal > 0 ? taxTotal / incomeTotal : 0;
  const withholdingTax = input.withholding_tax > 0 ? input.withholding_tax : 0;

  const summary = {
    income_total: roundCurrency(incomeTotal),
    taxable_income: roundCurrency(totals.taxable),
    tax_total: roundCurrency(taxTotal),
    net_income: roundCurrency(netIncome),
    net_monthly_income: roundCurrency(netMonthlyIncome),
    average_monthly_tax: roundCurrency(averageMonthlyTax),
    effective_tax_rate: pyRound(effectiveTaxRate, 4),
    deductions_entered: roundCurrency(input.total_deductions),
    deductions_applied: roundCurrency(general.deductionsApplied),
    labels: {
      income_total: translate("summary.income_total"),
      taxable_income: translate("summary.taxable_income"),
      tax_total: translate("summary.tax_total"),
      net_income: translate("summary.net_income"),
      net_monthly_income: translate("summary.net_monthly_income"),
      average_monthly_tax: translate("summary.average_monthly_tax"),
      effective_tax_rate: translate("summary.effective_tax_rate"),
      deductions_entered: translate("summary.deductions_entered"),
      deductions_applied: translate("summary.deductions_applied"),
    },
  };

  if (withholdingTax > 0) {
    summary.withholding_tax = roundCurrency(withholdingTax);
    summary.labels.withholding_tax = translate("summary.withholding_tax");
    const balanceDue = taxTotal - withholdingTax;
    const isRefund = balanceDue < 0;
    summary.balance_due = roundCurrency(isRefund ? -balanceDue : balanceDue);
    summary.balance_due_is_refund = isRefund;
    summary.labels.balance_due = translate(isRefund ? "summary.refund_due" : "summary.balance_due");
  }

  if (general.breakdown.length) {
    summary.deductions_breakdown = general.breakdown.map((entry) => ({
      type: entry.type,
      label: entry.label,
      entered: roundCurrency(entry.entered),
      eligible: roundCurrency(entry.eligible),
      credit_rate: entry.credit_rate,
      credit_requested: roundCurrency(entry.credit_requested),
      credit_applied: roundCurrency(entry.credit_applied),
      notes: entry.notes,
    }));
  }

  const meta = { year: input.year, locale: translate.locale };
  const youthCategory = input.youth_rate_category;
  if (youthCategory) {
    meta.youth_relief_category = youthCategory;
  }

  return excludeNone({ summary, details, meta });
}
