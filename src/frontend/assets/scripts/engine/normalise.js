/**
 * Payload normalisation and derived inputs, mirroring _normalise_payload in
 * calculation_service.py and CalculationInput in models/__init__.py.
 */

import { EngineError, formatValidationErrors } from "./request.js";

function validatePayments(value, payroll, fieldName) {
  if (value === null) {
    return null;
  }
  if (value < 0) {
    throw new EngineError(`Field '${fieldName}' cannot be negative`);
  }
  if (!payroll.allowed.includes(value)) {
    throw new EngineError(
      `Field '${fieldName}' must match an allowed payroll frequency (${payroll.allowed.join(", ")})`,
    );
  }
  return value;
}

/** Derived values computed by CalculationInput properties. */
export class CalculationInput {
  constructor(fields) {
    Object.assign(this, fields);
    this.validateBirthYear();
  }

  validateBirthYear() {
    if (this.taxpayer_birth_year === null) {
      return;
    }
    const reference = this.age_reference_year;
    const maxAllowed = reference > this.year ? reference - 1 : this.year;
    if (this.taxpayer_birth_year > maxAllowed) {
      throw new EngineError(
        formatValidationErrors([
          { loc: [], msg: `Value error, taxpayer_birth_year must be ${maxAllowed} or earlier` },
        ]),
      );
    }
  }

  get freelance_effective_category_contribution() {
    return this.freelance_include_category_contributions ? this.freelance_category_contribution : 0;
  }

  get freelance_effective_mandatory_contribution() {
    return this.freelance_include_mandatory_contributions
      ? this.freelance_additional_contributions
      : 0;
  }

  get freelance_effective_auxiliary_contribution() {
    return this.freelance_include_auxiliary_contributions
      ? this.freelance_auxiliary_contributions
      : 0;
  }

  get freelance_effective_lump_sum_contribution() {
    return this.freelance_include_lump_sum_contributions
      ? this.freelance_lump_sum_contributions
      : 0;
  }

  get total_freelance_contributions() {
    return (
      this.freelance_effective_category_contribution +
      this.freelance_effective_mandatory_contribution +
      this.freelance_effective_auxiliary_contribution +
      this.freelance_effective_lump_sum_contribution
    );
  }

  get freelance_taxable_income() {
    const taxable = this.freelance_profit - this.total_freelance_contributions;
    return taxable > 0 ? taxable : 0;
  }

  get has_employment_income() {
    return this.employment_income > 0;
  }

  get has_pension_income() {
    return this.pension_income > 0;
  }

  get has_freelance_income() {
    return (
      this.freelance_profit > 0 ||
      this.total_freelance_contributions > 0 ||
      this.freelance_taxable_income > 0
    );
  }

  get agricultural_taxable_income() {
    const profit = this.agricultural_gross_revenue - this.agricultural_deductible_expenses;
    return profit > 0 ? profit : 0;
  }

  get has_agricultural_income() {
    return (
      this.agricultural_gross_revenue > 0 ||
      this.agricultural_deductible_expenses > 0 ||
      this.agricultural_taxable_income > 0
    );
  }

  get rental_taxable_income() {
    const taxable = this.rental_gross_income - this.rental_deductible_expenses;
    return taxable > 0 ? taxable : 0;
  }

  get has_rental_income() {
    return (
      this.rental_gross_income > 0 ||
      this.rental_deductible_expenses > 0 ||
      this.rental_taxable_income > 0
    );
  }

  get has_investment_income() {
    return Object.values(this.investment_amounts).some((amount) => amount > 0);
  }

  get has_other_income() {
    return this.other_taxable_income > 0;
  }

  get has_non_agricultural_taxable_income() {
    return (
      this.has_employment_income ||
      this.has_pension_income ||
      this.freelance_taxable_income > 0 ||
      this.other_taxable_income > 0 ||
      this.rental_taxable_income > 0 ||
      this.has_investment_income
    );
  }

  get qualifies_for_agricultural_tax_credit() {
    if (!this.has_agricultural_income) {
      return false;
    }
    if (this.agricultural_professional_farmer) {
      return true;
    }
    return !this.has_non_agricultural_taxable_income;
  }

  get total_deductions() {
    const total =
      this.deductions_donations +
      this.deductions_medical +
      this.deductions_education +
      this.deductions_insurance;
    return total > 0 ? total : 0;
  }

  get youth_rate_category() {
    if (this.taxpayer_birth_year === null) {
      return null;
    }
    const age = this.age_reference_year - this.taxpayer_birth_year;
    if (age < 0) {
      return null;
    }
    for (const [bandId, maxAge] of this.youth_bands) {
      if (age <= maxAge) {
        return bandId;
      }
    }
    return null;
  }
}

/** _normalise_payload: turn a validated request into a CalculationInput. */
export function normalisePayload(request, config) {
  const birthYear = request.demographics.birth_year;

  const employment = request.employment;
  const employmentPayroll = config.employment.payroll;
  let employmentPayments = validatePayments(
    employment.payments_per_year,
    employmentPayroll,
    "employment.payments_per_year",
  );
  let employmentMonthlyIncome = null;
  let employmentIncome = 0;
  const employmentDeclaredGross = employment.gross_income;
  if (employment.monthly_income !== null && employment.monthly_income > 0) {
    const payments = employmentPayments || employmentPayroll.default;
    employmentPayments = payments;
    employmentMonthlyIncome = employment.monthly_income;
    employmentIncome = employmentMonthlyIncome * payments;
  }
  if (employment.gross_income > 0) {
    employmentIncome = employment.gross_income;
    if (employmentPayments && employmentMonthlyIncome === null) {
      employmentMonthlyIncome = employmentIncome / employmentPayments;
    }
  }

  const freelance = request.freelance;
  let profit;
  if (freelance.profit === null) {
    profit = freelance.gross_revenue - freelance.deductible_expenses;
    if (profit < 0) {
      profit = 0;
    }
  } else {
    profit = freelance.profit;
  }

  const categoryId = (freelance.efka_category || "").trim();
  let category = null;
  if (categoryId) {
    category = config.freelance.efka_categories.find((entry) => entry.id === categoryId) || null;
    if (category === null) {
      throw new EngineError("Unknown EFKA category selection");
    }
  }
  let categoryMonths = freelance.efka_months;
  if (categoryMonths !== null && categoryMonths <= 0) {
    categoryMonths = null;
  }
  if (categoryMonths === null && category !== null && freelance.include_category_contributions) {
    categoryMonths = 12;
  }
  let categoryContribution = 0;
  if (category !== null && categoryMonths && freelance.include_category_contributions) {
    categoryContribution = category.monthly_amount * categoryMonths;
  }

  const pension = request.pension;
  const pensionPayroll = config.pension.payroll;
  let pensionPayments = validatePayments(
    pension.payments_per_year,
    pensionPayroll,
    "pension.payments_per_year",
  );
  let pensionMonthlyIncome = null;
  let pensionIncome = 0;
  const pensionDeclaredGross = pension.gross_income;
  if (pension.monthly_income !== null && pension.monthly_income > 0) {
    const payments = pensionPayments || pensionPayroll.default;
    pensionPayments = payments;
    pensionMonthlyIncome = pension.monthly_income;
    pensionIncome = pensionMonthlyIncome * payments;
  }
  if (pension.gross_income > 0) {
    pensionIncome = pension.gross_income;
    if (pensionPayments && pensionMonthlyIncome === null) {
      pensionMonthlyIncome = pensionIncome / pensionPayments;
    }
  }

  const investmentAmounts = { ...request.investment };
  const agricultural = request.agricultural;
  const otherIncome = request.other.taxable_income;

  const birthYearLimit = config.rules.max_birth_year_with_income;
  if (birthYear !== null && birthYearLimit !== null && birthYear > birthYearLimit) {
    const hasIncome =
      employmentIncome > 0 ||
      pensionIncome > 0 ||
      profit > 0 ||
      request.rental.gross_income > 0 ||
      agricultural.gross_revenue > 0 ||
      otherIncome > 0 ||
      Object.values(investmentAmounts).some((value) => value > 0);
    if (hasIncome) {
      throw new EngineError(
        "Invalid calculation payload: demographics.birth_year must be " +
          `${birthYearLimit} or earlier when income is provided`,
      );
    }
  }

  return new CalculationInput({
    year: request.year,
    locale: request.locale || "en",
    children: request.dependents.children,
    taxpayer_birth_year: birthYear,
    tax_residency_transfer_to_greece: request.demographics.tax_residency_transfer_to_greece,
    age_reference_year: config.rules.age_reference_year,
    youth_bands: config.rules.youth_bands,
    employment_income: employmentIncome,
    employment_monthly_income: employmentMonthlyIncome,
    employment_payments_per_year: employmentPayments,
    employment_manual_contributions: employment.employee_contributions,
    employment_include_employee_contributions: employment.include_employee_contributions,
    employment_include_manual_contributions: employment.include_manual_employee_contributions,
    employment_include_employer_contributions: employment.include_employer_contributions,
    employment_declared_gross_income: employmentDeclaredGross,
    withholding_tax: request.withholding_tax,
    pension_income: pensionIncome,
    pension_monthly_income: pensionMonthlyIncome,
    pension_payments_per_year: pensionPayments,
    pension_declared_gross_income: pensionDeclaredGross,
    freelance_profit: profit,
    freelance_deductible_expenses: freelance.deductible_expenses,
    freelance_category_contribution: categoryContribution,
    freelance_additional_contributions: freelance.mandatory_contributions,
    freelance_auxiliary_contributions: freelance.auxiliary_contributions,
    freelance_lump_sum_contributions: freelance.lump_sum_contributions,
    freelance_include_category_contributions: freelance.include_category_contributions,
    freelance_include_mandatory_contributions: freelance.include_mandatory_contributions,
    freelance_include_auxiliary_contributions: freelance.include_auxiliary_contributions,
    freelance_include_lump_sum_contributions: freelance.include_lump_sum_contributions,
    include_trade_fee: freelance.include_trade_fee,
    freelance_trade_fee_location: freelance.trade_fee_location,
    freelance_years_active: freelance.years_active,
    freelance_newly_self_employed: freelance.newly_self_employed,
    rental_gross_income: request.rental.gross_income,
    rental_deductible_expenses: request.rental.deductible_expenses,
    investment_amounts: investmentAmounts,
    enfia_due: request.obligations.enfia,
    luxury_due: request.obligations.luxury,
    agricultural_gross_revenue: agricultural.gross_revenue,
    agricultural_deductible_expenses: agricultural.deductible_expenses,
    agricultural_professional_farmer: agricultural.professional_farmer,
    other_taxable_income: otherIncome,
    deductions_donations: request.deductions.donations,
    deductions_medical: request.deductions.medical,
    deductions_education: request.deductions.education,
    deductions_insurance: request.deductions.insurance,
  });
}
