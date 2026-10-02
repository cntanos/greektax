/**
 * Numeric helpers that reproduce Python semantics exactly.
 *
 * The engine must match the Python implementation to the last digit, so these
 * mirror CPython where JavaScript differs: rounding, min/max tie handling
 * (including signed zero), truthiness, and number formatting.
 */

const view = new DataView(new ArrayBuffer(8));

/**
 * Python's round(value, ndigits) for ndigits >= 1.
 *
 * CPython rounds the exact binary value of the float to ndigits decimals,
 * breaking exact ties to even, then returns the nearest float. JavaScript's
 * toFixed and Math.round(x * 10 ** n) differ on ties such as 0.125.
 */
export function pyRound(value, ndigits) {
  if (!Number.isFinite(value) || value === 0) {
    return value;
  }

  view.setFloat64(0, value);
  const high = view.getUint32(0);
  const low = view.getUint32(4);
  const negative = high >>> 31 === 1;
  const exponentBits = (high >>> 20) & 0x7ff;
  let mantissa = (BigInt(high & 0xfffff) << 32n) | BigInt(low);
  let exponent;
  if (exponentBits === 0) {
    exponent = -1074;
  } else {
    mantissa |= 1n << 52n;
    exponent = exponentBits - 1075;
  }

  // |value| == mantissa * 2 ** exponent; integers are already exact.
  if (exponent >= 0) {
    return value;
  }

  const shift = BigInt(-exponent);
  const scaled = mantissa * 10n ** BigInt(ndigits);
  let quotient = scaled >> shift;
  const remainder = scaled - (quotient << shift);
  const half = 1n << (shift - 1n);
  if (remainder > half || (remainder === half && (quotient & 1n) === 1n)) {
    quotient += 1n;
  }

  const digits = quotient.toString().padStart(ndigits + 1, "0");
  const magnitude = Number(`${digits.slice(0, -ndigits)}.${digits.slice(-ndigits)}`);
  return negative ? -magnitude : magnitude;
}

/** Python min(a, b): the first argument wins unless the second is smaller. */
export function pyMin(first, second) {
  return second < first ? second : first;
}

/** Python max(a, b): the first argument wins unless the second is larger. */
export function pyMax(first, second) {
  return second > first ? second : first;
}

/** Python max(iterable) over a non-empty array. */
export function pyMaxOf(values) {
  return values.reduce((best, value) => pyMax(best, value));
}

/** Python sum(iterable) over floats (left-to-right, as in CPython 3.11). */
export function pySum(values) {
  let total = 0;
  for (const value of values) {
    total += value;
  }
  return total;
}

/** Python bool(value) for JSON-compatible values. */
export function pyTruthy(value) {
  if (value === null || value === undefined || value === false) {
    return false;
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  if (typeof value === "string") {
    return value.length > 0;
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  if (typeof value === "object") {
    return Object.keys(value).length > 0;
  }
  return Boolean(value);
}

/** Python str(value) for JSON-compatible scalars. */
export function pyStr(value) {
  if (value === true) {
    return "True";
  }
  if (value === false) {
    return "False";
  }
  if (value === null || value === undefined) {
    return "None";
  }
  return String(value);
}

/** Python f"{value:.2f}". */
function fixed2(value) {
  return pyRound(value, 2).toFixed(2);
}

/** Python f"{value:,.2f}" (comma thousands separators). */
export function formatGroupedCurrency(value) {
  const text = fixed2(value);
  const negative = text.startsWith("-");
  const [whole, fraction] = (negative ? text.slice(1) : text).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}${grouped}.${fraction}`;
}

/** utils.format_percentage: "20%" for whole percentages, else "12.50%". */
export function formatPercentage(value) {
  const percentage = value * 100;
  if (Math.trunc(percentage) === percentage) {
    return `${Math.trunc(percentage)}%`;
  }
  return `${fixed2(percentage)}%`;
}
