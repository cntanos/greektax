# Tax Calculation API Contract

The tax calculation service accepts JSON payloads describing an individual's
annual financial data and produces a bilingual breakdown of taxes, credits, and
net income per category.

## Endpoint

```
POST /api/v1/calculations
Content-Type: application/json
```

Successful requests return `200 OK` with the calculation payload described
below. Validation issues produce a `400 Bad Request` response with a JSON body
containing `error` and `message` fields. When invalid field values are
detected, the API returns `{"error": "validation_error", "message": "..."}`.

## Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `year` | integer | ✅ | Tax year to evaluate. Must match an available configuration file. |
| `locale` | string | ❌ | BCP-47 locale code (`"en"` by default, `"el"` supported). |
| `dependents.children` | integer | ❌ | Number of dependant children. Used to derive employment/pension credits. |
| `employment.gross_income` | number | ❌ | Annual gross salary subject to the progressive employment scale. |
| `pension.gross_income` | number | ❌ | Annual pension income. Shares the employment scale and credits. |
| `freelance.profit` | number | ❌ | Declared freelance profit. Optional alternative: provide `gross_revenue` and `deductible_expenses`. |
| `freelance.gross_revenue` | number | ❌ | Total freelance revenue (used if `profit` omitted). |
| `freelance.deductible_expenses` | number | ❌ | Deductible business expenses. |
| `freelance.mandatory_contributions` | number | ❌ | Social security contributions deducted from profit. |
| `freelance.include_trade_fee` | boolean | ❌ | Include the business activity fee (defaults to `true`). |
| `rental.gross_income` | number | ❌ | Rental revenue for the year. |
| `rental.deductible_expenses` | number | ❌ | Deductible rental expenses. |
| `investment.*` | number | ❌ | Amounts for each configured investment category (e.g. `dividends`, `interest`, `capital_gains`, `royalties`). |

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
    "tax_total": 3910.0,
    "net_income": 29090.0,
    "labels": {
      "income_total": "Total income",
      "tax_total": "Total taxes",
      "net_income": "Net income"
    }
  },
  "details": [
    {
      "category": "employment",
      "label": "Employment income",
      "gross_income": 30000.0,
      "taxable_income": 30000.0,
      "tax_before_credits": 5900.0,
      "credits": 810.0,
      "tax": 5090.0,
      "total_tax": 5090.0,
      "net_income": 24910.0
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
    }
  ],
  "meta": {
    "year": 2024,
    "locale": "en"
  }
}
```

The response always includes:

- `summary`: Aggregated totals with localized labels.
- `details`: Per-category breakdowns. Additional fields appear depending on the
  income type (e.g., `trade_fee_label`, investment `items`).
- `meta`: Echoes the tax `year` and the resolved `locale` used for labels.

All currency values are rounded to two decimals.
