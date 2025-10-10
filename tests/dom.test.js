import { describe, expect, it, beforeEach } from "vitest";
import {
  select,
  selectAll,
  setText,
  setHidden,
  toggleClass,
  setAriaPressed,
  createElement,
} from "../src/frontend/assets/scripts/utils/dom.js";

beforeEach(() => {
  document.body.innerHTML = `
    <div id="container">
      <button data-role="primary"></button>
      <button data-role="secondary"></button>
    </div>
  `;
});

describe("DOM helpers", () => {
  it("selects single elements", () => {
    const button = select("[data-role=primary]");
    expect(button).toBeInstanceOf(HTMLElement);
  });

  it("selects multiple elements", () => {
    const buttons = selectAll("button");
    expect(buttons).toHaveLength(2);
  });

  it("updates text and hidden state", () => {
    const container = select("#container");
    setText(container, "Hello");
    expect(container?.textContent).toBe("Hello");
    setHidden(container, true);
    expect(container?.hidden).toBe(true);
  });

  it("toggles classes and aria state", () => {
    const button = select("[data-role=primary]");
    toggleClass(button, "active", true);
    expect(button?.classList.contains("active")).toBe(true);
    setAriaPressed(button, true);
    expect(button?.getAttribute("aria-pressed")).toBe("true");
  });

  it("creates elements with optional metadata", () => {
    const element = createElement("span", { text: "Hi", className: "tag" });
    expect(element?.textContent).toBe("Hi");
    expect(element?.className).toBe("tag");
  });
});
