const STORAGE_KEY = "greektax.locale";

const translationsByLocale = new Map();
let availableTranslationLocales = ["el", "en"];
let fallbackLocale = "en";
let currentLocale = "el";

export function normaliseLocaleChoice(locale) {
  if (typeof locale !== "string" || !locale) {
    return fallbackLocale;
  }
  return locale.toLowerCase().split("-")[0];
}

function getWindowRef(windowOverride) {
  if (windowOverride) {
    return windowOverride;
  }
  if (typeof window !== "undefined") {
    return window;
  }
  return null;
}

function getStorage(storageOverride) {
  if (storageOverride) {
    return storageOverride;
  }
  const windowRef = getWindowRef();
  return windowRef?.localStorage ?? null;
}

function storeFrontendTranslations(locale, frontend) {
  if (!locale || !frontend || typeof frontend !== "object") {
    return;
  }
  translationsByLocale.set(locale, frontend);
}

function ingestTranslationPayload(payload) {
  if (!payload || typeof payload !== "object") {
    throw new Error("Unexpected translations payload");
  }

  if (Array.isArray(payload.available_locales) && payload.available_locales.length) {
    availableTranslationLocales = payload.available_locales
      .map((value) => (typeof value === "string" ? value.toLowerCase().split("-")[0] : null))
      .filter((value) => value);
  }

  const resolvedLocale =
    typeof payload.locale === "string"
      ? payload.locale.toLowerCase().split("-")[0]
      : null;
  if (resolvedLocale && payload.frontend && typeof payload.frontend === "object") {
    storeFrontendTranslations(resolvedLocale, payload.frontend);
  }

  const fallbackPayload = payload.fallback;
  if (
    fallbackPayload &&
    typeof fallbackPayload === "object" &&
    typeof fallbackPayload.locale === "string" &&
    fallbackPayload.frontend &&
    typeof fallbackPayload.frontend === "object"
  ) {
    const fallbackResolved = fallbackPayload.locale.toLowerCase().split("-")[0];
    fallbackLocale = fallbackResolved;
    storeFrontendTranslations(fallbackResolved, fallbackPayload.frontend);
    if (!availableTranslationLocales.includes(fallbackResolved)) {
      availableTranslationLocales.push(fallbackResolved);
    }
  }

  if (resolvedLocale && !availableTranslationLocales.includes(resolvedLocale)) {
    availableTranslationLocales.push(resolvedLocale);
  }

  if (!availableTranslationLocales.length) {
    availableTranslationLocales = [fallbackLocale];
  } else {
    availableTranslationLocales = Array.from(new Set(availableTranslationLocales));
  }

  return resolvedLocale || fallbackLocale;
}

export async function ensureTranslations(locale, fetchTranslations) {
  const target = normaliseLocaleChoice(locale);
  if (!translationsByLocale.has(target)) {
    if (typeof fetchTranslations !== "function") {
      throw new Error("fetchTranslations dependency is required");
    }
    try {
      const payload = await fetchTranslations(target);
      return ingestTranslationPayload(payload);
    } catch (error) {
      if (typeof console !== "undefined" && console.error) {
        console.error("Failed to load translations", error);
      }
      if (!translationsByLocale.has(fallbackLocale)) {
        try {
          const fallbackPayload = await fetchTranslations(fallbackLocale);
          ingestTranslationPayload(fallbackPayload);
        } catch (fallbackError) {
          if (typeof console !== "undefined" && console.error) {
            console.error("Failed to load fallback translations", fallbackError);
          }
        }
      }
    }
  }
  return translationsByLocale.has(target) ? target : fallbackLocale;
}

export function getFrontendCatalog(locale) {
  const entry = translationsByLocale.get(locale);
  return entry && typeof entry === "object" ? entry : null;
}

export function getMessagesSection(locale, section) {
  const catalogue = getFrontendCatalog(locale);
  if (catalogue && section in catalogue && typeof catalogue[section] === "object") {
    return catalogue[section];
  }
  const fallbackCatalogue = getFrontendCatalog(fallbackLocale);
  if (
    fallbackCatalogue &&
    section in fallbackCatalogue &&
    typeof fallbackCatalogue[section] === "object"
  ) {
    return fallbackCatalogue[section];
  }
  return {};
}

function lookupMessage(locale, keyParts) {
  let cursor = getFrontendCatalog(locale);
  for (let index = 0; index < keyParts.length; index += 1) {
    const key = keyParts[index];
    if (!cursor || typeof cursor !== "object") {
      return undefined;
    }
    cursor = cursor[key];
  }
  if (typeof cursor === "string") {
    return cursor;
  }
  return undefined;
}

export function formatTemplate(template, replacements) {
  if (typeof template !== "string" || !replacements || typeof replacements !== "object") {
    return template;
  }
  return template.replace(/{{\s*([a-zA-Z0-9_.-]+)\s*}}/g, (match, key) => {
    const value = replacements[key];
    if (value === undefined || value === null) {
      return match;
    }
    if (typeof value === "number") {
      return String(value);
    }
    if (typeof value === "string") {
      return value;
    }
    return match;
  });
}

export function t(key, replacements = {}, locale = currentLocale) {
  if (typeof key !== "string" || !key) {
    return "";
  }
  const keyParts = key.split(".");
  const message = lookupMessage(locale, keyParts);
  if (typeof message === "string") {
    return formatTemplate(message, replacements);
  }
  const fallbackMessage =
    locale === fallbackLocale ? undefined : lookupMessage(fallbackLocale, keyParts);
  if (typeof fallbackMessage === "string") {
    return formatTemplate(fallbackMessage, replacements);
  }
  return key;
}

export function resolveLocaleTag(locale) {
  if (locale === "el") {
    return "el-GR";
  }
  if (locale === "en") {
    return "en-GB";
  }
  return locale || "en-GB";
}

const NON_BREAKING_SPACE = "\u00a0";
const GROUPING_REGEX = /\B(?=(\d{3})+(?!\d))/g;
const DEFAULT_CURRENCY = "EUR";

const FALLBACK_NUMBER_FORMATS = {
  el: {
    decimal: ",",
    group: ".",
    currencyPattern: (value, { useNonBreakingSpace }) =>
      `${value}${useNonBreakingSpace ? NON_BREAKING_SPACE : " "}€`,
    percentSuffix: "%",
  },
  en: {
    decimal: ".",
    group: ",",
    currencyPattern: (value) => `€${value}`,
    percentSuffix: "%",
  },
};

const numberFormatterCache = new Map();

export function __resetLocalisationState() {
  translationsByLocale.clear();
  availableTranslationLocales = ["el", "en"];
  fallbackLocale = "en";
  currentLocale = "el";
  numberFormatterCache.clear();
}

function getFallbackFormat(locale) {
  if (locale in FALLBACK_NUMBER_FORMATS) {
    return FALLBACK_NUMBER_FORMATS[locale];
  }
  return FALLBACK_NUMBER_FORMATS.en;
}

export function getActiveLocale() {
  return normaliseLocaleChoice(currentLocale || fallbackLocale || "en");
}

export function getCurrentLocale() {
  return currentLocale;
}

export function setActiveLocale(locale) {
  currentLocale = normaliseLocaleChoice(locale);
}

export function getFallbackLocale() {
  return fallbackLocale;
}

function getNumberFormatter(locale, options) {
  if (typeof Intl === "undefined" || typeof Intl.NumberFormat === "undefined") {
    return null;
  }

  const resolvedLocale = resolveLocaleTag(locale);
  const key = [
    resolvedLocale,
    options.style || "decimal",
    options.currency || "",
    options.minimumFractionDigits ?? "",
    options.maximumFractionDigits ?? "",
    options.useGrouping === false ? "nogroup" : "group",
  ].join("|");

  if (!numberFormatterCache.has(key)) {
    try {
      numberFormatterCache.set(key, new Intl.NumberFormat(resolvedLocale, options));
    } catch (error) {
      if (typeof console !== "undefined" && console.warn) {
        console.warn("Unable to create number formatter", error);
      }
      numberFormatterCache.set(key, null);
    }
  }

  return numberFormatterCache.get(key);
}

export function coerceFiniteNumber(value) {
  const parsed = Number.parseFloat(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatNumberParts(value, minimumFractionDigits, fallback) {
  const numeric = coerceFiniteNumber(value);
  const sign = numeric < 0 ? "-" : "";
  const absolute = Math.abs(numeric);
  const integerPart = Math.floor(absolute).toString().replace(GROUPING_REGEX, fallback.group);
  let fractionPart = Math.round(
    (absolute - Math.floor(absolute)) * 10 ** Math.max(0, minimumFractionDigits),
  )
    .toString()
    .padStart(minimumFractionDigits, "0");
  if (minimumFractionDigits === 0) {
    fractionPart = "";
  }
  const decimalPart = fractionPart
    ? `${fallback.decimal}${fractionPart}`
    : minimumFractionDigits > 0
    ? `${fallback.decimal}${"0".repeat(minimumFractionDigits)}`
    : "";
  return { sign, integerPart, fractionPart, decimalPart };
}

export function formatNumber(
  value,
  {
    locale = getActiveLocale(),
    minimumFractionDigits = 0,
    maximumFractionDigits = 2,
    useNonBreakingSpace = true,
  } = {},
) {
  const numeric = coerceFiniteNumber(value);
  const formatter = getNumberFormatter(resolveLocaleTag(locale), {
    style: "decimal",
    minimumFractionDigits,
    maximumFractionDigits,
  });

  if (formatter) {
    let formatted = formatter.format(numeric);
    if (!useNonBreakingSpace) {
      formatted = formatted.replace(/\u00a0/g, " ");
    }
    return formatted;
  }

  const fallback = getFallbackFormat(locale);
  const parts = formatNumberParts(numeric, maximumFractionDigits, fallback);
  let fractionPart = parts.fractionPart;
  if (fractionPart && maximumFractionDigits > minimumFractionDigits) {
    fractionPart = fractionPart.replace(/0+$/, "");
  }
  if (fractionPart && fractionPart.length < minimumFractionDigits) {
    while (fractionPart.length < minimumFractionDigits) {
      fractionPart += "0";
    }
  }
  const decimalPart = fractionPart
    ? `${fallback.decimal}${fractionPart}`
    : minimumFractionDigits > 0
    ? `${fallback.decimal}${"0".repeat(minimumFractionDigits)}`
    : "";
  return `${parts.sign}${parts.integerPart}${decimalPart}`;
}

export function formatInteger(value, { locale = getActiveLocale() } = {}) {
  const numeric = Math.round(coerceFiniteNumber(value));
  const formatter = getNumberFormatter(resolveLocaleTag(locale), {
    style: "decimal",
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  });
  if (formatter) {
    return formatter.format(numeric);
  }
  const fallback = getFallbackFormat(locale);
  const parts = formatNumberParts(numeric, 0, fallback);
  return `${parts.sign}${parts.integerPart}`;
}

export function formatCurrency(
  value,
  { locale = getActiveLocale(), useNonBreakingSpace = true } = {},
) {
  const numeric = coerceFiniteNumber(value);
  const formatter = getNumberFormatter(resolveLocaleTag(locale), {
    style: "currency",
    currency: DEFAULT_CURRENCY,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  if (formatter) {
    let formatted = formatter.format(numeric);
    if (!useNonBreakingSpace) {
      formatted = formatted.replace(/\u00a0/g, " ");
    }
    return formatted;
  }

  const fallback = getFallbackFormat(locale);
  const parts = formatNumberParts(numeric, 2, fallback);
  const valuePart = `${parts.integerPart}${fallback.decimal}${parts.fractionPart}`;
  const formattedValue = fallback.currencyPattern(valuePart, { useNonBreakingSpace });
  return `${parts.sign}${formattedValue}`;
}

export function formatPercent(
  value,
  {
    locale = getActiveLocale(),
    maximumFractionDigits = 1,
    minimumFractionDigits = 0,
    useNonBreakingSpace = true,
  } = {},
) {
  const numeric = coerceFiniteNumber(value);
  const formatter = getNumberFormatter(resolveLocaleTag(locale), {
    style: "percent",
    minimumFractionDigits,
    maximumFractionDigits,
  });

  if (formatter) {
    let formatted = formatter.format(numeric);
    if (!useNonBreakingSpace) {
      formatted = formatted.replace(/\u00a0/g, " ");
    }
    return formatted;
  }

  const fallback = getFallbackFormat(locale);
  const scaled = numeric * 100;
  const parts = formatNumberParts(
    scaled,
    Math.max(maximumFractionDigits, minimumFractionDigits),
    fallback,
  );
  let fractionPart = parts.fractionPart;
  if (fractionPart) {
    fractionPart = fractionPart.replace(/0+$/, "");
  }
  if (fractionPart && fractionPart.length < minimumFractionDigits) {
    while (fractionPart.length < minimumFractionDigits) {
      fractionPart += "0";
    }
  }
  const decimalPart = fractionPart ? `${fallback.decimal}${fractionPart}` : "";
  return `${parts.sign}${parts.integerPart}${decimalPart}${fallback.percentSuffix}`;
}

export function formatDateTime(value, { locale = getActiveLocale() } = {}) {
  if (!value) {
    return "";
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  if (typeof Intl !== "undefined" && typeof Intl.DateTimeFormat !== "undefined") {
    try {
      const formatter = new Intl.DateTimeFormat(resolveLocaleTag(locale), {
        dateStyle: "medium",
        timeStyle: "short",
      });
      return formatter.format(date);
    } catch (error) {
      if (typeof console !== "undefined" && console.warn) {
        console.warn("Unable to format date", error);
      }
    }
  }
  return date.toISOString();
}

export function formatList(items, localeOverride = getActiveLocale()) {
  if (!Array.isArray(items) || items.length === 0) {
    return "";
  }
  if (typeof Intl !== "undefined" && typeof Intl.ListFormat !== "undefined") {
    try {
      const formatter = new Intl.ListFormat(resolveLocaleTag(localeOverride), {
        style: "long",
        type: "conjunction",
      });
      return formatter.format(items);
    } catch (error) {
      // Fall back to manual formatting below.
    }
  }
  if (items.length === 1) {
    return items[0];
  }
  const rest = items.slice(0, -1).join(", ");
  const last = items[items.length - 1];
  const conjunction = t("ui.list_and", {}, localeOverride) || "and";
  return `${rest} ${conjunction} ${last}`;
}

export function formatListForLocale(items) {
  const values = Array.isArray(items)
    ? items.filter((item) => typeof item === "string" && item.trim())
    : [];
  if (!values.length) {
    return "";
  }

  if (typeof Intl !== "undefined" && typeof Intl.ListFormat === "function") {
    try {
      const formatter = new Intl.ListFormat(getActiveLocale(), {
        style: "long",
        type: "conjunction",
      });
      return formatter.format(values);
    } catch (error) {
      if (typeof console !== "undefined" && console.warn) {
        console.warn("Unable to format list for locale", error);
      }
    }
  }

  if (values.length === 1) {
    return values[0];
  }

  const conjunctionKey = "ui.list_and";
  const conjunction = t(conjunctionKey);
  const conjunctionWord =
    conjunction && conjunction !== conjunctionKey ? conjunction : "and";

  if (values.length === 2) {
    return `${values[0]} ${conjunctionWord} ${values[1]}`;
  }

  const head = values.slice(0, -1).join(", ");
  const tail = values[values.length - 1];
  return `${head}, ${conjunctionWord} ${tail}`;
}

export function resolveStoredLocale(defaultLocale = "el", storageOverride = null) {
  const storage = getStorage(storageOverride);
  try {
    const stored = storage?.getItem?.(STORAGE_KEY);
    return normaliseLocaleChoice(stored || defaultLocale);
  } catch (error) {
    if (typeof console !== "undefined" && console.warn) {
      console.warn("Unable to access localStorage", error);
    }
    return normaliseLocaleChoice(defaultLocale);
  }
}

export function persistLocale(locale, storageOverride = null) {
  const storage = getStorage(storageOverride);
  try {
    storage?.setItem?.(STORAGE_KEY, locale);
  } catch (error) {
    if (typeof console !== "undefined" && console.warn) {
      console.warn("Unable to persist locale preference", error);
    }
  }
}

export function getLocaleStorageKey() {
  return STORAGE_KEY;
}
