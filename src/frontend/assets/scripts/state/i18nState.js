export function createI18nState() {
  return {
    translationsByLocale: new Map(),
    availableTranslationLocales: ["el", "en"],
    fallbackLocale: "en",
  };
}
