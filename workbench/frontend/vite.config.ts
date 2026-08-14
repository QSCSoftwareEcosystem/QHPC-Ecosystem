import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";


const here = dirname(fileURLToPath(import.meta.url));


export default defineConfig({
  plugins: [react()],
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  test: {
    include: ["src/**/*.test.ts"],
  },
  build: {
    outDir: resolve(
      here,
      "../../src/qhpc_workbench/static/qhpc_workbench",
    ),
    emptyOutDir: true,
    cssCodeSplit: false,
    lib: {
      entry: resolve(here, "src/index.tsx"),
      formats: ["es"],
      fileName: () => "composer.js",
    },
    rollupOptions: {
      output: {
        assetFileNames: "composer.[ext]",
      },
    },
  },
});
