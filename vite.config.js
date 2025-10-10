import { defineConfig } from "vite";

export default defineConfig({
  root: "src/frontend",
  build: {
    outDir: "../../dist/frontend",
    emptyOutDir: true,
    sourcemap: true,
  },
});
