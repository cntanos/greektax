// Verifies the opt-in persistence contract: with the "Remember my entries"
// checkbox unchecked, the calculator never writes to localStorage; with it
// checked, the existing snapshot-and-restore flow works as before.

import { strict as assert } from "node:assert";
import test from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";

let JSDOM;
try {
  const jsdomPkg = await import("jsdom");
  JSDOM = jsdomPkg.default.JSDOM;
} catch (e) {
  // jsdom is an optional dev dependency installed locally via
  // `npm install --no-save jsdom`. Skip these tests in environments
  // (e.g. CI runs without `npm install`) where it is unavailable.
}

const condTest = JSDOM
  ? test
  : (name, fn) => test(name, { skip: "jsdom is not installed" }, fn);

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const FRONTEND_DIR = resolve(__dirname, "../../src/frontend");
const APP_MODULE = pathToFileURL(
  resolve(FRONTEND_DIR, "assets/scripts/ui/app.js")
).href;

const CALCULATOR_KEY = "greektax.calculator.v1";
const OPTIN_KEY = "greektax.calculator.persist-optin.v1";

function loadHtmlSkeleton() {
  return readFileSync(resolve(FRONTEND_DIR, "index.html"), "utf8").replace(
    /<script\s+type="module"[^>]*><\/script>/g,
    ""
  );
}

function installDomGlobals(dom) {
  const { window } = dom;
  const keys = new Set([
    "window",
    "document",
    "localStorage",
    "sessionStorage",
    "fetch",
    "Element",
    "Node",
    "Event",
    "CustomEvent",
    "Headers",
  ]);
  for (const k of Object.getOwnPropertyNames(window)) {
    if (/^(HTML|SVG)[A-Z]/.test(k)) keys.add(k);
  }
  for (const k of keys) {
    try {
      Object.defineProperty(globalThis, k, {
        value: k === "window" ? window : window[k],
        configurable: true,
        writable: true,
      });
    } catch (e) {
      /* skip non-overridable globals */
    }
  }
  globalThis.requestAnimationFrame = (cb) => window.setTimeout(cb, 0);
  globalThis.cancelAnimationFrame = (id) => window.clearTimeout(id);
  window.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({ locale: "el", messages: {} }),
    text: async () => "{}",
    headers: new window.Headers(),
  });
  globalThis.fetch = window.fetch;
}

async function freshAppEnvironment() {
  const dom = new JSDOM(loadHtmlSkeleton(), {
    url: "http://localhost/greektax/",
    pretendToBeVisual: true,
    runScripts: "outside-only",
  });
  installDomGlobals(dom);
  // Bypass the import cache so each test starts with a fresh module copy.
  const mod = await import(`${APP_MODULE}?t=${Date.now()}-${Math.random()}`);
  return { dom, mod };
}

condTest("default load leaves localStorage untouched", async () => {
  const { dom, mod } = await freshAppEnvironment();
  await mod.bootstrapApp();
  const grossInput = dom.window.document.getElementById(
    "employment-gross-income"
  );
  if (grossInput) {
    grossInput.value = "42000";
    grossInput.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  }
  // Allow the debounced persist scheduler (150 ms) to fire if it were going to.
  await new Promise((resolve) => setTimeout(resolve, 250));
  assert.equal(
    dom.window.localStorage.getItem(CALCULATOR_KEY),
    null,
    "calculator state must not be written when opt-in is off"
  );
  assert.equal(
    dom.window.localStorage.getItem(OPTIN_KEY),
    null,
    "opt-in preference must not be written until the user toggles it"
  );
});

condTest("toggling Remember on persists and toggling off clears", async () => {
  const { dom, mod } = await freshAppEnvironment();
  await mod.bootstrapApp();
  const toggle = dom.window.document.getElementById("remember-entries");
  assert.ok(toggle, "checkbox #remember-entries must exist in the served HTML");
  assert.equal(toggle.checked, false, "default state should be unchecked");

  // User opts in.
  toggle.checked = true;
  toggle.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  assert.equal(
    dom.window.localStorage.getItem(OPTIN_KEY),
    "1",
    "opt-in preference should be written when toggled on"
  );

  // Any subsequent edit gets persisted.
  const grossInput = dom.window.document.getElementById(
    "employment-gross-income"
  );
  if (grossInput) {
    grossInput.value = "37500";
    grossInput.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  }
  await new Promise((resolve) => setTimeout(resolve, 250));
  const stored = dom.window.localStorage.getItem(CALCULATOR_KEY);
  assert.ok(stored, "calculator state should be written after opting in");

  // User opts out — calculator state should be cleared, opt-in marker removed.
  toggle.checked = false;
  toggle.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  assert.equal(
    dom.window.localStorage.getItem(CALCULATOR_KEY),
    null,
    "calculator state must be cleared when opting out"
  );
  assert.equal(
    dom.window.localStorage.getItem(OPTIN_KEY),
    null,
    "opt-in marker must be removed when opting out"
  );
});

condTest("Remember checkbox itself is excluded from the persisted snapshot", async () => {
  const { dom, mod } = await freshAppEnvironment();
  await mod.bootstrapApp();
  const toggle = dom.window.document.getElementById("remember-entries");
  toggle.checked = true;
  toggle.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 250));
  const stored = dom.window.localStorage.getItem(CALCULATOR_KEY);
  assert.ok(stored, "calculator state should be persisted after opt-in");
  const payload = JSON.parse(stored);
  assert.ok(payload.values && typeof payload.values === "object");
  assert.ok(
    !Object.prototype.hasOwnProperty.call(payload.values, "remember-entries"),
    "remember-entries key must not appear in the persisted snapshot"
  );
});
