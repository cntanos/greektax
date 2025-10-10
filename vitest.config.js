import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["tests/setup.js"],
    include: ["tests/**/*.test.js"],
    exclude: ["tests/frontend/**"],
    coverage: {
      reporter: ["text", "lcov"],
    },
  },
});
