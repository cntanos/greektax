/**
 * Read-only access to the configuration bundled at build time.
 *
 * Each getter returns the same payload the corresponding /api/v1/config
 * endpoint returned, so callers keep their existing response handling.
 */

import { CLIENT_CONFIG } from "../data/client-config.generated.js";

const FALLBACK_LOCALE = "en";

function resolveLocale(locale) {
  const requested = String(locale || FALLBACK_LOCALE)
    .toLowerCase()
    .split("-")[0];
  return CLIENT_CONFIG.locales.includes(requested) ? requested : FALLBACK_LOCALE;
}

function perYearPayload(section, year, locale) {
  const byLocale = section[String(year)];
  if (!byLocale) {
    throw new Error(`No configuration bundled for ${year}`);
  }
  return byLocale[resolveLocale(locale)];
}

export function getYearsPayload() {
  return CLIENT_CONFIG.years;
}

export function getApplicationVersion() {
  return CLIENT_CONFIG.meta.version;
}

export function getInvestmentPayload(year, locale) {
  return perYearPayload(CLIENT_CONFIG.investment, year, locale);
}

export function getDeductionsPayload(year, locale) {
  return perYearPayload(CLIENT_CONFIG.deductions, year, locale);
}
