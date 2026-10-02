import test from "node:test";
import assert from "node:assert/strict";

import {
  preloadEngine,
  prepareClientPayload,
  runCalculation,
} from "../../src/frontend/assets/scripts/ui/calculationRunner.js";

test("client payload is JSON-normalised and its locale resolved", () => {
  const prepared = prepareClientPayload(
    { year: 2026, locale: "EL-gr", missing: undefined },
    "en",
    ["el", "en"],
  );
  assert.deepEqual(prepared, { year: 2026, locale: "el" });
  assert.equal(prepareClientPayload({ year: 2026, locale: "fr" }, "el", ["el", "en"]).locale, "en");
  assert.equal(prepareClientPayload({ year: 2026 }, "el-GR,en;q=0.8", ["el", "en"]).locale, "el");
});

test("runCalculation returns the engine result in the requested locale", async () => {
  const result = await runCalculation(
    { year: 2026, employment: { gross_income: 30000 } },
    "el",
  );
  assert.equal(result.meta.year, 2026);
  assert.equal(result.meta.locale, "el");
  assert.equal(result.summary.labels.income_total, "Συνολικό εισόδημα");
  assert.ok(result.summary.tax_total > 0);
});

test("runCalculation rejects with the validation message to show", async () => {
  await assert.rejects(
    runCalculation({ year: 2026, employment: { gross_income: -1 } }, "en"),
    /cannot be negative/,
  );
});

test("runCalculation reports an engine that fails to load", async () => {
  await assert.rejects(
    runCalculation({ year: 2026 }, "en", async () => {
      throw new Error("Failed to fetch dynamically imported module");
    }),
    /Failed to fetch/,
  );
});

test("preloadEngine loads the engine when scheduled and ignores a failure", async () => {
  const scheduled = [];
  let loads = 0;
  preloadEngine({
    schedule: (task) => scheduled.push(task),
    loadEngine: async () => {
      loads += 1;
      throw new Error("offline");
    },
  });
  assert.equal(loads, 0);
  scheduled.forEach((task) => task());
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(loads, 1);
});
