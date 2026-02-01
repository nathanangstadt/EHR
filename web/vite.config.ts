import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/health": { target: process.env.VITE_PROXY_TARGET ?? "http://api:8000", changeOrigin: true },
      "/fhir": { target: process.env.VITE_PROXY_TARGET ?? "http://api:8000", changeOrigin: true },
      "/jobs": { target: process.env.VITE_PROXY_TARGET ?? "http://api:8000", changeOrigin: true },
      "/preauth": { target: process.env.VITE_PROXY_TARGET ?? "http://api:8000", changeOrigin: true },
      "/payer": { target: process.env.VITE_PROXY_TARGET ?? "http://api:8000", changeOrigin: true },
      "/internal": { target: process.env.VITE_PROXY_TARGET ?? "http://api:8000", changeOrigin: true },
    },
  },
});
