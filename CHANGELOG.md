# Changelog

## Unreleased

### Security

- `index.html` now carries a Content-Security-Policy: scripts only from the site and the pinned Plotly build, no network requests, no form submissions, no `eval`.

### Fixes

- "Remember my entries" restores the saved entries after a reload again. At start-up the empty form was saved over them before they could be restored.

### Calculation corrections

Sources for each rule are in [`docs/reference/tax_rules_2025_2026.md`](docs/reference/tax_rules_2025_2026.md).

- Professional farmers pay 0% on the first 20,000 of agricultural profit from tax year 2026 (Article 4 of Law 5355/2026). Example: no children, 30,000 of profit, tax 2,183 instead of 5,083.
- Agricultural profit is taxed on the scale on its own in every year (Art. 29(3) ΚΦΕ) instead of being added to salaries, pensions and business profit. People with farm income next to other income pay less than before, e.g. salary 20,000 plus farm profit 10,000: 3,183 instead of 4,883.
- The tax residency transfer exemption (Art. 5Γ ΚΦΕ) now also halves taxable freelance profit, not only salary. Example: freelance profit 40,000 in 2026 with the box ticked, tax 2,900 instead of 8,900.
- The single "Tax residency transfer to Greece" box is replaced by one box in the salary section and one in the freelance section, because AADE admits each income category to Article 5Γ separately. A saved tick on the old box is not carried over.
- Tax reduction phase-out (Art. 16(2) ΚΦΕ) now uses taxable salary/pension income instead of gross income: employee contributions and the Article 5Γ exemption are deducted first. Employees above 12,000 pay less tax than before.
- Pensions get the Article 16 tax reduction again in 2025 and 2026 (pensioners were overcharged by up to the full reduction, e.g. 777).
- Professional farmers get the reduction on agricultural income in 2025 and 2026, phased out above 12,000 like salaries; farmers without that status do not get it in any year.
- The reduction can no longer offset tax on freelance or other income.
- 2025 has no youth rates; results no longer carry a youth-relief tag for 2025.
- Donations earn the 20% credit only when they exceed 100 in the year, and count up to 5% (not 10%) of taxable income.
- The education and insurance-premium credits were removed: neither exists in Greek law since 2014.
- Freelance EFKA contributions use the official 2025 and 2026 amounts (e-EFKA circular 6/2026 for 2026); engineers use the general main classes plus their auxiliary and lump-sum classes.
- 2026 maximum insurable monthly earnings for employees: 7,761.94.

### Client-only site

- Calculations run in the browser; no input is sent anywhere. The Flask API, the PythonAnywhere deployment and its workflow were removed. The Python engine stays as the reference that the JavaScript engine is tested against.
