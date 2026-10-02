import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { calculateTax, EngineError } from "../../src/frontend/assets/scripts/engine/calculate.js";

const FIXTURE_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "data",
  "parity",
);

// The fixtures are generated from the Python engine by
// scripts/generate_parity_fixtures.py. Results must match exactly: numbers
// are compared with Object.is, so even 0 versus -0 counts as a difference.
for (const file of readdirSync(FIXTURE_DIR).filter((name) => name.endsWith(".json")).sort()) {
  const cases = JSON.parse(readFileSync(path.join(FIXTURE_DIR, file), "utf8"));

  test(`client engine matches the Python engine for ${file}`, () => {
    const failures = [];
    for (const { name, payload, expected, error } of cases) {
      try {
        const result = calculateTax(payload);
        if (error !== undefined) {
          failures.push(`${name}: expected error "${error}" but got a result`);
          continue;
        }
        assert.deepStrictEqual(result, expected);
      } catch (caught) {
        if (error !== undefined && caught instanceof EngineError) {
          if (caught.message !== error) {
            failures.push(`${name}: error "${caught.message}" instead of "${error}"`);
          }
          continue;
        }
        failures.push(`${name}: ${caught.message.split("\n").slice(0, 12).join("\n")}`);
      }
    }
    assert.equal(failures.length, 0, `${failures.length} of ${cases.length} cases differ:\n${failures.slice(0, 5).join("\n\n")}`);
  });
}
