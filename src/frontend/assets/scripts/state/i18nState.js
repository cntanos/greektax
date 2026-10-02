export function createI18nState() {
  return {
    translationsByLocale: new Map(),
    fallbackLocale: "en",
  };
}
