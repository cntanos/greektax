import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function loadComputeDistributionTotals() {
  const sourcePath = resolve(
    __dirname,
    '../../src/frontend/assets/scripts/main.js',
  );
  const source = readFileSync(sourcePath, 'utf8');
  const snippetMatch = source.match(
    /const DISTRIBUTION_EXPENSE_FIELDS[\s\S]*?function computeDistributionTotals[\s\S]*?return { totals, totalValue };\n}/,
  );
  if (!snippetMatch) {
    throw new Error('Unable to load computeDistributionTotals from main.js');
  }
  const factory = new Function(`${snippetMatch[0]}; return computeDistributionTotals;`);
  return factory();
}

test('computeDistributionTotals keeps insurance separate from expenses', () => {
  const computeDistributionTotals = loadComputeDistributionTotals();
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
