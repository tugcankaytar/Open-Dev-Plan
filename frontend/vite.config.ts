import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies /api to the FastAPI backend (uv run odp serve, port
// 8765) so the frontend can be developed with `npm run dev` while the
// backend runs separately. In production, `npm run build`'s output is
// served directly by FastAPI (see src/odp/api/app.py) and no proxy is
// needed — the frontend and API share an origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
