import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The live recommendation API (uvicorn src.api.main:app --port 8000).
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", rewrite: (path) => path.replace(/^\/api/, "") },
    },
  },
});
