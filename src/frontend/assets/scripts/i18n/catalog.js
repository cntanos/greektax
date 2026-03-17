export function isPlainObject(value) {
  return Boolean(
    value && typeof value === "object" && !Array.isArray(value) && value !== null,
  );
}

export function mergeTranslationCatalogues(base, overrides) {
  if (!isPlainObject(overrides)) {
    return base || {};
  }

  const result = isPlainObject(base) ? { ...base } : {};

  Object.entries(overrides).forEach(([key, value]) => {
    const existing = result[key];
    if (isPlainObject(existing) && isPlainObject(value)) {
      result[key] = mergeTranslationCatalogues(existing, value);
    } else {
      result[key] = value;
    }
  });

  return result;
}
