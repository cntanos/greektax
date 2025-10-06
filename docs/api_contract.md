# Tax Calculation API Contract

The tax calculation service accepts JSON payloads describing an individual's
annual financial data and produces a bilingual breakdown of taxes, credits, and
net income per category. Input and output payloads are now expressed with
Pydantic models, meaning that types, default values, and validation rules are
enforced consistently across the stack.

Key implementation entry points:

- Request/response models live in
  [`app/models/api.py`](../src/greektax/backend/app/models/api.py) and mirror the
  shapes described below.
- Calculation orchestration happens inside
  [`app/services/calculation_service.py`](../src/greektax/backend/app/services/calculation_service.py),
  which normalises payloads, applies configuration toggles, and delegates to the
  category calculators.
- Year-specific thresholds and toggles are loaded from YAML through
  [`config/year_config.py`](../src/greektax/backend/config/year_config.py).

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

## Pydantic Models

| Model | Purpose |
| --- | --- |
| `CalculationRequest` | Complete inbound payload accepted by the calculation endpoint. |
| `DependentsInput`, `DemographicsInput`, `EmploymentInput`, `PensionInput`, `FreelanceInput`, `RentalInput`, `AgriculturalIncomeInput`, `OtherIncomeInput`, `ObligationsInput`, `DeductionsInput` | Section-specific request fragments with dedicated normalisation and validation. |
| `CalculationResponse` | Wrapper containing `Summary`, `DetailEntry` items, and `ResponseMeta`. |
| `Summary` & `SummaryLabels` | Aggregate totals and translated display strings. |
| `DeductionBreakdownEntry` | Optional per-deduction credit explanations returned when applicable. |

## Request Body

Every request must be a JSON object that matches the `CalculationRequest`
schema. Unknown top-level or nested keys are rejected (`extra="forbid"`).

### Top-level fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `year` | integer | ✅ | Tax year to evaluate. Must reference an available configuration file. |
| `locale` | string | ❌ | BCP-47 locale code (`"en"` by default, `"el"` supported). Whitespace-only values default to `"en"`. |
| `dependents` | object | ❌ | Household dependent information. Defaults to no dependents. |
| `demographics` | object | ❌ | Taxpayer demographic data used for relief eligibility. Defaults to empty values. |
| `employment` | object | ❌ | Employment income inputs. Defaults to zero amounts. |
| `pension` | object | ❌ | Pension income inputs. Defaults to zero amounts. |
| `freelance` | object | ❌ | Freelance/self-employment inputs. Defaults to zero amounts. |
| `rental` | object | ❌ | Rental income inputs. Defaults to zero amounts. |
| `agricultural` | object | ❌ | Agricultural activity inputs. Defaults to zero amounts. |
| `investment` | object | ❌ | Map of investment category identifiers to non-negative numeric amounts. Defaults to `{}`. |
| `other` | object | ❌ | Miscellaneous taxable income inputs. Defaults to zero amounts. |
| `obligations` | object | ❌ | Flat obligations such as ENFIA and luxury tax. Defaults to zero amounts. |
| `deductions` | object | ❌ | User-entered deduction amounts. Defaults to zero amounts. |
| `toggles` | object | ❌ | Optional boolean feature flags (e.g., presumptive relief opt-in). Defaults to `{}` and is merged with configuration toggles from `YearConfiguration.meta`. |
| `withholding_tax` | number | ❌ | Amount of tax already withheld. Defaults to `0`. Must be non-negative. |

### Dependents

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `children` | integer | ❌ | Defaults to `0`. Must be between `0` and `15` inclusive. |

### Demographics

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `birth_year` | integer | ✅ | Must be between 1901 and 2100. The value cannot exceed the filing year and, for tax years 2025 and 2026, values above 2025 are rejected. Used to derive youth relief automatically. |
| `taxpayer_birth_year` | integer | ❌ | Deprecated alias for `birth_year`. When provided it must match the required `birth_year` value. |
| `small_village` | boolean | ❌ | Defaults to `false`. |
| `new_mother` | boolean | ❌ | Defaults to `false`. |

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

### Sample request payload

```json
{
  "year": 2024,
  "locale": "el",
  "dependents": {"children": 2},
  "demographics": {
    "birth_year": 1998,
    "small_village": true
  },
  "employment": {
    "gross_income": 24000,
    "payments_per_year": 14,
    "employee_contributions": 1500,
    "include_social_contributions": false
  },
  "freelance": {
    "gross_revenue": 12000,
    "deductible_expenses": 4000,
    "include_trade_fee": true,
    "trade_fee_location": "reduced",
    "years_active": 1
  },
  "investment": {"dividends": 800, "interest": 120},
  "obligations": {"enfia": 260},
  "deductions": {"donations": 150, "insurance": 300},
  "toggles": {
    "presumptive_relief": true,
    "tekmiria_reduction": false
  },
  "withholding_tax": 1000
}
```

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

### Error handling scenarios

| Scenario | HTTP status | JSON body |
| --- | --- | --- |
| Missing/invalid JSON | `400 Bad Request` | `{"error": "bad_request", "message": "Request body must be valid JSON"}` (raised by Flask before reaching the service). |
| Pydantic validation failure | `400 Bad Request` | `{"error": "validation_error", "message": "Invalid calculation payload: freelance.trade_fee_location: Invalid trade fee location selection"}`. |
| Non-mapping `toggles` payload | `400 Bad Request` | `{"error": "validation_error", "message": "Invalid calculation payload: toggles: Toggles section must be an object mapping identifiers to booleans"}`. |
| Year configuration missing | `500 Internal Server Error` | Triggered when `load_year_configuration` raises `FileNotFoundError`; deploy new YAML to resolve. |

## Response Body

```
{
  "summary": {
    "income_total": 33000.0,
    "taxable_income": 31200.0,
    "tax_total": 4830.0,
    "net_income": 28170.0,
    "net_monthly_income": 2347.5,
    "effective_tax_rate": 0.1464,
    "average_monthly_tax": 402.5,
    "deductions_entered": 450.0,
    "deductions_applied": 360.0,
    "withholding_tax": 1000.0,
    "balance_due": 3830.0,
    "balance_due_is_refund": false,
    "labels": {
      "income_total": "Total income",
      "taxable_income": "Taxable income",
      "tax_total": "Total taxes",
      "net_income": "Net income",
      "net_monthly_income": "Net income per month",
      "average_monthly_tax": "Average tax per month",
      "effective_tax_rate": "Effective tax rate",
      "deductions_entered": "Deductions entered",
      "deductions_applied": "Deductions applied",
      "withholding_tax": "Withholding tax",
      "balance_due": "Balance due"
    },
    "deductions_breakdown": [
      {
        "type": "donations",
        "label": "Charitable donations",
        "entered": 150.0,
        "eligible": 150.0,
        "credit_rate": 0.1,
        "credit_requested": 15.0,
        "credit_applied": 15.0
      }
    ]
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
    }
  ],
  "meta": {
    "year": 2024,
    "locale": "en",
    "youth_relief_category": "under_25",
    "presumptive_adjustments": [
      "presumptive_income"
    ]
  }
}
```

The response always includes:

- `summary`: Aggregated totals with localized labels, including monthly net income
  and the effective tax rate. When applicable it also surfaces
  `withholding_tax`, `balance_due`, and per-deduction entries in
  `deductions_breakdown`.
- `details`: Per-category breakdowns. Additional fields appear depending on the
  income type (e.g., `monthly_gross_income`, `payments_per_year`, `trade_fee_label`,
  investment `items`). Flat obligations such as ENFIA or luxury taxes are
  returned as simple line items with negative `net_income` values to reflect
  their impact on take-home amounts.
- `meta`: Echoes the tax `year` and the resolved `locale` used for labels.

The orchestration layer in
[`app/services/calculation_service.py`](../src/greektax/backend/app/services/calculation_service.py)
produces this payload after loading the structured year metadata via
[`config/year_config.py`](../src/greektax/backend/config/year_config.py) and the
Pydantic response models highlighted earlier.

All currency values are rounded to two decimals.
