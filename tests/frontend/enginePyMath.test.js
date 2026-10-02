import test from "node:test";
import assert from "node:assert/strict";

import {
  formatGroupedCurrency,
  formatPercentage,
  pyMax,
  pyMin,
  pyRound,
  pyTruthy,
} from "../../src/frontend/assets/scripts/engine/pyMath.js";

test("pyRound breaks exact binary ties to even, like Python", () => {
  assert.equal(pyRound(0.125, 2), 0.12);
  assert.equal(pyRound(0.375, 2), 0.38);
  assert.equal(pyRound(2.675, 2), 2.67); // 2.675 is stored just below the tie
  assert.equal(pyRound(1.005, 2), 1);
  assert.equal(pyRound(12345.6789, 4), 12345.6789);
});

test("pyRound keeps Python's signed zero", () => {
  assert.ok(Object.is(pyRound(-0.001, 2), -0));
  assert.ok(Object.is(pyRound(-0, 2), -0));
  assert.ok(Object.is(pyRound(0.004, 2), 0));
});

test("pyMin and pyMax keep the first argument on ties, including signed zero", () => {
  assert.ok(Object.is(pyMax(-0, 0), -0));
  assert.ok(Object.is(pyMin(0, -0), 0));
  assert.equal(pyMax(3, 5), 5);
  assert.equal(pyMin(3, 5), 3);
});

test("pyTruthy follows Python bool()", () => {
  for (const value of [null, false, 0, "", [], {}]) {
    assert.equal(pyTruthy(value), false, JSON.stringify(value));
  }
  for (const value of [true, 1, -2, "0", "false", [0], { a: 1 }]) {
    assert.equal(pyTruthy(value), true, JSON.stringify(value));
  }
});

test("number formatting matches Python format specs", () => {
  assert.equal(formatGroupedCurrency(3000), "3,000.00");
  assert.equal(formatGroupedCurrency(1234567.125), "1,234,567.12");
  assert.equal(formatPercentage(0.2), "20%");
  assert.equal(formatPercentage(0.125), "12.50%");
});
