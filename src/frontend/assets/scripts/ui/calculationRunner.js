/**
 * Runs a calculation with the bundled engine (assets/scripts/engine/).
 * Everything happens in the browser; nothing is sent anywhere.
 *
 * The engine is loaded separately from the page so that it does not delay the
 * first render: preloadEngine() fetches it once the page is idle.
 */

const importEngine = () => import("../engine/calculate.js");

const scheduleIdle = (task) =>
  typeof requestIdleCallback === "function"
    ? requestIdleCallback(task, { timeout: 2000 })
    : setTimeout(task, 0);

/** Start loading the engine once the page is idle. */
export function preloadEngine({ loadEngine = importEngine, schedule = scheduleIdle } = {}) {
  schedule(() => {
    // A failure is reported by the calculation that needs the engine.
    loadEngine().catch(() => {});
  });
}

/**
 * Give the engine a JSON-normalised copy of the payload (as the parity
 * fixtures are), with its locale resolved to a supported one ("en" otherwise).
 */
export function prepareClientPayload(payload, acceptLanguage, availableLocales) {
  const prepared = JSON.parse(JSON.stringify(payload));
  const normalise = (value) => {
    const candidate = String(value).toLowerCase().split("-")[0];
    return availableLocales.includes(candidate) ? candidate : "en";
  };
  if (prepared.locale) {
    prepared.locale = normalise(prepared.locale);
  } else if (acceptLanguage) {
    const primary = String(acceptLanguage).split(",")[0].trim();
    if (primary) {
      prepared.locale = normalise(primary);
    }
  }
  return prepared;
}

/**
 * Return the result to render, or throw an Error whose message is the one to
 * show the user.
 */
export async function runCalculation(payload, locale, loadEngine = importEngine) {
  const engine = await loadEngine();
  return engine.calculateTax(
    prepareClientPayload(payload, locale, engine.ENGINE_LOCALES),
  );
}
