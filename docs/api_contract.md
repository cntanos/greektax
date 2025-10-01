# Tax Calculation API Contract

The tax calculation service accepts JSON payloads describing an individual's
annual financial data and produces a bilingual breakdown of taxes, credits, and
net income per category.

## Endpoints

```
POST /api/v1/calculations
Content-Type: application/json
```

Successful requests return `200 OK` with the calculation payload described
below. Validation issues produce a `400 Bad Request` response with a JSON body
containing `error` and `message` fields. When invalid field values are
detected, the API returns `{"error": "validation_error", "message": "..."}`.

Metadata endpoints support the front-end in building dynamic forms:

```
GET /api/v1/config/years
GET /api/v1/config/<year>/investment-categories?locale=<locale>
GET /api/v1/config/<year>/deductions?locale=<locale>
```

The first returns all configured tax years plus a suggested default. The second
exposes investment income categories (identifier, rate, locale-aware label) for
the requested year. The third surfaces deduction hints for the UI, returning the
deduction identifier, the applicable income categories, the translated display
label and description, as well as validation metadata (e.g., minimum, maximum,
or numeric type) to apply on the client.

## Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `year` | integer | ✅ | Tax year to evaluate. Must match an available configuration file. |
| `locale` | string | ❌ | BCP-47 locale code (`"en"` by default, `"el"` supported). |
| `dependents.children` | integer | ❌ | Number of dependant children. Used to derive employment/pension credits. |
| `employment.gross_income` | number | ❌ | Annual gross salary subject to the progressive employment scale. |
| `employment.monthly_income` | number | ❌ | Monthly gross salary (optional). When provided it is multiplied by `employment.payments_per_year`. |
| `employment.payments_per_year` | integer | ❌ | Salary payments per year (e.g. 12 or 14). Defaults to 14 when paired with a monthly input. |
| `pension.gross_income` | number | ❌ | Annual pension income. Shares the employment scale and credits. |
| `freelance.profit` | number | ❌ | Declared freelance profit. Optional alternative: provide `gross_revenue` and `deductible_expenses`. |
| `freelance.gross_revenue` | number | ❌ | Total freelance revenue (used if `profit` omitted). |
| `freelance.deductible_expenses` | number | ❌ | Deductible business expenses. |
| `freelance.mandatory_contributions` | number | ❌ | Social security contributions deducted from profit. |
| `freelance.include_trade_fee` | boolean | ❌ | Include the business activity fee (defaults to `true`). |
| `rental.gross_income` | number | ❌ | Rental revenue for the year. |
| `rental.deductible_expenses` | number | ❌ | Deductible rental expenses. |
| `investment.*` | number | ❌ | Amounts for each configured investment category (e.g. `dividends`, `interest`, `capital_gains`, `royalties`). |
| `obligations.vat` | number | ❌ | Value Added Tax due for the year. Included in totals without further calculation. |
| `obligations.enfia` | number | ❌ | ENFIA property tax amount to include in the summary. |
| `obligations.luxury` | number | ❌ | Luxury living tax amount for high-value assets. Added directly to the summary. |

All numeric fields must be non-negative. Boolean fields accept `true`, `false`,
and equivalent string toggles (`"yes"`, `"no"`, `"1"`, `"0"`, etc.). Missing
sections default to zero values.

### Validation Errors

Invalid inputs raise `ValueError` with a descriptive message referencing the
problematic field (for example, `"Field 'rental.gross_income' must be numeric"`).
API layers should translate these exceptions into `400 Bad Request` responses.

## Response Body

```
{
  "summary": {
    "income_total": 33000.0,
    "tax_total": 4830.0,
    "net_income": 28170.0,
    "net_monthly_income": 2347.5,
    "effective_tax_rate": 0.1464,
    "labels": {
      "income_total": "Total income",
      "tax_total": "Total taxes",
      "net_income": "Net income",
      "net_monthly_income": "Net income per month",
      "effective_tax_rate": "Effective tax rate"
    }
  },
  "details": [
    {
      "category": "employment",
      "label": "Employment income",
      "gross_income": 30000.0,
      "monthly_gross_income": 2142.86,
      "payments_per_year": 14,
      "taxable_income": 30000.0,
      "tax_before_credits": 5900.0,
      "credits": 810.0,
      "tax": 5090.0,
      "total_tax": 5090.0,
      "net_income": 24910.0,
      "net_income_per_payment": 1786.43
    },
    {
      "category": "freelance",
      "label": "Freelance income",
      "gross_income": 10000.0,
      "deductible_contributions": 2500.0,
      "taxable_income": 7500.0,
      "tax": 900.0,
      "trade_fee": 650.0,
      "trade_fee_label": "Business activity fee",
      "total_tax": 1550.0,
      "net_income": 5950.0
    },
    {
      "category": "investment",
      "label": "Investment income",
      "gross_income": 3500.0,
      "tax": 425.0,
      "total_tax": 425.0,
      "net_income": 3075.0,
      "items": [
        {
          "type": "dividends",
          "label": "Dividends",
          "amount": 1000.0,
          "rate": 0.05,
          "tax": 50.0
        }
      ]
    },
    {
      "category": "vat",
      "label": "Value Added Tax",
      "tax": 600.0,
      "total_tax": 600.0,
      "net_income": -600.0
    },
    {
      "category": "enfia",
      "label": "ENFIA property tax",
      "tax": 320.0,
      "total_tax": 320.0,
      "net_income": -320.0
    }
  ],
  "meta": {
    "year": 2024,
    "locale": "en"
  }
}
```

The response always includes:

- `summary`: Aggregated totals with localized labels, including monthly net income
  and the effective tax rate.
- `details`: Per-category breakdowns. Additional fields appear depending on the
  income type (e.g., `monthly_gross_income`, `payments_per_year`, `trade_fee_label`,
  investment `items`). Flat obligations
  such as VAT and ENFIA are returned as simple line items with negative
  `net_income` values to reflect their impact on take-home amounts.
- `meta`: Echoes the tax `year` and the resolved `locale` used for labels.

All currency values are rounded to two decimals.
