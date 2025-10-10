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

  const moduleScript = document.createElement("script");
  moduleScript.type = "module";
  moduleScript.defer = true;
  moduleScript.src = moduleUrl;
  moduleScript.dataset.entryModule = moduleUrl;

  moduleScript.addEventListener("error", (event) => {
    const detail = event?.error ?? event;
    console.error(
      "GreekTax failed to load the front-end module bundle.",
      detail,
    );
  });

  const parent = loaderScript.parentNode ?? document.head;
  if (loaderScript.nextSibling) {
    parent.insertBefore(moduleScript, loaderScript.nextSibling);
  } else {
    parent.appendChild(moduleScript);
  }
})();
