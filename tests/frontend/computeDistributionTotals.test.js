import { strict as assert } from 'node:assert';
import test from 'node:test';

import { computeDistributionTotals } from '../../src/frontend/assets/scripts/charts/distribution.js';

test('computeDistributionTotals keeps insurance separate from expenses', () => {
  const detail = {
    gross_income: 15000,
    net_income: 6800,
    total_tax: 3200,
    employee_contributions: 2900,
    deductible_contributions: 600,
    deductible_expenses: 1000,
  };

  const { totals, totalValue } = computeDistributionTotals([detail]);

  assert.ok(
    totals.insurance > 0,
    'insurance total should remain positive when contributions exist',
  );
  assert.equal(
    totals.insurance,
    detail.employee_contributions + detail.deductible_contributions,
    'insurance total should equal explicit contributions',
  );
  assert.equal(
    totals.expenses,
    detail.deductible_expenses,
    'expenses should remain isolated in their own slice',
  );
  assert.equal(
    totalValue,
    totals.net_income + totals.taxes + totals.insurance + totals.expenses,
    'total value should match recomputed gross flows',
  );
});
