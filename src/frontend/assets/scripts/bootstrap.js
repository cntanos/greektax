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

  const resolveModuleUrl = () => {
    const trimmedPath = modulePath.trim();
    if (!trimmedPath) {
      throw new Error("Empty front-end module path");
    }

    // Absolute URLs (including protocol-relative URLs) should be respected as-is.
    const absoluteUrlPattern = /^(?:[a-zA-Z][a-zA-Z\d+\-.]*:)?\/\//;
    if (absoluteUrlPattern.test(trimmedPath)) {
      if (trimmedPath.startsWith("//")) {
        const protocol = typeof window !== "undefined" && window.location
          ? window.location.protocol
          : "https:";
        return `${protocol}${trimmedPath}`;
      }
      return trimmedPath;
    }

    try {
      return new URL(
        trimmedPath,
        document?.baseURI ?? window?.location?.href ?? "",
      ).toString();
    } catch (error) {
      // Rethrow to ensure the calling context handles the failure uniformly.
      throw error instanceof Error
        ? error
        : new Error("Failed to resolve front-end module URL");
    }
  };

  let moduleUrl;
  try {
    moduleUrl = resolveModuleUrl();
  } catch (error) {
    console.error(
      "GreekTax could not resolve the front-end module path.",
      error,
    );
    return;
  }

  const forceFallback =
    loaderScript.dataset.forceFallback === "true" ||
    (typeof window !== "undefined" &&
      window.GREEKTAX_FORCE_MODULE_FALLBACK === true);

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

  const createModuleGraphBuilder = () => {
    const moduleCache = new Map();
    const entryOrigin = (() => {
      try {
        return new URL(moduleUrl, document.baseURI).origin;
      } catch (error) {
        return document.location?.origin || "";
      }
    })();

    const shouldInlineSpecifier = (targetUrl) => {
      if (!targetUrl) {
        return false;
      }
      try {
        const parsed = new URL(targetUrl);
        return parsed.origin === entryOrigin;
      } catch (error) {
        return false;
      }
    };

    const revokeAll = () => {
      for (const record of moduleCache.values()) {
        try {
          if (record && typeof record.revoke === "function") {
            record.revoke();
          }
        } catch (error) {
          // Ignore revocation errors—they are non-fatal cleanup issues.
        }
      }
      moduleCache.clear();
    };

    const registerModuleSource = (originalUrl, source) => {
      const blob = new Blob([source], { type: "application/javascript" });
      const blobUrl = URL.createObjectURL(blob);
      const record = {
        url: originalUrl,
        blobUrl,
        revoke: () => {
          try {
            URL.revokeObjectURL(blobUrl);
          } catch (error) {
            // Swallow errors—revoking an already released URL is harmless.
          }
        },
      };
      moduleCache.set(originalUrl, record);
      return record;
    };

    const gatherModuleSpecifiers = (source) => {
      const matches = [];

      const patterns = [
        /(import\s+[^"'`]*?from\s*)(["'])([^"']+)(["'])/g,
        /(import\s*)(["'])([^"']+)(["'])/g,
        /(export\s+[^"'`]*?from\s*)(["'])([^"']+)(["'])/g,
        /(import\s*\(\s*)(["'])([^"']+)(["'])(\s*\))/g,
      ];

      for (const pattern of patterns) {
        pattern.lastIndex = 0;
        let match;
        while ((match = pattern.exec(source)) !== null) {
          const [
            fullMatch,
            prefix,
            openQuote,
            specifier,
            closeQuote,
            suffix = "",
          ] = match;

          const specifierStart =
            match.index + prefix.length + openQuote.length;
          const specifierEnd = specifierStart + specifier.length;

          matches.push({
            specifier,
            specifierStart,
            specifierEnd,
            openQuote,
            closeQuote,
            suffix,
            fullMatch,
          });
        }
      }

      // Sort matches by their appearance order so replacements are applied safely.
      matches.sort((a, b) => a.specifierStart - b.specifierStart);

      return matches;
    };

    const rebuildModuleSource = (source, replacements) => {
      if (!Array.isArray(replacements) || !replacements.length) {
        return source;
      }

      let cursor = 0;
      let result = "";

      for (const replacement of replacements) {
        const { specifierStart, specifierEnd, value } = replacement;
        result += source.slice(cursor, specifierStart);
        result += value;
        cursor = specifierEnd;
      }

      result += source.slice(cursor);
      return result;
    };

    const loadModuleGraph = async (targetUrl, ancestry = new Set()) => {
      if (!targetUrl) {
        throw new Error("Cannot load an empty module URL");
      }

      if (moduleCache.has(targetUrl)) {
        return moduleCache.get(targetUrl);
      }

      if (ancestry.has(targetUrl)) {
        throw new Error(`Circular module reference detected for ${targetUrl}`);
      }

      ancestry.add(targetUrl);

      try {
        const response = await fetch(targetUrl, { credentials: "same-origin" });
        if (!response.ok) {
          throw new Error(
            `Failed to download module ${targetUrl} (HTTP ${response.status}).`,
          );
        }

        const contentType = response.headers.get("content-type") || "";

        if (/json/i.test(contentType) || targetUrl.endsWith(".json")) {
          const jsonText = await response.text();
          const jsonModuleSource = `export default ${jsonText.trim()};`;
          return registerModuleSource(
            targetUrl,
            `${jsonModuleSource}\n//# sourceURL=${targetUrl}`,
          );
        }

        const sourceText = await response.text();
        const specifiers = gatherModuleSpecifiers(sourceText);
        const replacements = [];
        const seenOffsets = new Set();

        for (const entry of specifiers) {
          if (seenOffsets.has(entry.specifierStart)) {
            continue;
          }
          seenOffsets.add(entry.specifierStart);

          const resolvedSpecifier = (() => {
            try {
              return new URL(entry.specifier, targetUrl).toString();
            } catch (error) {
              return entry.specifier;
            }
          })();

          let replacementValue = resolvedSpecifier;
          const requiresJsonModule =
            typeof resolvedSpecifier === "string" &&
            resolvedSpecifier.toLowerCase().includes(".json");
          const shouldInline =
            requiresJsonModule || shouldInlineSpecifier(resolvedSpecifier);

          if (shouldInline) {
            try {
              const moduleRecord = await loadModuleGraph(
                resolvedSpecifier,
                ancestry,
              );
              if (moduleRecord?.blobUrl) {
                replacementValue = moduleRecord.blobUrl;
              }
            } catch (dependencyError) {
              console.error(
                `GreekTax failed to inline dependency ${resolvedSpecifier}.`,
                dependencyError,
              );
              replacementValue = resolvedSpecifier;
            }
          }

          replacements.push({
            specifierStart: entry.specifierStart,
            specifierEnd: entry.specifierEnd,
            value: replacementValue,
          });
        }

        const transformedSource = rebuildModuleSource(sourceText, replacements);
        return registerModuleSource(
          targetUrl,
          `${transformedSource}\n//# sourceURL=${targetUrl}`,
        );
      } finally {
        ancestry.delete(targetUrl);
      }
    };

    return {
      loadModuleGraph,
      revokeAll,
    };
  };

  (async () => {
    if (!forceFallback) {
      try {
        await attachModuleScript();
        return;
      } catch (nativeError) {
        console.warn(
          "GreekTax will retry loading the front-end module after a MIME type error.",
          nativeError,
        );
      }
    } else if (typeof console !== "undefined" && console.info) {
      console.info("GreekTax is forcing the module fallback loader.");
    }

    try {
      const { loadModuleGraph, revokeAll } = createModuleGraphBuilder();
      const entryModule = await loadModuleGraph(moduleUrl);
      if (!entryModule?.blobUrl) {
        throw new Error("Failed to construct fallback module blob");
      }

      const fallbackModule = document.createElement("script");
      fallbackModule.type = "module";
      fallbackModule.dataset.entryModule = moduleUrl;
      fallbackModule.src = entryModule.blobUrl;

      const cleanup = () => {
        fallbackModule.removeEventListener("load", onLoad);
        fallbackModule.removeEventListener("error", onError);
      };

      const onLoad = () => {
        cleanup();
        // Give the module graph a moment to finish evaluating before cleanup.
        setTimeout(() => {
          revokeAll();
        }, 0);
      };

      const onError = (event) => {
        cleanup();
        revokeAll();
        const detail = event?.error ?? event;
        console.error(
          "GreekTax failed to execute the fallback front-end module.",
          detail,
        );
      };

      fallbackModule.addEventListener("load", onLoad);
      fallbackModule.addEventListener("error", onError);

      insertScript(fallbackModule);
    } catch (fallbackError) {
      console.error(
        "GreekTax failed to load the front-end module bundle.",
        fallbackError,
      );
    }
  })();
})();
