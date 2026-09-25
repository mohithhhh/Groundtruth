import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

// In development the app talks to the FastAPI server. Point API_TARGET at a
// deployed Cloud Run URL to develop the UI without running the backend.
const apiTarget = process.env.API_TARGET ?? "http://localhost:8080";

/**
 * MapLibre 6 parses GeoJSON in an ES-module web worker that it loads from a
 * separate file, and that worker imports ./maplibre-gl-shared.mjs relatively.
 * Bundling does not carry either file along, so ship both verbatim under
 * /maplibre/ and point MapLibre at them (see setWorkerUrl in main.tsx).
 */
function maplibreWorker(): Plugin {
  const dir = join(dirname(createRequire(import.meta.url).resolve("maplibre-gl/package.json")), "dist");
  const files = ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"];
  return {
    name: "penumbra-maplibre-worker",
    configureServer(server) {
      server.middlewares.use("/maplibre/", (req, res, next) => {
        const name = (req.url ?? "").replace(/^\//, "").split("?")[0];
        if (!files.includes(name)) return next();
        res.setHeader("Content-Type", "text/javascript");
        res.end(readFileSync(join(dir, name)));
      });
    },
    generateBundle() {
      for (const name of files) this.emitFile({ type: "asset", fileName: `maplibre/${name}`, source: readFileSync(join(dir, name)) });
    },
  };
}

export default defineConfig({
  plugins: [react(), maplibreWorker()],
  server: {
    port: 5173,
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 1600 },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
