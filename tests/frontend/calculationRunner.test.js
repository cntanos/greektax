import test from "node:test";
import assert from "node:assert/strict";

import {
  diffResults,
  preloadEngine,
  prepareClientPayload,
  resolveEngineMode,
  runCalculation,
} from "../../src/frontend/assets/scripts/ui/calculationRunner.js";

const docWithMode = (content) => ({
  querySelector: (selector) =>
    selector === 'meta[name="greektax-engine"]' && content !== undefined
      ? { getAttribute: () => content }
      : null,
});

const recordingLogger = () => {
  const calls = { warn: [], info: [] };
  return {
    calls,
    warn: (...args) => calls.warn.push(args),
    info: (...args) => calls.info.push(args),
  };
};

// Shadow comparisons are logged after the result is returned.
const flush = () => new Promise((resolve) => setImmediate(resolve));

const fakeEngine = (calculateTax) => async () => ({ calculateTax, ENGINE_LOCALES: ["el", "en"] });

test("engine mode defaults to server and ignores unknown values", () => {
  assert.equal(resolveEngineMode(docWithMode(undefined)), "server");
  assert.equal(resolveEngineMode(docWithMode("hybrid")), "server");
  assert.equal(resolveEngineMode(docWithMode(" Shadow ")), "shadow");
  assert.equal(resolveEngineMode(docWithMode("client")), "client");
  assert.equal(resolveEngineMode(undefined), "server");
});

test("client payload is JSON-normalised and its locale resolved like the API route", () => {
  const prepared = prepareClientPayload(
    { year: 2026, locale: "EL-gr", missing: undefined },
    "en",
    ["el", "en"],
  );
  assert.deepEqual(prepared, { year: 2026, locale: "el" });
  assert.equal(prepareClientPayload({ year: 2026, locale: "fr" }, "el", ["el", "en"]).locale, "en");
  assert.equal(prepareClientPayload({ year: 2026 }, "el-GR,en;q=0.8", ["el", "en"]).locale, "el");
});

test("diffResults reports differing paths, including signed zero", () => {
  assert.deepEqual(diffResults({ a: 1, b: [1, 2] }, { a: 1, b: [1, 2] }), []);
  const differences = diffResults({ a: 1, b: { c: 0 } }, { a: 2, b: { c: -0 }, d: 3 });
  assert.deepEqual(
    differences.map((entry) => entry.path),
    ["a", "b.c", "d"],
  );
});

test("server mode only calls the server", async () => {
  let engineLoaded = false;
  const result = await runCalculation({
    payload: { year: 2026 },
    mode: "server",
    requestServer: async () => ({ source: "server" }),
    loadEngine: async () => {
      engineLoaded = true;
      return {};
    },
  });
  assert.deepEqual(result, { source: "server" });
  assert.equal(engineLoaded, false);
});

test("client mode never calls the server and surfaces engine errors", async () => {
  const requestServer = async () => assert.fail("server must not be called");
  const result = await runCalculation({
    payload: { year: 2026, locale: "el" },
    mode: "client",
    requestServer,
    loadEngine: fakeEngine((payload) => ({ echoed: payload })),
  });
  assert.deepEqual(result, { echoed: { year: 2026, locale: "el" } });

  await assert.rejects(
    runCalculation({
      payload: { year: 2026 },
      mode: "client",
      requestServer,
      loadEngine: fakeEngine(() => {
        throw new Error("Invalid calculation payload: bogus: Extra inputs are not permitted");
      }),
    }),
    /Extra inputs are not permitted/,
  );
});

test("shadow mode returns the server result and logs nothing alarming when engines agree", async () => {
  const logger = recordingLogger();
  const result = await runCalculation({
    payload: { year: 2026 },
    mode: "shadow",
    requestServer: async () => ({ total: 1 }),
    loadEngine: fakeEngine(() => ({ total: 1 })),
    logger,
  });
  assert.deepEqual(result, { total: 1 });
  await flush();
  assert.equal(logger.calls.warn.length, 0);
  assert.equal(logger.calls.info.length, 1);
});

test("shadow mode warns with the differing paths but still shows the server result", async () => {
  const logger = recordingLogger();
  const result = await runCalculation({
    payload: { year: 2026 },
    mode: "shadow",
    requestServer: async () => ({ summary: { tax_total: 100 } }),
    loadEngine: fakeEngine(() => ({ summary: { tax_total: 101 } })),
    logger,
  });
  assert.deepEqual(result, { summary: { tax_total: 100 } });
  await flush();
  assert.equal(logger.calls.warn.length, 1);
  assert.deepEqual(
    logger.calls.warn[0][1].differences.map((entry) => entry.path),
    ["result.summary.tax_total"],
  );
});

test("shadow mode compares errors and rethrows the server error", async () => {
  const logger = recordingLogger();
  await assert.rejects(
    runCalculation({
      payload: { year: 2026 },
      mode: "shadow",
      requestServer: async () => {
        throw new Error("same message");
      },
      loadEngine: fakeEngine(() => {
        throw new Error("same message");
      }),
      logger,
    }),
    /same message/,
  );
  await flush();
  assert.equal(logger.calls.warn.length, 0);
  assert.equal(logger.calls.info.length, 1);
});

test("shadow mode does not wait for a client engine that never loads", async () => {
  const logger = recordingLogger();
  const result = await runCalculation({
    payload: { year: 2026 },
    mode: "shadow",
    requestServer: async () => ({ total: 1 }),
    loadEngine: () => new Promise(() => {}),
    logger,
  });
  assert.deepEqual(result, { total: 1 });
  await flush();
  assert.equal(logger.calls.warn.length + logger.calls.info.length, 0);
});

test("preloadEngine schedules a download only in shadow and client modes", async () => {
  const scheduled = [];
  const schedule = (task) => scheduled.push(task);
  let loads = 0;
  const loadEngine = async () => {
    loads += 1;
    throw new Error("network down");
  };
  assert.equal(preloadEngine("server", { loadEngine, schedule }), false);
  assert.equal(preloadEngine("shadow", { loadEngine, schedule }), true);
  assert.equal(preloadEngine("client", { loadEngine, schedule }), true);
  assert.equal(scheduled.length, 2);
  scheduled.forEach((task) => task());
  await flush();
  assert.equal(loads, 2);
});
