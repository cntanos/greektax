# Changelog

## Unreleased

### Security

- `index.html` now carries a Content-Security-Policy: scripts only from the site and the pinned Plotly build, no network requests, no form submissions, no `eval`.

### Calculation corrections

Sources for each rule are in [`docs/reference/tax_rules_2025_2026.md`](docs/reference/tax_rules_2025_2026.md).

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
