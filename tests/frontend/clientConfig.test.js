import test from "node:test";
import assert from "node:assert/strict";

import {
  getApplicationVersion,
  getDeductionsPayload,
  getInvestmentPayload,
  getYearsPayload,
} from "../../src/frontend/assets/scripts/config/clientConfig.js";

test("years payload lists every bundled year with a default", () => {
  const payload = getYearsPayload();
  const years = payload.years.map((entry) => entry.year);
  assert.ok(years.length > 0);
  assert.equal(payload.default_year, years[years.length - 1]);
});

test("application version is a non-empty string", () => {
  assert.match(getApplicationVersion(), /\S/);
});

test("per-year payloads resolve the requested locale", () => {
  const year = getYearsPayload().default_year;
  assert.equal(getInvestmentPayload(year, "el").locale, "el");
  assert.equal(getDeductionsPayload(year, "en").locale, "en");
});

test("region suffixes and unknown locales fall back like the API", () => {
  const year = getYearsPayload().default_year;
  assert.equal(getInvestmentPayload(year, "EL-gr").locale, "el");
  assert.equal(getInvestmentPayload(year, "fr").locale, "en");
  assert.equal(getDeductionsPayload(year, undefined).locale, "en");
});

test("a year without bundled configuration throws", () => {
  assert.throws(() => getInvestmentPayload(1999, "en"), /No configuration bundled for 1999/);
  assert.throws(() => getDeductionsPayload(1999, "en"), /No configuration bundled for 1999/);
});
