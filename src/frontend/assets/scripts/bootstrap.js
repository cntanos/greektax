/**
 * Lightweight bootstrapper that ensures the main front-end bundle loads as an
 * ES module, even if the hosting HTML forgets to mark the script tag with
 * `type="module"`.
 */

(function bootstrapFrontendModule() {
  if (typeof document === "undefined") {
    return;
  }

  const loaderScript = document.currentScript;
  if (!loaderScript) {
    return;
  }

  if (loaderScript.dataset.entryModuleLoaded === "true") {
    return;
  }
  loaderScript.dataset.entryModuleLoaded = "true";

  const modulePath =
    loaderScript.getAttribute("data-module") ?? "./main.js";

  let moduleUrl;
  try {
    if (loaderScript.src) {
      moduleUrl = new URL(modulePath, loaderScript.src).toString();
    } else {
      moduleUrl = new URL(modulePath, document.baseURI).toString();
    }
  } catch (error) {
    console.error(
      "GreekTax could not resolve the front-end module path.",
      error,
    );
    return;
  }

  const existingModule = document.querySelector(
    `script[type="module"][data-entry-module="${moduleUrl}"]`,
  );
  if (existingModule) {
    return;
  }

  const parent = loaderScript.parentNode ?? document.head;
  const insertScript = (script) => {
    if (loaderScript.nextSibling) {
      parent.insertBefore(script, loaderScript.nextSibling);
    } else {
      parent.appendChild(script);
    }
  };

  const attachModuleScript = () =>
    new Promise((resolve, reject) => {
      const moduleScript = document.createElement("script");
      moduleScript.type = "module";
      moduleScript.defer = true;
      moduleScript.src = moduleUrl;
      moduleScript.dataset.entryModule = moduleUrl;

      const cleanup = () => {
        moduleScript.removeEventListener("load", onLoad);
        moduleScript.removeEventListener("error", onError);
      };

      const onLoad = () => {
        cleanup();
        resolve();
      };

      const onError = (event) => {
        cleanup();
        moduleScript.remove();
        const detail = event?.error ?? event;
        reject(detail instanceof Error ? detail : new Error("Module load failed"));
      };

      moduleScript.addEventListener("load", onLoad);
      moduleScript.addEventListener("error", onError);

      insertScript(moduleScript);
    });

  const fetchModuleSource = async () => {
    const response = await fetch(moduleUrl, { credentials: "same-origin" });
    if (!response.ok) {
      throw new Error(
        `Failed to download front-end module (HTTP ${response.status}).`,
      );
    }
    return response.text();
  };

  const rewriteRelativeImportSpecifiers = (source) => {
    const pattern =
      /(import\s+[^"'`]*?from\s*)(["'])(\.{1,2}\/[^"']+)(["'])/g;
    const exportPattern =
      /(export\s+[^"'`]*?from\s*)(["'])(\.{1,2}\/[^"']+)(["'])/g;
    const dynamicPattern =
      /(import\s*\(\s*)(["'])(\.{1,2}\/[^"']+)(["'])(\s*\))/g;

    const toAbsolute = (specifier) => new URL(specifier, moduleUrl).toString();

    return source
      .replace(pattern, (match, prefix, openQuote, specifier, closeQuote) =>
        `${prefix}${openQuote}${toAbsolute(specifier)}${closeQuote}`,
      )
      .replace(
        exportPattern,
        (match, prefix, openQuote, specifier, closeQuote) =>
          `${prefix}${openQuote}${toAbsolute(specifier)}${closeQuote}`,
      )
      .replace(
        dynamicPattern,
        (match, prefix, openQuote, specifier, closeQuote, suffix) =>
          `${prefix}${openQuote}${toAbsolute(specifier)}${closeQuote}${suffix}`,
      );
  };

  const injectInlineModule = (source) => {
    const inlineModule = document.createElement("script");
    inlineModule.type = "module";
    inlineModule.dataset.entryModule = moduleUrl;
    inlineModule.textContent = `${source}\n//# sourceURL=${moduleUrl}`;
    insertScript(inlineModule);
  };

  (async () => {
    try {
      await attachModuleScript();
      return;
    } catch (nativeError) {
      console.warn(
        "GreekTax will retry loading the front-end module after a MIME type error.",
        nativeError,
      );
    }

    try {
      const source = await fetchModuleSource();
      const rewrittenSource = rewriteRelativeImportSpecifiers(source);
      injectInlineModule(rewrittenSource);
    } catch (fallbackError) {
      console.error(
        "GreekTax failed to load the front-end module bundle.",
        fallbackError,
      );
    }
  })();
})();
