import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api is proxied to FastAPI so the browser never hits CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
