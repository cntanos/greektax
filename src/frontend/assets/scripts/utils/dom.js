export function getDocument(documentOverride) {
  if (documentOverride) {
    return documentOverride;
  }
  if (typeof document !== "undefined") {
    return document;
  }
  return null;
}

export function select(selector, { root = getDocument() } = {}) {
  return root?.querySelector?.(selector) ?? null;
}

export function selectAll(selector, { root = getDocument() } = {}) {
  return Array.from(root?.querySelectorAll?.(selector) ?? []);
}

export function setText(element, value) {
  if (!element) {
    return;
  }
  element.textContent = value;
}

export function setHidden(element, hidden) {
  if (!element) {
    return;
  }
  element.hidden = Boolean(hidden);
}

export function toggleClass(element, className, state) {
  if (!element || !element.classList) {
    return;
  }
  if (state === undefined) {
    element.classList.toggle(className);
  } else {
    element.classList.toggle(className, Boolean(state));
  }
}

export function setAriaPressed(element, state) {
  if (!element) {
    return;
  }
  element.setAttribute("aria-pressed", state ? "true" : "false");
}

export function createElement(tagName, { text = null, className = null } = {}) {
  const doc = getDocument();
  if (!doc) {
    return null;
  }
  const element = doc.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (text !== null && text !== undefined) {
    element.textContent = text;
  }
  return element;
}
