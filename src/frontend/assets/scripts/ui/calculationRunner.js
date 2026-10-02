/**
 * Chooses where a calculation runs, controlled by the deploy-time
 * <meta name="greektax-engine" content="..."> tag:
 *
 * - "server" (default): POST to the API, as before.
 * - "shadow": POST to the API and also run the client engine; show the server
 *   result and report any difference in the browser console. Nothing is sent
 *   anywhere else.
 * - "client": run the client engine only; no calculation request is made.
 */

export const ENGINE_MODES = ["server", "shadow", "client"];
const DEFAULT_MODE = "server";
const SHADOW_LOG_PREFIX = "[GreekTax shadow]";

export function resolveEngineMode(documentRef) {
  const meta = documentRef?.querySelector?.('meta[name="greektax-engine"]');
  const requested = (meta?.getAttribute("content") || "").trim().toLowerCase();
  return ENGINE_MODES.includes(requested) ? requested : DEFAULT_MODE;
}

/** POST the payload to the calculation endpoint (the original request). */
export async function fetchServerCalculation(endpoint, payload, acceptLanguage) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept-Language": acceptLanguage,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    throw new Error(errorPayload.message || response.statusText);
  }
  return response.json();
}

/**
 * Give the client engine exactly what the API route would pass to
 * calculate_tax: the JSON-serialised payload, with the locale resolved as in
 * routes/calculations.py (_resolve_locale).
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

/** List the paths at which two JSON values differ (numbers via Object.is). */
export function diffResults(expected, actual, path = "") {
  if (Object.is(expected, actual)) {
    return [];
  }
  const bothObjects =
    expected !== null &&
    actual !== null &&
    typeof expected === "object" &&
    typeof actual === "object" &&
    Array.isArray(expected) === Array.isArray(actual);
  if (!bothObjects) {
    return [{ path: path || "(root)", server: expected, client: actual }];
  }
  const keys = new Set([...Object.keys(expected), ...Object.keys(actual)]);
  const differences = [];
  for (const key of keys) {
    differences.push(...diffResults(expected[key], actual[key], path ? `${path}.${key}` : key));
  }
  return differences;
}

async function settle(run) {
  try {
    return { result: await run() };
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }
}

/**
 * Run a calculation in the given mode and return the result to render, or
 * throw an Error whose message is the one to show (as the API error did).
 */
export async function runCalculation({
  payload,
  mode,
  acceptLanguage,
  requestServer,
  loadEngine = () => import("../engine/calculate.js"),
  logger = console,
}) {
  const runClient = async () => {
    const engine = await loadEngine();
    return engine.calculateTax(
      prepareClientPayload(payload, acceptLanguage, engine.ENGINE_LOCALES),
    );
  };

  if (mode === "client") {
    return runClient();
  }

  if (mode !== "shadow") {
    return requestServer(payload);
  }

  const server = await settle(() => requestServer(payload));
  const client = await settle(runClient);
  const differences = diffResults(server, client);
  if (differences.length) {
    logger.warn(`${SHADOW_LOG_PREFIX} client engine differs from the server`, {
      differences,
      payload,
    });
  } else {
    logger.info(`${SHADOW_LOG_PREFIX} client engine matches the server`);
  }

  if (server.error !== undefined) {
    throw new Error(server.error);
  }
  return server.result;
}
