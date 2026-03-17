export const DISTRIBUTION_EXPENSE_FIELDS = ["deductible_expenses"];
export const DISTRIBUTION_TAX_CATEGORIES = new Set(["luxury", "enfia"]);

function sumDetailFields(detail, fields, toFiniteNumber) {
  if (!detail) {
    return 0;
  }
  return fields.reduce((total, field) => {
    const amount = toFiniteNumber(detail[field]);
    return amount > 0 ? total + amount : total;
  }, 0);
}

function computeDistributionForDetail(detail, toFiniteNumber) {
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

  let expenses = sumDetailFields(detail, DISTRIBUTION_EXPENSE_FIELDS, toFiniteNumber);

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

export function computeDistributionTotals(details, options = {}) {
  const toFiniteNumber = options.toFiniteNumber || ((value) => {
    const parsed = Number.parseFloat(value ?? 0);
    return Number.isFinite(parsed) ? parsed : 0;
  });
  const resolveLabel =
    options.resolveLabel ||
    (() => "Total income");

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
    const breakdown = computeDistributionForDetail(detail, toFiniteNumber);

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

      const label = resolveLabel(detail);
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
