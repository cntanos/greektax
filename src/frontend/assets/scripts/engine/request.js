/**
 * Validation of calculation payloads, mirroring the Pydantic request models
 * in src/greektax/backend/app/models/api.py (lax Python-mode coercion, field
 * validators, error ordering and messages).
 */

import { pyStr, pyTruthy } from "./pyMath.js";

export class EngineError extends Error {}

const NET_INCOME_INPUT_ERROR =
  "Employment net income inputs are no longer supported; provide gross amounts instead";

const BOOL_STRINGS = new Map([
  ["0", false], ["off", false], ["f", false], ["false", false], ["n", false], ["no", false],
  ["1", true], ["on", true], ["t", true], ["true", true], ["y", true], ["yes", true],
]);

const NUMERIC_PATTERN = /^[+-]?(\d+(_\d+)*\.?(\d+(_\d+)*)?|\.\d+(_\d+)*)([eE][+-]?\d+)?$/;
// Pydantic accepts integer strings with an all-zero fraction ("7.00") but not "7.".
const INTEGER_PATTERN = /^[+-]?\d+(_\d+)*(\.0+)?$/;

class FieldError {
  constructor(loc, msg) {
    this.loc = loc;
    this.msg = msg;
  }
}

const isMapping = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

function parseFloatLax(value) {
  if (typeof value === "boolean") {
    return { value: value ? 1 : 0 };
  }
  if (typeof value === "number") {
    return { value };
  }
  if (typeof value === "string") {
    const text = value.trim();
    if (NUMERIC_PATTERN.test(text)) {
      return { value: Number(text.replaceAll("_", "")) };
    }
    if (/^[+-]?(inf|infinity)$/i.test(text)) {
      return { value: text.startsWith("-") ? -Infinity : Infinity };
    }
    if (/^[+-]?nan$/i.test(text)) {
      return { value: Number.NaN };
    }
    return { error: "Input should be a valid number, unable to parse string as a number" };
  }
  return { error: "Input should be a valid number" };
}

function parseIntLax(value) {
  if (typeof value === "boolean") {
    return { value: value ? 1 : 0 };
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      return { error: "Input should be a finite number" };
    }
    if (!Number.isInteger(value)) {
      return { error: "Input should be a valid integer, got a number with a fractional part" };
    }
    // Python ints have no negative zero.
    return { value: value + 0 };
  }
  if (typeof value === "string") {
    const text = value.trim();
    if (INTEGER_PATTERN.test(text)) {
      return { value: Number(text.replaceAll("_", "")) + 0 };
    }
    return { error: "Input should be a valid integer, unable to parse string as an integer" };
  }
  return { error: "Input should be a valid integer" };
}

function parseBoolLax(value) {
  if (typeof value === "boolean") {
    return { value };
  }
  if (typeof value === "number") {
    if (value === 0 || value === 1) {
      return { value: value === 1 };
    }
    // Whole numbers are "uninterpretable"; fractions are not booleans at all.
    return Number.isInteger(value)
      ? { error: "Input should be a valid boolean, unable to interpret input" }
      : { error: "Input should be a valid boolean" };
  }
  if (typeof value === "string") {
    const key = value.trim().toLowerCase();
    if (BOOL_STRINGS.has(key)) {
      return { value: BOOL_STRINGS.get(key) };
    }
    return { error: "Input should be a valid boolean, unable to interpret input" };
  }
  return { error: "Input should be a valid boolean" };
}

function parseStr(value) {
  if (typeof value === "string") {
    return { value };
  }
  return { error: "Input should be a valid string" };
}

const PARSERS = { float: parseFloatLax, int: parseIntLax, bool: parseBoolLax, str: parseStr };

function checkBounds(spec, value) {
  if (spec.ge !== undefined && !(value >= spec.ge)) {
    return `Input should be greater than or equal to ${spec.ge}`;
  }
  if (spec.le !== undefined && !(value <= spec.le)) {
    return `Input should be less than or equal to ${spec.le}`;
  }
  return null;
}

/**
 * Validate ``raw`` against ``model`` and return the parsed object.
 * Errors are pushed onto ``errors`` in Pydantic's order: declared fields
 * first (nested models expanded in place), then unexpected keys.
 */
function validateModel(model, raw, loc, errors) {
  let data = raw;
  if (model.before) {
    data = model.before(data);
  }
  if (!isMapping(data)) {
    errors.push(new FieldError(loc, `Input should be a valid dictionary or instance of ${model.name}`));
    return null;
  }

  const result = {};
  const fieldsSet = new Set();
  const errorCount = errors.length;

  for (const [name, spec] of Object.entries(model.fields)) {
    const fieldLoc = [...loc, name];
    const provided = Object.prototype.hasOwnProperty.call(data, name);
    if (provided) {
      fieldsSet.add(name);
    }
    let value = provided ? data[name] : spec.default;
    if (!provided && spec.model) {
      value = {};
    }
    if (!provided && spec.required) {
      errors.push(new FieldError(fieldLoc, "Field required"));
      continue;
    }
    if (provided && spec.before) {
      try {
        value = spec.before(value);
      } catch (error) {
        if (error instanceof ValueErrorSignal) {
          errors.push(new FieldError(fieldLoc, `Value error, ${error.message}`));
          continue;
        }
        throw error;
      }
    }
    if (spec.model) {
      const nested = validateModel(spec.model, value, fieldLoc, errors);
      if (nested !== null) {
        result[name] = nested;
      }
      continue;
    }
    if (value === null && spec.optional) {
      result[name] = null;
      continue;
    }
    if (!provided && !spec.dict) {
      result[name] = value;
      continue;
    }
    if (spec.dict) {
      if (!isMapping(value)) {
        errors.push(new FieldError(fieldLoc, "Input should be a valid dictionary"));
        continue;
      }
      const parsed = {};
      let failed = false;
      for (const [key, entry] of Object.entries(value)) {
        const outcome = PARSERS[spec.dict](entry);
        if (outcome.error) {
          errors.push(new FieldError([...fieldLoc, key], outcome.error));
          failed = true;
        } else {
          parsed[key] = outcome.value;
        }
      }
      if (failed) {
        continue;
      }
      value = parsed;
    } else {
      const outcome = PARSERS[spec.type](value);
      if (outcome.error) {
        errors.push(new FieldError(fieldLoc, outcome.error));
        continue;
      }
      value = outcome.value;
      const boundsError = checkBounds(spec, value);
      if (boundsError) {
        errors.push(new FieldError(fieldLoc, boundsError));
        continue;
      }
    }
    if (spec.after) {
      try {
        value = spec.after(value);
      } catch (error) {
        if (error instanceof ValueErrorSignal) {
          errors.push(new FieldError(fieldLoc, `Value error, ${error.message}`));
          continue;
        }
        throw error;
      }
    }
    result[name] = value;
  }

  for (const key of Object.keys(data)) {
    if (!Object.prototype.hasOwnProperty.call(model.fields, key)) {
      errors.push(new FieldError([...loc, key], "Extra inputs are not permitted"));
    }
  }

  if (errors.length > errorCount) {
    return null;
  }

  if (model.after) {
    try {
      model.after(result, fieldsSet);
    } catch (error) {
      if (error instanceof ValueErrorSignal) {
        errors.push(new FieldError(loc, `Value error, ${error.message}`));
        return null;
      }
      throw error;
    }
  }
  return result;
}

/** A ValueError raised inside a validator (reported as "Value error, ..."). */
export class ValueErrorSignal extends Error {}

const amount = { type: "float", default: 0, ge: 0 };
const optionalAmount = { type: "float", default: null, ge: 0, optional: true };
const optionalCount = { type: "int", default: null, ge: 0, optional: true };

const FREELANCE_BOOL_DEFAULTS = {
  include_trade_fee: true,
  include_category_contributions: true,
  include_mandatory_contributions: true,
  include_auxiliary_contributions: true,
  include_lump_sum_contributions: true,
  newly_self_employed: false,
};

const freelanceBool = (name) => ({
  type: "bool",
  default: FREELANCE_BOOL_DEFAULTS[name],
  before: (value) => (value === null ? FREELANCE_BOOL_DEFAULTS[name] : pyTruthy(value)),
});

const rejectNetIncome = (value) => {
  if (value !== null && value > 0) {
    throw new ValueErrorSignal(NET_INCOME_INPUT_ERROR);
  }
  return value;
};

const DependentsInput = {
  name: "DependentsInput",
  fields: { children: { type: "int", default: 0, ge: 0, le: 15 } },
};

const DemographicsInput = {
  name: "DemographicsInput",
  fields: {
    taxpayer_birth_year: { type: "int", default: null, ge: 1901, le: 2100, optional: true },
    birth_year: { type: "int", default: null, ge: 1901, le: 2100, optional: true },
    tax_residency_transfer_to_greece: { type: "bool", default: false },
  },
  before(data) {
    if (isMapping(data) && !("birth_year" in data) && "taxpayer_birth_year" in data) {
      return { ...data, birth_year: data.taxpayer_birth_year };
    }
    return data;
  },
  after(model) {
    const birthYear = model.birth_year || model.taxpayer_birth_year;
    if (model.taxpayer_birth_year !== null && model.taxpayer_birth_year !== birthYear) {
      throw new ValueErrorSignal(
        "birth_year and taxpayer_birth_year must match when both are provided",
      );
    }
    model.birth_year = birthYear;
    model.taxpayer_birth_year = birthYear;
  },
};

const EmploymentInput = {
  name: "EmploymentInput",
  fields: {
    gross_income: amount,
    monthly_income: optionalAmount,
    net_income: { ...optionalAmount, after: rejectNetIncome },
    net_monthly_income: { ...optionalAmount, after: rejectNetIncome },
    payments_per_year: optionalCount,
    employee_contributions: amount,
    include_social_contributions: { type: "bool", default: true },
    include_employee_contributions: { type: "bool", default: true },
    include_manual_employee_contributions: { type: "bool", default: true },
    include_employer_contributions: { type: "bool", default: true },
  },
  after(model, fieldsSet) {
    if (fieldsSet.has("include_social_contributions")) {
      const base = Boolean(model.include_social_contributions);
      for (const key of [
        "include_employee_contributions",
        "include_manual_employee_contributions",
        "include_employer_contributions",
      ]) {
        if (!fieldsSet.has(key)) {
          model[key] = base;
        }
      }
    } else {
      model.include_social_contributions =
        Boolean(model.include_employee_contributions) ||
        Boolean(model.include_manual_employee_contributions) ||
        Boolean(model.include_employer_contributions);
    }
  },
};

const PensionInput = {
  name: "PensionInput",
  fields: {
    gross_income: amount,
    monthly_income: optionalAmount,
    payments_per_year: optionalCount,
  },
};

const FreelanceInput = {
  name: "FreelanceInput",
  fields: {
    profit: optionalAmount,
    gross_revenue: amount,
    deductible_expenses: amount,
    efka_category: { type: "str", default: null, optional: true },
    efka_months: optionalCount,
    mandatory_contributions: amount,
    auxiliary_contributions: amount,
    lump_sum_contributions: amount,
    include_trade_fee: freelanceBool("include_trade_fee"),
    include_category_contributions: freelanceBool("include_category_contributions"),
    include_mandatory_contributions: freelanceBool("include_mandatory_contributions"),
    include_auxiliary_contributions: freelanceBool("include_auxiliary_contributions"),
    include_lump_sum_contributions: freelanceBool("include_lump_sum_contributions"),
    trade_fee_location: {
      type: "str",
      default: "standard",
      before(value) {
        if (value === null) {
          return "standard";
        }
        if (typeof value === "string") {
          const normalised = value.trim().toLowerCase();
          if (normalised === "" || normalised === "standard") {
            return "standard";
          }
          if (normalised === "reduced") {
            return "reduced";
          }
        }
        throw new ValueErrorSignal("Invalid trade fee location selection");
      },
    },
    years_active: optionalCount,
    newly_self_employed: freelanceBool("newly_self_employed"),
  },
};

const simpleModel = (name, fields) => ({ name, fields });

const RentalInput = simpleModel("RentalInput", { gross_income: amount, deductible_expenses: amount });
const AgriculturalIncomeInput = simpleModel("AgriculturalIncomeInput", {
  gross_revenue: amount,
  deductible_expenses: amount,
  professional_farmer: { type: "bool", default: false },
});
const OtherIncomeInput = simpleModel("OtherIncomeInput", { taxable_income: amount });
const ObligationsInput = simpleModel("ObligationsInput", { enfia: amount, luxury: amount });
const DeductionsInput = simpleModel("DeductionsInput", {
  donations: amount,
  medical: amount,
  education: amount,
  insurance: amount,
});

const mappingOrEmpty = (message) => (value) => {
  if (value === null) {
    return {};
  }
  if (isMapping(value)) {
    return value;
  }
  // Python raises TypeError here, which Pydantic does not convert.
  throw new EngineError(message);
};

const CalculationRequest = {
  name: "CalculationRequest",
  fields: {
    year: { type: "int", ge: 0, required: true },
    locale: {
      type: "str",
      default: "en",
      before: (value) => (value === null ? "en" : pyStr(value).trim() || "en"),
    },
    dependents: { model: DependentsInput },
    demographics: { model: DemographicsInput },
    employment: { model: EmploymentInput },
    pension: { model: PensionInput },
    freelance: { model: FreelanceInput },
    rental: { model: RentalInput },
    agricultural: { model: AgriculturalIncomeInput },
    investment: {
      dict: "float",
      default: {},
      before: mappingOrEmpty("Investment section must be an object mapping categories to amounts"),
      after(value) {
        for (const [key, entry] of Object.entries(value)) {
          if (entry < 0) {
            throw new ValueErrorSignal(
              `Investment amount for category '${key}' cannot be negative`,
            );
          }
        }
        return value;
      },
    },
    other: { model: OtherIncomeInput },
    obligations: { model: ObligationsInput },
    deductions: { model: DeductionsInput },
    toggles: {
      dict: "bool",
      default: {},
      before: mappingOrEmpty("Toggles section must be an object mapping identifiers to booleans"),
    },
    withholding_tax: amount,
  },
};

/** format_validation_error from models/api.py. */
export function formatValidationErrors(errors) {
  const messages = errors.map(({ loc, msg }) => {
    const message = msg.toLowerCase().includes("greater than or equal to 0")
      ? "value cannot be negative"
      : msg;
    return loc.length ? `${loc.join(".")}: ${message}` : message;
  });
  return `Invalid calculation payload: ${messages.join("; ")}`;
}

/** Validate a payload as calculate_tax does before normalisation. */
export function parseCalculationRequest(payload) {
  if (!isMapping(payload)) {
    throw new EngineError("Payload must be a mapping");
  }
  if (!("year" in payload)) {
    throw new EngineError("Payload must include a tax year");
  }
  const errors = [];
  const request = validateModel(CalculationRequest, payload, [], errors);
  if (errors.length) {
    throw new EngineError(formatValidationErrors(errors));
  }
  return request;
}
