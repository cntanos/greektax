# Tax Calculation API Contract

The tax calculation service accepts JSON payloads describing an individual's
annual financial data and produces a bilingual breakdown of taxes, credits, and
net income per category. Input and output payloads are now expressed with
Pydantic models, meaning that types, default values, and validation rules are
enforced consistently across the stack.

## Endpoints

```
POST /api/v1/calculations
Content-Type: application/json
```

Successful requests return `200 OK` with the calculation payload described
below. Validation issues produce a `400 Bad Request` response with a JSON body
containing `error` and `message` fields. When invalid field values are
detected, the API returns `{"error": "validation_error", "message": "..."}`
where the message lists each failing field and its validation error.

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

Every request must be a JSON object that matches the `CalculationRequest`
schema. Unknown top-level or nested keys are rejected (`extra="forbid"`).

### Top-level fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `year` | integer | ✅ | Tax year to evaluate. Must reference an available configuration file. |
| `locale` | string | ❌ | BCP-47 locale code (`"en"` by default, `"el"` supported). Whitespace-only values default to `"en"`. |
| `dependents` | object | ❌ | Household dependent information. Defaults to no dependents. |
| `employment` | object | ❌ | Employment income inputs. Defaults to zero amounts. |
| `pension` | object | ❌ | Pension income inputs. Defaults to zero amounts. |
| `freelance` | object | ❌ | Freelance/self-employment inputs. Defaults to zero amounts. |
| `rental` | object | ❌ | Rental income inputs. Defaults to zero amounts. |
| `agricultural` | object | ❌ | Agricultural activity inputs. Defaults to zero amounts. |
| `investment` | object | ❌ | Map of investment category identifiers to non-negative numeric amounts. Defaults to `{}`. |
| `other` | object | ❌ | Miscellaneous taxable income inputs. Defaults to zero amounts. |
| `obligations` | object | ❌ | Flat obligations such as ENFIA and luxury tax. Defaults to zero amounts. |
| `deductions` | object | ❌ | User-entered deduction amounts. Defaults to zero amounts. |
| `withholding_tax` | number | ❌ | Amount of tax already withheld. Defaults to `0`. Must be non-negative. |

### Dependents

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `children` | integer | ❌ | Defaults to `0`. Must be ≥ 0. |

### Employment & Pension sections

Each section shares the same structure:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `gross_income` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `monthly_income` | number | ❌ | Defaults to `null`. When provided it must be ≥ 0. |
| `payments_per_year` | integer | ❌ | Defaults to `null`. When provided it must be ≥ 0. |
| `employee_contributions` (employment only) | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `net_income` | number | ❌ | Deprecated field. Positive values are rejected with instructions to provide gross amounts instead. |
| `net_monthly_income` | number | ❌ | Same rules as `net_income`. |

### Freelance

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `profit` | number | ❌ | Optional shortcut; must be ≥ 0 when provided. |
| `gross_revenue` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `deductible_expenses` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `efka_category` | string | ❌ | Optional supplementary metadata. |
| `efka_months` | integer | ❌ | Defaults to `null`. Must be ≥ 0. |
| `mandatory_contributions` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `auxiliary_contributions` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `lump_sum_contributions` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `include_trade_fee` | boolean | ❌ | Defaults to `true` when omitted or `null`. |
| `trade_fee_location` | string | ❌ | Defaults to `"standard"`. Only `"standard"` or `"reduced"` values (case-insensitive) are accepted. |
| `years_active` | integer | ❌ | Defaults to `null`. Must be ≥ 0. |
| `newly_self_employed` | boolean | ❌ | Defaults to `false` when omitted or `null`. |

### Rental

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `gross_income` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `deductible_expenses` | number | ❌ | Defaults to `0`. Must be ≥ 0. |

### Agricultural income

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `gross_revenue` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `deductible_expenses` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `professional_farmer` | boolean | ❌ | Defaults to `false`. |

### Other income

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `taxable_income` | number | ❌ | Defaults to `0`. Must be ≥ 0. |

### Obligations

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `enfia` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `luxury` | number | ❌ | Defaults to `0`. Must be ≥ 0. |

### Deductions

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `donations` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `medical` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `education` | number | ❌ | Defaults to `0`. Must be ≥ 0. |
| `insurance` | number | ❌ | Defaults to `0`. Must be ≥ 0. |

All numeric fields are validated as non-negative floats or integers during
schema parsing. Boolean fields accept JSON booleans as well as typical string or
numeric truthy/falsy representations supported by Pydantic.

### Validation Errors

Validation is performed by the `CalculationRequest` Pydantic model. Any issues
raise a `pydantic.ValidationError`, which is converted into a single
human-readable string via the shared `format_validation_error` helper. The API
returns:

```json
{
  "error": "validation_error",
  "message": "Invalid calculation payload:\\n- employment.gross_income: value cannot be negative\\n- freelance.trade_fee_location: Invalid trade fee location selection"
}
```

Key characteristics of the new validation layer:

- Errors list the dotted path to the offending field followed by Pydantic's
  normalized message.
- Negative numeric inputs are rewritten to `value cannot be negative` for
  consistency.
- Extra keys that are not part of the schema trigger `...: Extra inputs are not
  permitted`.
- Legacy net income fields are accepted only when blank or zero and otherwise
  produce `Employment net income inputs are no longer supported; provide gross
  amounts instead`.

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
      "average_monthly_tax": "Average tax per month",
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
      "gross_income_per_payment": 2142.86,
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
      "category": "enfia",
      "label": "ENFIA property tax",
      "tax": 320.0,
      "total_tax": 320.0,
      "net_income": -320.0
    },
    {
      "category": "luxury",
      "label": "Luxury living tax",
      "tax": 150.0,
      "total_tax": 150.0,
      "net_income": -150.0
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
  such as ENFIA and luxury taxes are returned as simple line items with negative
  `net_income` values to reflect their impact on take-home amounts.
- `meta`: Echoes the tax `year` and the resolved `locale` used for labels.

All currency values are rounded to two decimals.
