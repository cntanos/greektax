// Guards the rule documented in CLAUDE.md: every identifier reference in
// src/frontend/assets/scripts/ui/app.js must resolve to a local declaration,
// an import binding, or a browser/standard global. PR #221 dropped eleven
// declarations and surfaced runtime ReferenceErrors only after deployment;
// this test exists so that regression cannot reach prod again.
//
// Identifiers in binding position (declarators, params, imports, non-computed
// member/property names) are skipped — only true reference reads/writes are
// checked.

import { strict as assert } from "node:assert";
import test from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

let parse;
try {
  const acornPkg = await import("acorn");
  parse = acornPkg.parse;
} catch (e) {
  // acorn is an optional dev dependency; skip gracefully when it is not
  // installed (e.g. CI runs that haven't executed `npm install`).
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const APP_JS = resolve(
  __dirname,
  "../../src/frontend/assets/scripts/ui/app.js"
);

const condTest = parse
  ? test
  : (name, fn) => test(name, { skip: "acorn is not installed" }, fn);

// Browser / standard-library globals that legitimately appear unimported.
// Extending this set is fine when adding code that uses a real platform API;
// adding to it as a workaround for a typo is not.
const GLOBALS = new Set([
  "window", "document", "navigator", "console", "fetch", "Headers",
  "URL", "URLSearchParams", "FormData", "Promise", "Map", "Set",
  "WeakMap", "WeakSet", "Array", "Object", "String", "Number",
  "Boolean", "Math", "Date", "JSON", "RegExp", "Error", "TypeError",
  "RangeError", "ReferenceError", "SyntaxError", "Symbol", "Intl",
  "BigInt", "ArrayBuffer", "Uint8Array", "Int32Array", "Float64Array",
  "parseInt", "parseFloat", "isNaN", "isFinite", "encodeURIComponent",
  "decodeURIComponent", "encodeURI", "decodeURI", "atob", "btoa",
  "queueMicrotask", "structuredClone", "setTimeout", "clearTimeout",
  "setInterval", "clearInterval", "requestAnimationFrame",
  "cancelAnimationFrame", "performance", "localStorage", "sessionStorage",
  "Element", "HTMLElement", "HTMLFieldSetElement", "HTMLInputElement",
  "HTMLSelectElement", "HTMLTextAreaElement", "HTMLFormElement",
  "HTMLButtonElement", "HTMLDetailsElement", "HTMLAnchorElement",
  "HTMLLabelElement", "HTMLOptionElement", "HTMLDivElement",
  "HTMLParagraphElement", "HTMLSpanElement", "HTMLTableElement",
  "HTMLTableRowElement", "HTMLTableCellElement", "HTMLImageElement",
  "HTMLLIElement", "HTMLUListElement", "HTMLOListElement",
  "HTMLHeadingElement", "HTMLPreElement", "HTMLScriptElement",
  "HTMLLinkElement", "HTMLMetaElement", "HTMLStyleElement",
  "HTMLTemplateElement", "HTMLBodyElement", "HTMLHtmlElement",
  "SVGElement", "SVGSVGElement",
  "Node", "Event", "CustomEvent", "MouseEvent", "KeyboardEvent",
  "FocusEvent", "InputEvent", "Plotly", "globalThis", "undefined",
  "NaN", "Infinity", "self", "Reflect", "Proxy",
  "ResizeObserver", "MutationObserver", "IntersectionObserver",
  "PerformanceObserver", "AbortController", "AbortSignal",
  "Blob", "File", "FileReader", "ImageData", "TextEncoder", "TextDecoder",
  "DOMParser", "XMLSerializer", "DataView", "Int8Array", "Uint16Array",
  "Int16Array", "Uint32Array", "Float32Array", "BigInt64Array",
  "BigUint64Array", "Uint8ClampedArray", "DOMException",
  "arguments",
]);

function collectPatternNames(pattern, set) {
  if (!pattern) return;
  if (pattern.type === "Identifier") set.add(pattern.name);
  else if (pattern.type === "ObjectPattern")
    for (const prop of pattern.properties) {
      if (prop.type === "RestElement") collectPatternNames(prop.argument, set);
      else collectPatternNames(prop.value, set);
    }
  else if (pattern.type === "ArrayPattern")
    for (const el of pattern.elements) collectPatternNames(el, set);
  else if (pattern.type === "AssignmentPattern")
    collectPatternNames(pattern.left, set);
  else if (pattern.type === "RestElement")
    collectPatternNames(pattern.argument, set);
}

function collectHoistedNames(stmt, set) {
  if (!stmt) return;
  if (stmt.type === "VariableDeclaration") {
    for (const decl of stmt.declarations) collectPatternNames(decl.id, set);
  } else if (stmt.type === "FunctionDeclaration" && stmt.id?.name) {
    set.add(stmt.id.name);
  } else if (stmt.type === "ClassDeclaration" && stmt.id?.name) {
    set.add(stmt.id.name);
  } else if (stmt.type === "ExportNamedDeclaration" && stmt.declaration) {
    collectHoistedNames(stmt.declaration, set);
  }
}

function bindingsFromPattern(pattern, set) {
  if (!pattern) return;
  if (pattern.type === "Identifier") {
    set.add(pattern);
  } else if (pattern.type === "ObjectPattern") {
    for (const prop of pattern.properties) {
      if (prop.type === "RestElement") bindingsFromPattern(prop.argument, set);
      else bindingsFromPattern(prop.value, set);
    }
  } else if (pattern.type === "ArrayPattern") {
    for (const el of pattern.elements) bindingsFromPattern(el, set);
  } else if (pattern.type === "AssignmentPattern") {
    bindingsFromPattern(pattern.left, set);
  } else if (pattern.type === "RestElement") {
    bindingsFromPattern(pattern.argument, set);
  }
}

function findUndeclaredReferences(source) {
  const ast = parse(source, {
    ecmaVersion: "latest",
    sourceType: "module",
    locations: true,
  });

  const moduleScope = new Set(GLOBALS);
  for (const node of ast.body) {
    if (node.type === "ImportDeclaration") {
      for (const spec of node.specifiers) {
        if (spec.local?.name) moduleScope.add(spec.local.name);
      }
    } else if (node.type === "VariableDeclaration") {
      for (const decl of node.declarations) {
        collectPatternNames(decl.id, moduleScope);
      }
    } else if (node.type === "FunctionDeclaration" && node.id?.name) {
      moduleScope.add(node.id.name);
    } else if (
      node.type === "ExportNamedDeclaration" &&
      node.declaration?.type === "FunctionDeclaration" &&
      node.declaration.id?.name
    ) {
      moduleScope.add(node.declaration.id.name);
    } else if (
      node.type === "ExportNamedDeclaration" &&
      node.declaration?.type === "VariableDeclaration"
    ) {
      for (const decl of node.declaration.declarations) {
        collectPatternNames(decl.id, moduleScope);
      }
    } else if (node.type === "ClassDeclaration" && node.id?.name) {
      moduleScope.add(node.id.name);
    }
  }

  const undefRefs = new Map();
  const bindingNodes = new Set();

  function inScope(name, scopeStack) {
    if (moduleScope.has(name)) return true;
    for (const scope of scopeStack) if (scope.has(name)) return true;
    return false;
  }

  function walk(node, scopeStack) {
    if (!node || typeof node !== "object") return;

    if (
      node.type === "FunctionDeclaration" ||
      node.type === "FunctionExpression" ||
      node.type === "ArrowFunctionExpression"
    ) {
      const newScope = new Set();
      if (node.id?.name) {
        newScope.add(node.id.name);
        bindingNodes.add(node.id);
      }
      for (const param of node.params || []) {
        collectPatternNames(param, newScope);
        bindingsFromPattern(param, bindingNodes);
      }
      if (node.body?.type === "BlockStatement") {
        for (const stmt of node.body.body) collectHoistedNames(stmt, newScope);
      }
      scopeStack = [...scopeStack, newScope];
    } else if (node.type === "BlockStatement") {
      const newScope = new Set();
      for (const stmt of node.body) collectHoistedNames(stmt, newScope);
      scopeStack = [...scopeStack, newScope];
    } else if (node.type === "CatchClause" && node.param) {
      const newScope = new Set();
      collectPatternNames(node.param, newScope);
      bindingsFromPattern(node.param, bindingNodes);
      scopeStack = [...scopeStack, newScope];
    } else if (
      (node.type === "ForStatement" ||
        node.type === "ForInStatement" ||
        node.type === "ForOfStatement") &&
      node.init?.type === "VariableDeclaration"
    ) {
      const newScope = new Set();
      for (const decl of node.init.declarations) {
        collectPatternNames(decl.id, newScope);
        bindingsFromPattern(decl.id, bindingNodes);
      }
      scopeStack = [...scopeStack, newScope];
    } else if (
      (node.type === "ForInStatement" || node.type === "ForOfStatement") &&
      node.left?.type === "VariableDeclaration"
    ) {
      const newScope = new Set();
      for (const decl of node.left.declarations) {
        collectPatternNames(decl.id, newScope);
        bindingsFromPattern(decl.id, bindingNodes);
      }
      scopeStack = [...scopeStack, newScope];
    }

    if (node.type === "VariableDeclarator") bindingsFromPattern(node.id, bindingNodes);
    if (node.type === "ImportSpecifier") bindingNodes.add(node.local);
    if (node.type === "ImportDefaultSpecifier") bindingNodes.add(node.local);
    if (node.type === "ImportNamespaceSpecifier") bindingNodes.add(node.local);
    if (node.type === "ClassDeclaration" && node.id) bindingNodes.add(node.id);
    if (node.type === "ClassExpression" && node.id) bindingNodes.add(node.id);
    if (node.type === "LabeledStatement") bindingNodes.add(node.label);
    if (node.type === "BreakStatement" && node.label) bindingNodes.add(node.label);
    if (node.type === "ContinueStatement" && node.label) bindingNodes.add(node.label);

    if (node.type === "MemberExpression" && !node.computed) bindingNodes.add(node.property);
    if (
      (node.type === "Property" || node.type === "PropertyDefinition") &&
      !node.computed &&
      !node.shorthand &&
      node.key
    ) {
      bindingNodes.add(node.key);
    }
    if (node.type === "MethodDefinition" && !node.computed && node.key) {
      bindingNodes.add(node.key);
    }

    if (node.type === "Identifier" && !bindingNodes.has(node)) {
      if (!inScope(node.name, scopeStack)) {
        if (!undefRefs.has(node.name)) undefRefs.set(node.name, []);
        undefRefs.get(node.name).push(node.loc.start.line);
      }
    }

    for (const key of Object.keys(node)) {
      if (key === "loc" || key === "start" || key === "end") continue;
      const child = node[key];
      if (Array.isArray(child)) {
        child.forEach((c) => walk(c, scopeStack));
      } else if (child && typeof child === "object" && child.type) {
        walk(child, scopeStack);
      }
    }
  }

  walk(ast, []);
  return undefRefs;
}

condTest("ui/app.js has no undeclared identifier references", () => {
  const source = readFileSync(APP_JS, "utf8");
  const undefRefs = findUndeclaredReferences(source);

  if (undefRefs.size > 0) {
    const lines = [];
    for (const [name, hits] of undefRefs) {
      const uniqueLines = [...new Set(hits)];
      lines.push(`  - ${name} (lines ${uniqueLines.join(", ")})`);
    }
    assert.fail(
      `Found ${undefRefs.size} undeclared identifier reference(s) in app.js:\n${lines.join("\n")}`
    );
  }
});
