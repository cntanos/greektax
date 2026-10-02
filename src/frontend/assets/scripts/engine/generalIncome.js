/**
 * General income (employment, pension, freelance, agricultural, other),
 * mirroring calculators/general_income.py and GeneralIncomeComponent.
 */

import {
  allocateProgressiveTax,
  creditForChildren,
  householdRate,
  isMultiRate,
  youthRate,
} from "./brackets.js";
import {
  formatGroupedCurrency,
  formatPercentage,
  pyMax,
  pyMin,
  pyRound,
  pySum,
} from "./pyMath.js";

const roundCurrency = (value) => pyRound(value, 2);

function component(fields) {
  return {
    contributions: 0,
    deductible_expenses: 0,
    trade_fee: 0,
    tax_before_credit: 0,
    credit: 0,
    tax_after_credit: 0,
    payments_per_year: null,
    monthly_gross_income: null,
    employee_contributions: 0,
    employee_manual_contributions: 0,
    employer_contributions: 0,
    include_employee_contributions: true,
    category_contributions: 0,
    additional_contributions: 0,
    auxiliary_contributions: 0,
    lump_sum_contributions: 0,
    deductions_applied: 0,
    ...fields,
  };
}

function totalTax(item) {
  let total = item.tax_after_credit;
  if (item.category === "freelance") {
    total += item.trade_fee;
  }
  return total;
}

function netIncome(item) {
  let net = item.gross_income - item.tax_after_credit;
  if (item.category === "freelance") {
    net -= item.contributions + item.trade_fee;
  }
  if (
    (item.category === "employment" || item.category === "pension") &&
    item.include_employee_contributions
  ) {
    net -= item.employee_contributions;
  }
  return net;
}

const perPayment = (item, value) =>
  !item.payments_per_year || item.payments_per_year <= 0 ? null : value / item.payments_per_year;

function calculateTradeFee(input, freelance) {
  if (!input.include_trade_fee) {
    return 0;
  }
  if (input.freelance_taxable_income <= 0) {
    return 0;
  }
  const tradeFee = freelance.trade_fee;
  if (tradeFee.fee_sunset) {
    return 0;
  }
  const sunset = tradeFee.sunset;
  if (sunset !== null) {
    const statusKey = (sunset.status_key || "").trim().toLowerCase();
    if (statusKey.endsWith("scheduled")) {
      if (sunset.year === null) {
        return 0;
      }
      if (input.year >= sunset.year - 1) {
        return 0;
      }
    }
  }
  let amount = tradeFee.standard_amount;
  if (input.freelance_trade_fee_location === "reduced" && tradeFee.reduced_amount !== null) {
    amount = tradeFee.reduced_amount;
  }
  if (input.freelance_newly_self_employed) {
    const yearsActive = input.freelance_years_active || 0;
    const reductionYears = tradeFee.newly_self_employed_reduction_years;
    if (reductionYears !== null && yearsActive < reductionYears) {
      amount = tradeFee.reduced_amount !== null ? pyMin(amount, tradeFee.reduced_amount) : 0;
    }
  }
  return amount > 0 ? amount : 0;
}

function buildComponents(input, config) {
  const components = [];

  if (input.has_employment_income) {
    let paymentsPerYear = input.employment_payments_per_year;
    if (!paymentsPerYear || paymentsPerYear <= 0) {
      paymentsPerYear = config.employment.payroll.default;
    }
    let monthlyIncome = input.employment_monthly_income;
    if (monthlyIncome === null && paymentsPerYear) {
      monthlyIncome = input.employment_income / paymentsPerYear;
    }

    const contributions = config.employment.contributions;
    const salaryCap = contributions.monthly_salary_cap;
    let contributionBase = input.employment_income;
    if (salaryCap !== null && salaryCap > 0 && paymentsPerYear && monthlyIncome !== null) {
      contributionBase = pyMin(input.employment_income, salaryCap * paymentsPerYear);
    }

    const includeAuto = input.employment_include_employee_contributions;
    const includeManual = input.employment_include_manual_contributions;
    const includeEmployer = input.employment_include_employer_contributions;
    const employeeRate = contributions.employee_rate;

    let autoEmployee = includeAuto ? contributionBase * employeeRate : 0;
    const employer = includeEmployer ? contributionBase * contributions.employer_rate : 0;
    let manualEmployee = includeManual ? input.employment_manual_contributions : 0;
    const maxEmployee =
      (includeAuto || includeManual) && contributionBase > 0 ? contributionBase * employeeRate : 0;

    let employee = autoEmployee + manualEmployee;
    if (maxEmployee && employee > maxEmployee) {
      let excess = employee - maxEmployee;
      if (manualEmployee > 0) {
        const manualReduction = pyMin(manualEmployee, excess);
        manualEmployee -= manualReduction;
        excess -= manualReduction;
      }
      if (excess > 0 && autoEmployee > 0) {
        autoEmployee -= pyMin(autoEmployee, excess);
      }
      employee = maxEmployee;
    } else if (maxEmployee) {
      employee = pyMin(employee, maxEmployee);
    }

    let taxableIncome = input.employment_income - employee;
    if (taxableIncome < 0) {
      taxableIncome = 0;
    }
    if (input.tax_residency_transfer_to_greece && taxableIncome > 0) {
      taxableIncome *= config.rules.residency_transfer_taxable_share;
    }

    components.push(
      component({
        category: "employment",
        label_key: "details.employment",
        gross_income: input.employment_income,
        taxable_income: taxableIncome,
        credit_eligible: true,
        deductible_expenses: 0,
        employee_contributions: employee,
        employee_manual_contributions: manualEmployee,
        employer_contributions: employer,
        include_employee_contributions: includeAuto || includeManual,
        payments_per_year: input.employment_payments_per_year,
        monthly_gross_income: input.employment_monthly_income,
      }),
    );
  }

  if (input.has_pension_income) {
    components.push(
      component({
        category: "pension",
        label_key: "details.pension",
        gross_income: input.pension_income,
        taxable_income: input.pension_income,
        credit_eligible: true,
        payments_per_year: input.pension_payments_per_year,
        monthly_gross_income: input.pension_monthly_income,
      }),
    );
  }

  if (input.has_freelance_income) {
    components.push(
      component({
        category: "freelance",
        label_key: "details.freelance",
        gross_income: input.freelance_profit,
        taxable_income: input.freelance_taxable_income,
        credit_eligible: true,
        deductible_expenses: input.freelance_deductible_expenses,
        contributions: input.total_freelance_contributions,
        trade_fee: calculateTradeFee(input, config.freelance),
        category_contributions: input.freelance_effective_category_contribution,
        additional_contributions: input.freelance_effective_mandatory_contribution,
        auxiliary_contributions: input.freelance_effective_auxiliary_contribution,
        lump_sum_contributions: input.freelance_effective_lump_sum_contribution,
      }),
    );
  }

  if (input.has_agricultural_income) {
    components.push(
      component({
        category: "agricultural",
        label_key: "details.agricultural",
        gross_income: input.agricultural_gross_revenue,
        taxable_income: input.agricultural_taxable_income,
        credit_eligible: input.qualifies_for_agricultural_tax_credit,
        deductible_expenses: input.agricultural_deductible_expenses,
      }),
    );
  }

  if (input.has_other_income) {
    components.push(
      component({
        category: "other",
        label_key: "details.other",
        gross_income: input.other_taxable_income,
        taxable_income: input.other_taxable_income,
        credit_eligible: false,
      }),
    );
  }

  return components;
}

function applyProgressiveTax(components, input, config) {
  const totalTaxable = pySum(components.map((item) => item.taxable_income));
  let taxesBeforeCredit;

  if (totalTaxable <= 0) {
    taxesBeforeCredit = components.map(() => 0);
  } else {
    const dependants = input.children > 0 ? input.children : 0;
    const youthCategory = input.youth_rate_category;
    const youthCategories = new Set(config.rules.youth_relief_categories);
    const resolveRate = (index, bracket) => {
      const item = components[index];
      if (isMultiRate(bracket)) {
        if (youthCategories.has(item.category) && youthCategory && youthCategory in bracket.youth) {
          return youthRate(bracket, youthCategory, dependants);
        }
        return householdRate(bracket, dependants);
      }
      return bracket.rate;
    };
    taxesBeforeCredit = allocateProgressiveTax(
      components.map((item) => item.taxable_income),
      config.employment.brackets,
      resolveRate,
    );
  }

  // Article 16 ΚΦΕ: one credit, reduced above a taxable-income threshold, that
  // can only offset the tax on the credit categories (salaries, pensions and
  // qualifying agricultural income), shared in proportion to that tax.
  const salaryRules = config.rules.salary_credit;
  const salaryCategories = new Set(salaryRules.income_categories);

  components.forEach((item, index) => {
    item.tax_before_credit = taxesBeforeCredit[index];
  });

  const eligible = components.filter(
    (item) => item.credit_eligible && salaryCategories.has(item.category),
  );

  const creditIncome = pySum(eligible.map((item) => item.taxable_income));
  let creditReduction = 0;
  if (creditIncome > salaryRules.reduction_threshold) {
    creditReduction =
      ((creditIncome - salaryRules.reduction_threshold) / salaryRules.reduction_step) *
      salaryRules.reduction_per_step;
  }

  let creditRequested = 0;
  if (eligible.length) {
    const taxCredit = config.employment.tax_credit;
    creditRequested = creditForChildren(taxCredit, input.children);
    const exemptFrom = taxCredit.income_reduction_exempt_from_dependants;
    const exempt = exemptFrom !== null && input.children >= exemptFrom;
    if (creditReduction > 0 && !exempt) {
      creditRequested = pyMax(creditRequested - creditReduction, 0);
    }
  }

  const eligibleTax = pySum(eligible.map((item) => item.tax_before_credit));
  const creditApplied = pyMin(creditRequested, eligibleTax);

  for (const item of components) {
    if (eligible.includes(item) && eligibleTax > 0) {
      item.credit = creditApplied * (item.tax_before_credit / eligibleTax);
    } else {
      item.credit = 0;
    }
    item.tax_after_credit = pyMax(item.tax_before_credit - item.credit, 0);
  }
}

function applyDeductionCredits(input, components, translate, rules) {
  const eligibleComponents = components.filter((item) => item.credit_eligible);
  const availableTax = pySum(eligibleComponents.map((item) => item.tax_after_credit));
  const incomeForThresholds = pySum(eligibleComponents.map((item) => item.gross_income));

  const breakdown = [];
  const append = (type, [entered, eligible, rate], requested, note = null) => {
    breakdown.push({
      type,
      label: translate(`forms.deductions.${type}`),
      entered,
      eligible,
      credit_rate: rate,
      credit_requested: requested,
      credit_applied: 0,
      notes: note,
    });
  };

  const donationsConfig = rules.donations;
  const donations = pyMax(input.deductions_donations, 0);
  if (donations > 0) {
    let eligible;
    let note = null;
    if (donations <= donationsConfig.min_total_amount) {
      eligible = 0;
      note =
        "Donations qualify only when the year's total exceeds " +
        `€${formatGroupedCurrency(donationsConfig.min_total_amount)}.`;
    } else if (incomeForThresholds > 0) {
      const capRate = donationsConfig.income_cap_rate;
      const incomeCap = capRate !== null ? incomeForThresholds * capRate : null;
      eligible = incomeCap !== null ? pyMin(donations, incomeCap) : donations;
      if (incomeCap !== null && donations > incomeCap) {
        note =
          "Only donations up to " +
          `${formatPercentage(capRate)} of eligible income qualify for the ` +
          `${formatPercentage(donationsConfig.credit_rate)} credit.`;
      }
    } else {
      eligible = 0;
      note = "Donations cannot generate a credit without taxable income.";
    }
    append("donations", [donations, eligible, donationsConfig.credit_rate], eligible * donationsConfig.credit_rate, note);
  }

  const medicalConfig = rules.medical;
  const medical = pyMax(input.deductions_medical, 0);
  if (medical > 0) {
    let eligibleExpense;
    let note = null;
    if (incomeForThresholds > 0) {
      const threshold = incomeForThresholds * medicalConfig.income_threshold_rate;
      eligibleExpense = pyMax(medical - threshold, 0);
      if (medical <= threshold) {
        note =
          "Medical expenses must exceed " +
          `${formatPercentage(medicalConfig.income_threshold_rate)} of income before a credit is granted.`;
      }
    } else {
      eligibleExpense = 0;
      note =
        "Medical credits require taxable income to satisfy the " +
        `${formatPercentage(medicalConfig.income_threshold_rate)} threshold.`;
    }
    let requested = eligibleExpense * medicalConfig.credit_rate;
    if (requested > medicalConfig.max_credit) {
      requested = medicalConfig.max_credit;
      const extraNote =
        "Medical expense credits are capped at " +
        `€${formatGroupedCurrency(medicalConfig.max_credit)} per taxpayer.`;
      note = note ? `${note} ${extraNote}`.trim() : extraNote;
    }
    append("medical", [medical, eligibleExpense, medicalConfig.credit_rate], requested, note);
  }

  const totalRequested = pySum(breakdown.map((item) => item.credit_requested));
  if (totalRequested <= 0) {
    return [0, breakdown];
  }

  let scalingFactor = 1;
  if (totalRequested > availableTax) {
    scalingFactor = totalRequested > 0 ? availableTax / totalRequested : 0;
    const limitation = "Credits were limited by the remaining tax liability.";
    for (const item of breakdown) {
      item.notes = item.notes ? `${item.notes} ${limitation}`.trim() : limitation;
    }
  }

  let totalApplied = 0;
  for (const item of breakdown) {
    const applied = item.credit_requested * scalingFactor;
    item.credit_applied = applied;
    totalApplied += applied;
  }

  if (totalApplied <= 0 || availableTax <= 0) {
    return [0, breakdown];
  }

  for (const item of eligibleComponents) {
    const share = availableTax > 0 ? item.tax_after_credit / availableTax : 0;
    const creditShare = totalApplied * share;
    if (creditShare <= 0) {
      continue;
    }
    item.deductions_applied = creditShare;
    item.tax_after_credit = pyMax(item.tax_after_credit - creditShare, 0);
  }

  return [totalApplied, breakdown];
}

function detailFromComponent(item, translate) {
  const grossIncome = roundCurrency(item.gross_income);
  const taxableIncome = roundCurrency(item.taxable_income);
  const total = roundCurrency(totalTax(item));
  const net = roundCurrency(netIncome(item));

  const detail = {
    category: item.category,
    label: translate(item.label_key),
    gross_income: grossIncome,
    taxable_income: taxableIncome,
    tax: roundCurrency(item.tax_after_credit),
    total_tax: total,
    net_income: net,
  };

  if (item.deductible_expenses) {
    detail.deductible_expenses = roundCurrency(item.deductible_expenses);
  }
  if (item.credit_eligible) {
    detail.tax_before_credits = roundCurrency(item.tax_before_credit);
    detail.credits = roundCurrency(item.credit);
  }

  if (item.category === "employment" || item.category === "pension") {
    if (item.employee_contributions) {
      detail.employee_contributions = roundCurrency(item.employee_contributions);
      if (item.employee_manual_contributions) {
        detail.employee_contributions_manual = roundCurrency(item.employee_manual_contributions);
      }
      if (item.payments_per_year) {
        detail.employee_contributions_per_payment = roundCurrency(
          item.employee_contributions / item.payments_per_year,
        );
      }
    }
    if (item.employer_contributions) {
      detail.employer_contributions = roundCurrency(item.employer_contributions);
      if (item.payments_per_year) {
        detail.employer_contributions_per_payment = roundCurrency(
          item.employer_contributions / item.payments_per_year,
        );
      }
    }
    if (item.category === "employment") {
      const employerCost = item.gross_income + item.employer_contributions;
      detail.employer_cost = roundCurrency(employerCost);
      const employerCostPerPayment = perPayment(item, employerCost);
      if (employerCostPerPayment !== null) {
        detail.employer_cost_per_payment = roundCurrency(employerCostPerPayment);
      }
    }
  }

  if (item.category === "freelance") {
    detail.deductible_contributions = roundCurrency(item.contributions);
    detail.trade_fee = roundCurrency(item.trade_fee);
    if (item.trade_fee) {
      detail.trade_fee_label = translate("details.trade_fee");
    }
    for (const field of [
      "category_contributions",
      "additional_contributions",
      "auxiliary_contributions",
      "lump_sum_contributions",
    ]) {
      if (item[field]) {
        detail[field] = roundCurrency(item[field]);
      }
    }
  }

  if (item.monthly_gross_income !== null) {
    detail.monthly_gross_income = roundCurrency(item.monthly_gross_income);
  }
  if (item.payments_per_year) {
    detail.payments_per_year = item.payments_per_year;
    const grossPerPayment = perPayment(item, item.gross_income);
    if (grossPerPayment !== null) {
      detail.gross_income_per_payment = roundCurrency(grossPerPayment);
    }
    const netPerPayment = perPayment(item, netIncome(item));
    if (netPerPayment !== null) {
      detail.net_income_per_payment = roundCurrency(netPerPayment);
    }
  }

  if (item.deductions_applied) {
    detail.deductions_applied = roundCurrency(item.deductions_applied);
  }

  return { detail, grossIncome, taxableIncome, total, net };
}

/** calculate_general_income_details. */
export function calculateGeneralIncome(input, config, translate) {
  const components = buildComponents(input, config);
  const totals = { income: 0, tax: 0, net: 0, taxable: 0 };
  if (!components.length) {
    return { details: [], deductionsApplied: 0, totals, breakdown: [] };
  }

  applyProgressiveTax(components, input, config);
  const [deductionsApplied, breakdown] = applyDeductionCredits(
    input,
    components,
    translate,
    config.deductions,
  );

  const details = [];
  for (const item of components) {
    const { detail, grossIncome, taxableIncome, total, net } = detailFromComponent(item, translate);
    details.push(detail);
    totals.income += grossIncome;
    totals.tax += total;
    totals.net += net;
    totals.taxable += taxableIncome;
  }

  return { details, deductionsApplied, totals, breakdown };
}
