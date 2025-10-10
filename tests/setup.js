import { beforeEach, vi } from "vitest";

globalThis.IS_REACT_ACT_ENVIRONMENT = false;

beforeEach(() => {
  vi.restoreAllMocks();
});
