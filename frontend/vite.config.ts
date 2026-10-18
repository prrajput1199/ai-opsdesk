/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
    server: {
      port: 5173,
      // In development the API is proxied so the browser sees one origin: cookies stay
      // first-party and SameSite=Lax works without CORS.
      // Only /api is proxied: /admin/* belongs to the React app (the Django admin site is
      // available directly on the backend, e.g. http://localhost:8000/admin/).
      proxy: {
        "/api": { target: env.VITE_PROXY_TARGET || "http://localhost:8000", changeOrigin: false },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: false,
    },
  };
});
