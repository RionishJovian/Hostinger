import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
const apiTarget = process.env.MIKROMAGIC_DEV_API_TARGET || "http://127.0.0.1:8788";
const demoTarget = process.env.MIKROMAGIC_DEV_DEMO_TARGET || "http://127.0.0.1:8787";

export default defineConfig({
  build: {
    outDir: "dist/client",
  },
  optimizeDeps: {
    include: ["react", "react-dom/client"],
  },
  server: {
    host: "127.0.0.1",
    proxy: { "/api": demoTarget, "/v1": apiTarget },
    allowedHosts: ["terminal.local"],
    warmup: {
      clientFiles: ["./src/main.jsx"],
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
    proxy: { "/v1": apiTarget },
  },
  plugins: [react()],
});
