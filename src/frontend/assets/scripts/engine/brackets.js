/**
 * Progressive tax helpers, mirroring calculators/utils.py and the rate-table
 * lookups in config/year_config.py.
 */

import { pySum } from "./pyMath.js";

/** HouseholdRateTable / YouthRateTable dependant lookup on [count, rate] pairs. */
function rateForDependants(table, dependants) {
  for (const [count, rate] of table) {
    if (count === dependants) {
      return rate;
    }
  }
  for (const [count, rate] of table) {
    if (dependants < count) {
      return rate;
    }
  }
  return table[table.length - 1][1];
}

export function householdRate(bracket, dependants) {
  return rateForDependants(bracket.household, dependants);
}

export function youthRate(bracket, band, dependants) {
  const table = bracket.youth[band];
  if (!table) {
    return householdRate(bracket, dependants);
  }
  if (table.dependants.length) {
    return rateForDependants(table.dependants, dependants);
  }
  if (table.rate !== null) {
    return table.rate;
  }
  return householdRate(bracket, dependants);
}

export const isMultiRate = (bracket) => Array.isArray(bracket.household);

/** Base rate of a bracket (MultiRateBracket.rate is the 0-dependant rate). */
export function baseRate(bracket) {
  return isMultiRate(bracket) ? householdRate(bracket, 0) : bracket.rate;
}

/** EmploymentTaxCredit.amount_for_children. */
export function creditForChildren(credit, dependants) {
  if (dependants < 0) {
    return 0;
  }
  const amounts = credit.amounts_by_children;
  for (const [count, amount] of amounts) {
    if (count === dependants) {
      return amount;
    }
  }
  if (!amounts.length) {
    return 0;
  }
  const [maxKey, baseAmount] = amounts[amounts.length - 1];
  if (dependants <= maxKey) {
    return baseAmount;
  }
  return baseAmount + (dependants - maxKey) * credit.incremental_amount_per_child;
}

/** utils.calculate_progressive_tax. */
export function calculateProgressiveTax(amount, brackets) {
  if (amount <= 0) {
    return 0;
  }
  let total = 0;
  let lowerBound = 0;
  for (const bracket of brackets) {
    const upper = bracket.upper;
    const rate = baseRate(bracket);
    if (upper === null || amount < upper) {
      total += (amount - lowerBound) * rate;
      break;
    }
    total += (upper - lowerBound) * rate;
    lowerBound = upper;
  }
  return total;
}

/** utils.allocate_progressive_tax. */
export function allocateProgressiveTax(amounts, brackets, rateResolver) {
  if (!amounts.length) {
    return [];
  }

  const remaining = amounts.map((amount) => (amount > 0 ? amount : 0));
  const taxes = amounts.map(() => 0);

  let totalRemaining = pySum(remaining);
  if (totalRemaining <= 0) {
    return taxes;
  }

  let lowerBound = 0;

  for (const bracket of brackets) {
    const upper = bracket.upper;
    let capacity;
    if (upper === null) {
      capacity = totalRemaining;
    } else {
      capacity = upper - lowerBound;
      if (capacity < 0) {
        capacity = 0;
      }
      capacity = capacity <= totalRemaining ? capacity : totalRemaining;
    }

    if (capacity <= 0) {
      lowerBound = upper !== null ? upper : lowerBound;
      continue;
    }

    const active = [];
    remaining.forEach((value, index) => {
      if (value > 0) {
        active.push(index);
      }
    });
    if (!active.length) {
      break;
    }

    const activeTotal = pySum(active.map((index) => remaining[index]));
    if (activeTotal <= 0) {
      break;
    }

    const allocations = new Map();
    let allocated = 0;

    active.forEach((index, position) => {
      const remainingIncome = remaining[index];
      if (remainingIncome <= 0) {
        return;
      }
      let allocation;
      if (position === active.length - 1) {
        const left = capacity - allocated;
        allocation = left < remainingIncome ? left : remainingIncome;
      } else {
        const share = remainingIncome / activeTotal;
        allocation = capacity * share;
        if (remainingIncome < allocation) {
          allocation = remainingIncome;
        }
        const remainingCapacity = capacity - allocated;
        if (remainingCapacity < allocation) {
          allocation = remainingCapacity;
        }
      }
      if (allocation < 0) {
        allocation = 0;
      }
      allocations.set(index, allocation);
      allocated += allocation;
    });

    let leftover = capacity - allocated;
    if (leftover > 1e-9) {
      for (const index of active) {
        if (leftover <= 1e-9) {
          break;
        }
        const remainingIncome = remaining[index] - (allocations.get(index) ?? 0);
        if (remainingIncome <= 0) {
          continue;
        }
        const extra = remainingIncome < leftover ? remainingIncome : leftover;
        if (extra <= 0) {
          continue;
        }
        allocations.set(index, (allocations.get(index) ?? 0) + extra);
        allocated += extra;
        leftover -= extra;
      }
    }

    for (const [index, allocation] of allocations) {
      if (allocation <= 0) {
        continue;
      }
      const rate = rateResolver(index, bracket);
      taxes[index] += allocation * rate;
      remaining[index] -= allocation;
      if (remaining[index] < 0) {
        remaining[index] = 0;
      }
    }

    totalRemaining -= capacity;
    if (totalRemaining <= 1e-9) {
      break;
    }
    lowerBound = upper !== null ? upper : lowerBound;
  }

  return taxes;
}
